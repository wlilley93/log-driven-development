"""Normaliser for clinic output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser

# Mapping of diagnostic types to structured finding data
DIAGNOSTIC_MAP = {
    "event-loop-delay": {
        "rule_id": "clinic/event-loop-delay",
        "rule_name": "Event loop delay",
        "default_severity": Severity.HIGH,
        "fix_hint": (
            "Event loop delays block all concurrent requests. Move CPU-intensive work "
            "to worker threads (worker_threads module), break large synchronous operations "
            "into smaller async chunks, or offload to a job queue (Bull, BullMQ)."
        ),
        "effort": Effort.HIGH,
    },
    "memory-leak": {
        "rule_id": "clinic/memory-leak",
        "rule_name": "Memory leak detected",
        "default_severity": Severity.HIGH,
        "fix_hint": (
            "Memory leaks cause increasing latency and eventual OOM crashes. Check for: "
            "growing Maps/Sets/arrays that are never pruned, closures capturing large scopes, "
            "unremoved event listeners, unclosed streams/sockets, and global caches without "
            "TTL. Use --inspect with Chrome DevTools heap snapshots to identify retained objects."
        ),
        "effort": Effort.HIGH,
    },
    "high-cpu": {
        "rule_id": "clinic/high-cpu",
        "rule_name": "High CPU usage",
        "default_severity": Severity.MEDIUM,
        "fix_hint": (
            "High CPU on the main thread degrades request throughput. Identify the hot code "
            "path with `clinic flame` or `0x`, then consider: worker_threads for CPU work, "
            "caching computed results, or optimising the algorithm. Avoid JSON.parse/stringify "
            "on large payloads in the request path."
        ),
        "effort": Effort.MEDIUM,
    },
    "gc-pressure": {
        "rule_id": "clinic/gc-pressure",
        "rule_name": "GC pressure",
        "default_severity": Severity.MEDIUM,
        "fix_hint": (
            "Excessive garbage collection pauses degrade tail latency. Reduce allocations: "
            "reuse objects/buffers, use object pools, prefer Buffer.allocUnsafe for short-lived "
            "buffers, avoid creating closures in hot loops, and consider --max-old-space-size "
            "tuning for the V8 heap."
        ),
        "effort": Effort.MEDIUM,
    },
    "handle-leak": {
        "rule_id": "clinic/handle-leak",
        "rule_name": "Handle leak",
        "default_severity": Severity.MEDIUM,
        "fix_hint": (
            "Leaking handles (sockets, file descriptors, timers) prevents graceful shutdown "
            "and wastes OS resources. Ensure: all streams are properly closed/destroyed, "
            "setTimeout/setInterval are cleared, database connections are released back to "
            "the pool, and HTTP agents manage keep-alive connections."
        ),
        "effort": Effort.MEDIUM,
    },
    "io-delay": {
        "rule_id": "clinic/io-delay",
        "rule_name": "I/O delay",
        "default_severity": Severity.MEDIUM,
        "fix_hint": (
            "Slow I/O operations (disk, network) block the event loop when done synchronously. "
            "Use async fs operations, connection pooling for databases, and HTTP keep-alive. "
            "Consider batching multiple small I/O operations."
        ),
        "effort": Effort.MEDIUM,
    },
}


class ClinicNormaliser(BaseNormaliser):
    """Convert clinic JSON output to Finding objects.

    clinic JSON shape varies by subcommand. Supported shapes:

    1. Structured diagnostics:
    {
      "diagnostics": [
        {
          "type": "event-loop-delay",
          "message": "...",
          "severity": "high"
        }
      ]
    }

    2. Analysis data (from .clinic directory):
    {
      "analysis": {
        "eventLoop": {"delay": {"mean": 5.2, "max": 150.3}},
        "cpu": {"mean": 85.2, "max": 100},
        "memory": {"rss": {"trend": "increasing"}},
        "handles": {"trend": "increasing"}
      }
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        findings: list[Finding] = []

        # Handle structured diagnostics format
        diagnostics = raw_data.get("diagnostics", [])
        if isinstance(diagnostics, list):
            for diag in diagnostics:
                if not isinstance(diag, dict):
                    continue
                finding = self._normalise_diagnostic(diag)
                if finding:
                    findings.append(finding)

        # Handle analysis data format
        analysis = raw_data.get("analysis", {})
        if isinstance(analysis, dict):
            findings.extend(self._normalise_analysis(analysis))

        return findings

    def _normalise_diagnostic(self, diag: dict[str, Any]) -> Finding | None:
        """Convert a single diagnostic entry to a Finding."""
        diag_type = diag.get("type", "unknown")
        message = diag.get("message", f"Clinic detected issue: {diag_type}")
        raw_severity = diag.get("severity", "medium").lower()

        template = DIAGNOSTIC_MAP.get(diag_type)

        if template:
            severity = self._parse_severity(raw_severity, template["default_severity"])
            return Finding(
                tool="clinic",
                severity=severity,
                category=Category.RUNTIME,
                file=diag.get("file", "server"),
                rule_id=template["rule_id"],
                rule_name=template["rule_name"],
                message=message,
                line=diag.get("line"),
                fix_hint=template["fix_hint"],
                effort=template["effort"],
                raw=diag,
            )

        # Unknown diagnostic type — still report it
        severity = self._parse_severity(raw_severity, Severity.MEDIUM)
        return Finding(
            tool="clinic",
            severity=severity,
            category=Category.RUNTIME,
            file=diag.get("file", "server"),
            rule_id=f"clinic/{diag_type}",
            rule_name=diag_type.replace("-", " ").title(),
            message=message,
            fix_hint=f"Clinic flagged a '{diag_type}' issue. Run `npx clinic doctor` interactively for detailed analysis.",
            effort=Effort.MEDIUM,
            raw=diag,
        )

    def _normalise_analysis(self, analysis: dict[str, Any]) -> list[Finding]:
        """Convert analysis data to findings."""
        findings: list[Finding] = []

        # Event loop analysis
        event_loop = analysis.get("eventLoop", {})
        if isinstance(event_loop, dict):
            delay = event_loop.get("delay", {})
            if isinstance(delay, dict):
                max_delay = _safe_float(delay.get("max", 0))
                mean_delay = _safe_float(delay.get("mean", 0))

                if max_delay > 100:  # >100ms max delay is problematic
                    findings.append(Finding(
                        tool="clinic",
                        severity=Severity.HIGH if max_delay > 500 else Severity.MEDIUM,
                        category=Category.RUNTIME,
                        file="server",
                        rule_id="clinic/event-loop-delay",
                        rule_name="Event loop delay",
                        message=(
                            f"Event loop max delay: {max_delay:.0f}ms "
                            f"(mean: {mean_delay:.1f}ms). Requests are being queued."
                        ),
                        fix_hint=DIAGNOSTIC_MAP["event-loop-delay"]["fix_hint"],
                        metric="event_loop_delay_ms",
                        current_value=round(max_delay, 1),
                        target_value=100.0,
                        effort=Effort.HIGH,
                        raw={"event_loop_delay": delay},
                    ))

        # CPU analysis
        cpu = analysis.get("cpu", {})
        if isinstance(cpu, dict):
            mean_cpu = _safe_float(cpu.get("mean", 0))
            max_cpu = _safe_float(cpu.get("max", 0))

            if mean_cpu > 70:  # >70% mean CPU is concerning
                findings.append(Finding(
                    tool="clinic",
                    severity=Severity.HIGH if mean_cpu > 90 else Severity.MEDIUM,
                    category=Category.RUNTIME,
                    file="server",
                    rule_id="clinic/high-cpu",
                    rule_name="High CPU usage",
                    message=(
                        f"Mean CPU usage: {mean_cpu:.0f}% "
                        f"(peak: {max_cpu:.0f}%). Server is CPU-bound."
                    ),
                    fix_hint=DIAGNOSTIC_MAP["high-cpu"]["fix_hint"],
                    metric="cpu_percent",
                    current_value=round(mean_cpu, 1),
                    target_value=70.0,
                    effort=Effort.MEDIUM,
                    raw={"cpu": cpu},
                ))

        # Memory analysis
        memory = analysis.get("memory", {})
        if isinstance(memory, dict):
            rss = memory.get("rss", {})
            if isinstance(rss, dict):
                trend = rss.get("trend", "").lower()
                if trend == "increasing":
                    findings.append(Finding(
                        tool="clinic",
                        severity=Severity.HIGH,
                        category=Category.RUNTIME,
                        file="server",
                        rule_id="clinic/memory-leak",
                        rule_name="Memory leak detected",
                        message="RSS memory trend is increasing, indicating a potential memory leak.",
                        fix_hint=DIAGNOSTIC_MAP["memory-leak"]["fix_hint"],
                        effort=Effort.HIGH,
                        raw={"memory": memory},
                    ))

        # Handle analysis
        handles = analysis.get("handles", {})
        if isinstance(handles, dict):
            trend = handles.get("trend", "").lower()
            if trend == "increasing":
                findings.append(Finding(
                    tool="clinic",
                    severity=Severity.MEDIUM,
                    category=Category.RUNTIME,
                    file="server",
                    rule_id="clinic/handle-leak",
                    rule_name="Handle leak",
                    message="Active handle count is increasing, indicating handle/connection leaks.",
                    fix_hint=DIAGNOSTIC_MAP["handle-leak"]["fix_hint"],
                    effort=Effort.MEDIUM,
                    raw={"handles": handles},
                ))

        return findings

    def _parse_severity(self, raw: str, default: Severity) -> Severity:
        """Parse a severity string to a Severity enum."""
        mapping = {
            "critical": Severity.CRITICAL,
            "high": Severity.HIGH,
            "medium": Severity.MEDIUM,
            "low": Severity.LOW,
            "info": Severity.INFO,
        }
        return mapping.get(raw.lower(), default)


def _safe_float(value: Any) -> float:
    """Safely convert a value to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
