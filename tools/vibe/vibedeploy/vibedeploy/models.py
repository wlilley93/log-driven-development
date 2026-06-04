"""Normalised finding schema and scan result models for deploy readiness."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

    @property
    def rank(self) -> int:
        return {
            Severity.CRITICAL: 4,
            Severity.HIGH: 3,
            Severity.MEDIUM: 2,
            Severity.LOW: 1,
            Severity.INFO: 0,
        }[self]

    def __ge__(self, other: Severity) -> bool:
        return self.rank >= other.rank

    def __gt__(self, other: Severity) -> bool:
        return self.rank > other.rank

    def __le__(self, other: Severity) -> bool:
        return self.rank <= other.rank

    def __lt__(self, other: Severity) -> bool:
        return self.rank < other.rank


class Category(str, Enum):
    ENV_SECRETS = "ENV_SECRETS"
    DATABASE = "DATABASE"
    DOCKER = "DOCKER"
    IAC = "IaC"
    KUBERNETES = "KUBERNETES"
    SSL_TLS = "SSL_TLS"
    HTTP_HEADERS = "HTTP_HEADERS"
    CLOUD = "CLOUD"
    CORS_API = "CORS_API"
    BUILD = "BUILD"
    PROCESS = "PROCESS"
    LOGGING = "LOGGING"
    CONFIG = "CONFIG"
    SUPPLY_CHAIN = "SUPPLY_CHAIN"
    WEB_SERVER = "WEB_SERVER"
    DNS_NETWORK = "DNS_NETWORK"
    AST = "AST"
    GENERAL = "GENERAL"


class Effort(str, Enum):
    TRIVIAL = "TRIVIAL"      # < 5 minutes, single-line fix
    LOW = "LOW"              # < 30 minutes
    MEDIUM = "MEDIUM"        # 1-4 hours
    HIGH = "HIGH"            # > 4 hours, architectural change
    UNKNOWN = "UNKNOWN"


class ToolStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"


@dataclass
class Finding:
    """A single normalised deploy-readiness finding."""

    tool: str
    severity: Severity
    category: Category
    file: str
    rule_id: str
    rule_name: str
    message: str
    line: int | None = None
    col: int | None = None
    fix_hint: str | None = None
    fix_command: str | None = None
    docs_url: str | None = None
    blocks_deploy: bool = False
    effort: Effort = Effort.UNKNOWN
    cve: str | None = None
    cvss: float | None = None
    raw: dict = field(default_factory=dict)
    # Set by deduplicator
    tools: list[str] = field(default_factory=list)
    is_duplicate: bool = False
    duplicate_group: str | None = None

    @property
    def id(self) -> str:
        """Deterministic hash of tool+file+line+rule_id."""
        key = f"{self.tool}:{self.file}:{self.line}:{self.rule_id}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["id"] = self.id
        d["severity"] = self.severity.value
        d["category"] = self.category.value
        d["effort"] = self.effort.value
        return d


@dataclass
class ToolResult:
    """Result from a single tool run."""

    tool: str
    status: ToolStatus
    findings: list[Finding] = field(default_factory=list)
    duration_seconds: float = 0.0
    error: str | None = None
    version: str | None = None


@dataclass
class ScanResult:
    """Complete deploy-readiness scan result across all tools."""

    target: str
    timestamp: str
    tool_results: list[ToolResult] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    deduplicated_findings: list[Finding] = field(default_factory=list)
    tool_overlap: dict[str, Any] = field(default_factory=dict)
    stack_info: dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 0.0
    exit_code: int = 0

    @property
    def findings_by_severity(self) -> dict[Severity, list[Finding]]:
        result: dict[Severity, list[Finding]] = {s: [] for s in Severity}
        for f in self.deduplicated_findings:
            result[f.severity].append(f)
        return result

    @property
    def severity_counts(self) -> dict[str, int]:
        counts = {}
        for sev, findings in self.findings_by_severity.items():
            counts[sev.value] = len(findings)
        return counts

    @property
    def deploy_blockers(self) -> list[Finding]:
        return [f for f in self.deduplicated_findings if f.blocks_deploy]

    @property
    def deploy_ready(self) -> bool:
        return len(self.deploy_blockers) == 0

    @property
    def readiness_score(self) -> int:
        """0-100 deploy readiness score. 100 = no findings."""
        if not self.deduplicated_findings:
            return 100
        penalty = 0
        for f in self.deduplicated_findings:
            if f.blocks_deploy:
                penalty += 20
            elif f.severity == Severity.CRITICAL:
                penalty += 15
            elif f.severity == Severity.HIGH:
                penalty += 8
            elif f.severity == Severity.MEDIUM:
                penalty += 3
            elif f.severity == Severity.LOW:
                penalty += 1
        return max(0, 100 - penalty)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "timestamp": self.timestamp,
            "duration_seconds": self.duration_seconds,
            "exit_code": self.exit_code,
            "deploy_ready": self.deploy_ready,
            "readiness_score": self.readiness_score,
            "severity_counts": self.severity_counts,
            "blocker_count": len(self.deploy_blockers),
            "stack_info": self.stack_info,
            "tool_results": [
                {
                    "tool": tr.tool,
                    "status": tr.status.value,
                    "duration_seconds": tr.duration_seconds,
                    "finding_count": len(tr.findings),
                    "error": tr.error,
                    "version": tr.version,
                }
                for tr in self.tool_results
            ],
            "findings": [f.to_dict() for f in self.deduplicated_findings],
            "tool_overlap": self.tool_overlap,
        }

    def to_json(self, pretty: bool = False) -> str:
        indent = 2 if pretty else None
        return json.dumps(self.to_dict(), indent=indent, default=str)
