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
    BUNDLE = "BUNDLE"
    ASSET = "ASSET"
    NETWORK = "NETWORK"
    DATABASE = "DATABASE"
    RUNTIME = "RUNTIME"
    CACHE = "CACHE"
    DEPENDENCY = "DEPENDENCY"
    CSS = "CSS"
    FONT = "FONT"
    RENDER = "RENDER"
    COMPRESSION = "COMPRESSION"
    LOAD = "LOAD"
    CODE = "CODE"


class Effort(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

    @property
    def weight(self) -> int:
        return {Effort.LOW: 3, Effort.MEDIUM: 2, Effort.HIGH: 1}[self]


class ToolStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"


@dataclass
class Finding:
    """A single normalised performance finding from any tool."""

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
    metric: str | None = None
    current_value: float | None = None
    target_value: float | None = None
    saving_estimate: str | None = None
    effort: Effort = Effort.MEDIUM
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

    @property
    def quick_win_score(self) -> float:
        """Score for quick wins ranking: higher = better ROI."""
        sev_weight = {4: 4, 3: 3, 2: 2, 1: 1, 0: 0.5}
        return sev_weight.get(self.severity.rank, 1) * self.effort.weight

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["id"] = self.id
        d["severity"] = self.severity.value
        d["category"] = self.category.value
        d["effort"] = self.effort.value
        d["quick_win_score"] = self.quick_win_score
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
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class BudgetResult:
    """Result of checking a metric against a budget."""

    metric: str
    current: float
    target: float
    unit: str
    passed: bool
    fail_on_exceed: bool


@dataclass
class ScanResult:
    """Complete scan result across all tools."""

    target: str
    timestamp: str
    stack: str = "auto"
    tool_results: list[ToolResult] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    deduplicated_findings: list[Finding] = field(default_factory=list)
    tool_overlap: dict[str, Any] = field(default_factory=dict)
    budget_results: list[BudgetResult] = field(default_factory=list)
    quick_wins: list[Finding] = field(default_factory=list)
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
    def findings_by_category(self) -> dict[Category, list[Finding]]:
        result: dict[Category, list[Finding]] = {c: [] for c in Category}
        for f in self.deduplicated_findings:
            result[f.category].append(f)
        return result

    @property
    def estimated_gains(self) -> dict[str, str]:
        """Aggregate estimated savings from CRITICAL+HIGH findings."""
        gains: dict[str, list[str]] = {}
        for f in self.deduplicated_findings:
            if f.severity >= Severity.HIGH and f.saving_estimate:
                cat = f.category.value
                if cat not in gains:
                    gains[cat] = []
                gains[cat].append(f.saving_estimate)
        return {k: ", ".join(v) for k, v in gains.items()}

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "timestamp": self.timestamp,
            "stack": self.stack,
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
                    "metrics": tr.metrics,
                }
                for tr in self.tool_results
            ],
            "findings": [f.to_dict() for f in self.deduplicated_findings],
            "quick_wins": [f.to_dict() for f in self.quick_wins],
            "budget_results": [
                {
                    "metric": b.metric,
                    "current": b.current,
                    "target": b.target,
                    "unit": b.unit,
                    "passed": b.passed,
                    "fail_on_exceed": b.fail_on_exceed,
                }
                for b in self.budget_results
            ],
            "tool_overlap": self.tool_overlap,
        }

    def to_json(self, pretty: bool = False) -> str:
        indent = 2 if pretty else None
        return json.dumps(self.to_dict(), indent=indent, default=str)
