"""Core data types for vibeaudit findings and scan results."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, computed_field


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

    @property
    def rank(self) -> int:
        return {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3,
            Severity.INFO: 4,
        }[self]

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank < other.rank


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class VulnClass(str, Enum):
    IDOR = "idor"
    AUTH_BYPASS = "auth_bypass"
    MASS_ASSIGNMENT = "mass_assignment"
    RACE_CONDITION = "race_condition"
    BROKEN_ACCESS_CONTROL = "broken_access_control"
    JWT_MISCONFIG = "jwt_misconfig"
    SSRF = "ssrf"
    PATH_TRAVERSAL = "path_traversal"
    CRYPTO_WEAKNESS = "crypto_weakness"
    DATA_EXPOSURE = "data_exposure"
    COMMAND_INJECTION = "command_injection"
    XXE = "xxe"
    GRAPHQL = "graphql"
    PROTOTYPE_POLLUTION = "prototype_pollution"
    INSECURE_DEFAULTS = "insecure_defaults"
    TIMING_ATTACKS = "timing_attacks"
    MISSING_RATE_LIMIT = "missing_rate_limit"
    AI_PROMPT_INJECTION = "ai_prompt_injection"


# Human-readable labels
VULN_CLASS_LABELS: dict[VulnClass, str] = {
    VulnClass.IDOR: "Insecure Direct Object Reference",
    VulnClass.AUTH_BYPASS: "Authentication Bypass",
    VulnClass.MASS_ASSIGNMENT: "Mass Assignment",
    VulnClass.RACE_CONDITION: "Race Condition",
    VulnClass.BROKEN_ACCESS_CONTROL: "Broken Access Control",
    VulnClass.JWT_MISCONFIG: "JWT Misconfiguration",
    VulnClass.SSRF: "Server-Side Request Forgery",
    VulnClass.PATH_TRAVERSAL: "Path Traversal",
    VulnClass.CRYPTO_WEAKNESS: "Cryptographic Weakness",
    VulnClass.DATA_EXPOSURE: "Sensitive Data Exposure",
    VulnClass.COMMAND_INJECTION: "Command Injection",
    VulnClass.XXE: "XML External Entity",
    VulnClass.GRAPHQL: "GraphQL Security",
    VulnClass.PROTOTYPE_POLLUTION: "Prototype Pollution",
    VulnClass.INSECURE_DEFAULTS: "Insecure Defaults",
    VulnClass.TIMING_ATTACKS: "Timing Attack",
    VulnClass.MISSING_RATE_LIMIT: "Missing Rate Limiting",
    VulnClass.AI_PROMPT_INJECTION: "AI Prompt Injection",
}


class CodeSnippet(BaseModel):
    """A code excerpt extracted for analysis."""

    file_path: str
    start_line: int
    end_line: int
    content: str
    language: str = "unknown"


class Finding(BaseModel):
    """A single security finding from LLM analysis."""

    id: str = ""
    vuln_class: VulnClass
    severity: Severity
    confidence: Confidence
    title: str
    description: str
    attack_scenario: str = ""
    impact: str = ""
    remediation: str = ""
    fix_example: str = ""
    snippets: list[CodeSnippet] = Field(default_factory=list)
    cwe_id: str = ""
    owasp_category: str = ""
    affected_lines: list[int] = Field(default_factory=list)
    prompt_version: str = ""
    model: str = ""
    tokens_used: int = 0
    reasoning: str = ""
    false_positive_likelihood: str = ""
    raw_response: str = ""
    source: str = "vibeaudit"  # vibeaudit | sarif_import | agent

    def model_post_init(self, __context: object) -> None:
        if not self.id:
            self.id = self.compute_id()

    def compute_id(self) -> str:
        """Deterministic SHA256 hash for deduplication."""
        parts = [
            self.vuln_class.value,
            self.snippets[0].file_path if self.snippets else "",
            str(self.snippets[0].start_line) if self.snippets else "",
            str(self.snippets[0].end_line) if self.snippets else "",
            _normalize_code(self.snippets[0].content) if self.snippets else "",
        ]
        raw = "|".join(parts)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def file_location(self) -> str:
        if not self.snippets:
            return "unknown"
        s = self.snippets[0]
        return f"{s.file_path}:{s.start_line}"


class ScanResult(BaseModel):
    """Complete result of a vibeaudit scan."""

    findings: list[Finding] = Field(default_factory=list)
    scanned_files: int = 0
    scanned_classes: list[str] = Field(default_factory=list)
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    duration_seconds: float = 0.0
    provider: str = ""
    model: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def counts_by_severity(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for sev in Severity:
            count = sum(1 for f in self.findings if f.severity == sev)
            if count > 0:
                counts[sev.value] = count
        return counts


def _normalize_code(code: str) -> str:
    """Normalize code for dedup hashing — collapse whitespace, strip comments."""
    code = re.sub(r"//.*$", "", code, flags=re.MULTILINE)
    code = re.sub(r"#.*$", "", code, flags=re.MULTILINE)
    code = re.sub(r"\s+", " ", code)
    return code.strip()
