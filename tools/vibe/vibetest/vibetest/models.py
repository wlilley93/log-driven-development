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
    MISSING = "MISSING"
    QUALITY = "QUALITY"
    SMELL = "SMELL"
    FLAKY = "FLAKY"
    COVERAGE = "COVERAGE"


class RunnerStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Finding:
    """A single normalised test quality finding."""

    runner: str
    severity: Severity
    category: Category
    file: str
    rule_id: str
    message: str
    line: int | None = None
    fix_hint: str | None = None
    raw: dict = field(default_factory=dict)

    @property
    def id(self) -> str:
        """Deterministic hash of runner+file+line+rule_id."""
        key = f"{self.runner}:{self.file}:{self.line}:{self.rule_id}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["id"] = self.id
        d["severity"] = self.severity.value
        d["category"] = self.category.value
        return d


@dataclass
class RunnerResult:
    """Result from a single runner."""

    runner: str
    status: RunnerStatus
    findings: list[Finding] = field(default_factory=list)
    duration_seconds: float = 0.0
    error: str | None = None


@dataclass
class ScanResult:
    """Complete scan result across all runners."""

    target: str
    timestamp: str
    runner_results: list[RunnerResult] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    duration_seconds: float = 0.0
    exit_code: int = 0

    @property
    def findings_by_severity(self) -> dict[Severity, list[Finding]]:
        result: dict[Severity, list[Finding]] = {s: [] for s in Severity}
        for f in self.findings:
            result[f.severity].append(f)
        return result

    @property
    def severity_counts(self) -> dict[str, int]:
        counts = {}
        for sev, findings in self.findings_by_severity.items():
            counts[sev.value] = len(findings)
        return counts

    @property
    def findings_by_category(self) -> dict[Category, list[Finding]]:
        result: dict[Category, list[Finding]] = {c: [] for c in Category}
        for f in self.findings:
            result[f.category].append(f)
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "timestamp": self.timestamp,
            "duration_seconds": self.duration_seconds,
            "exit_code": self.exit_code,
            "severity_counts": self.severity_counts,
            "runner_results": [
                {
                    "runner": rr.runner,
                    "status": rr.status.value,
                    "duration_seconds": rr.duration_seconds,
                    "finding_count": len(rr.findings),
                    "error": rr.error,
                }
                for rr in self.runner_results
            ],
            "findings": [f.to_dict() for f in self.findings],
        }

    def to_json(self, pretty: bool = False) -> str:
        indent = 2 if pretty else None
        return json.dumps(self.to_dict(), indent=indent, default=str)
