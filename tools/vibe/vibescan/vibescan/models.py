"""Normalised finding schema and scan result models."""

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
    SECRET = "SECRET"
    VULNERABILITY = "VULNERABILITY"
    CODE = "CODE"
    CONFIG = "CONFIG"
    LICENCE = "LICENCE"
    IAC = "IaC"


class ToolStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"


@dataclass
class Finding:
    """A single normalised finding from any tool."""

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
    cve: str | None = None
    cvss: float | None = None
    licence: str | None = None
    secret_verified: bool | None = None
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
    """Complete scan result across all tools."""

    target: str
    timestamp: str
    tool_results: list[ToolResult] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    deduplicated_findings: list[Finding] = field(default_factory=list)
    tool_overlap: dict[str, Any] = field(default_factory=dict)
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "timestamp": self.timestamp,
            "duration_seconds": self.duration_seconds,
            "exit_code": self.exit_code,
            "severity_counts": self.severity_counts,
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
