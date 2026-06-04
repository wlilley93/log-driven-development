"""Normaliser for wrk load test output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser


class WrkNormaliser(BaseNormaliser):
    """Convert parsed wrk output dict to Finding objects.

    The runner parses wrk's text output into a dict with this shape:
    {
      "latency_avg_ms": 45.2,
      "latency_stdev_ms": 12.3,
      "latency_max_ms": 1200.0,
      "latency_stdev_pct": "78.5%",
      "req_sec_avg": 166.5,
      "req_sec_stdev": 5.2,
      "req_sec_max": 180.0,
      "total_requests": 5000,
      "duration_s": 30.0,
      "transfer_bytes": 15000000,
      "rps": 166.67,
      "errors_connect": 0,
      "errors_read": 2,
      "errors_write": 0,
      "errors_timeout": 1,
      "non_2xx_3xx": 5
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        findings: list[Finding] = []

        # --- Average latency ---
        avg_ms = raw_data.get("latency_avg_ms")
        max_ms = raw_data.get("latency_max_ms")

        if avg_ms is not None:
            avg_s = avg_ms / 1000.0
            if avg_s > 2.0:
                severity = Severity.CRITICAL
            elif avg_s > 1.0:
                severity = Severity.HIGH
            elif avg_s > 0.5:
                severity = Severity.MEDIUM
            else:
                severity = None

            if severity:
                msg = f"Average latency is {avg_ms:.0f}ms ({avg_s:.2f}s)."
                if max_ms is not None:
                    msg += f" Max: {max_ms:.0f}ms."
                findings.append(Finding(
                    tool="wrk",
                    severity=severity,
                    category=Category.LOAD,
                    file="<url>",
                    rule_id="avg-latency",
                    rule_name="Average Latency",
                    message=msg + " Target: < 200ms avg.",
                    metric="avg_latency",
                    current_value=round(avg_ms, 1),
                    target_value=200,
                    effort=Effort.HIGH,
                    fix_hint="Profile slow endpoints, add caching, optimise database queries.",
                    saving_estimate=f"Reduce average latency from {avg_ms:.0f}ms to < 200ms",
                    raw={"avg_ms": avg_ms, "max_ms": max_ms},
                ))

        # --- Max latency spikes ---
        if max_ms is not None and avg_ms is not None:
            if max_ms > avg_ms * 10 and max_ms > 5000:
                findings.append(Finding(
                    tool="wrk",
                    severity=Severity.HIGH,
                    category=Category.LOAD,
                    file="<url>",
                    rule_id="latency-spike",
                    rule_name="Latency Spike",
                    message=f"Max latency ({max_ms:.0f}ms) is {max_ms / avg_ms:.0f}x the average. Likely GC pauses or resource contention.",
                    metric="max_latency",
                    current_value=round(max_ms, 1),
                    target_value=round(avg_ms * 5, 1),
                    effort=Effort.HIGH,
                    fix_hint="Investigate tail latency causes: GC pauses, lock contention, cold cache, connection pool exhaustion.",
                    raw={"max_ms": max_ms, "avg_ms": avg_ms, "ratio": max_ms / avg_ms},
                ))

        # --- Error rate ---
        total_requests = raw_data.get("total_requests", 0)
        errors_connect = raw_data.get("errors_connect", 0)
        errors_read = raw_data.get("errors_read", 0)
        errors_write = raw_data.get("errors_write", 0)
        errors_timeout = raw_data.get("errors_timeout", 0)
        non_2xx_3xx = raw_data.get("non_2xx_3xx", 0)

        total_errors = errors_connect + errors_read + errors_write + errors_timeout + non_2xx_3xx

        if total_requests > 0 and total_errors > 0:
            error_pct = (total_errors / total_requests) * 100

            if error_pct > 1.0:
                severity = Severity.CRITICAL
            elif error_pct > 0.5:
                severity = Severity.HIGH
            elif error_pct > 0.1:
                severity = Severity.MEDIUM
            else:
                severity = Severity.LOW

            findings.append(Finding(
                tool="wrk",
                severity=severity,
                category=Category.LOAD,
                file="<url>",
                rule_id="error-rate",
                rule_name="HTTP Error Rate",
                message=(
                    f"Error rate: {error_pct:.2f}% "
                    f"(connect: {errors_connect}, read: {errors_read}, "
                    f"write: {errors_write}, timeout: {errors_timeout}, "
                    f"non-2xx/3xx: {non_2xx_3xx}). Target: < 0.1%."
                ),
                metric="error_rate",
                current_value=round(error_pct, 2),
                target_value=0.1,
                effort=Effort.HIGH,
                fix_hint="Investigate server errors under load. Check connection limits, timeouts, and resource exhaustion.",
                saving_estimate=f"Reduce error rate from {error_pct:.2f}% to < 0.1%",
                raw={
                    "connect": errors_connect,
                    "read": errors_read,
                    "write": errors_write,
                    "timeout": errors_timeout,
                    "non_2xx_3xx": non_2xx_3xx,
                    "total_requests": total_requests,
                },
            ))

        # --- RPS ---
        rps = raw_data.get("rps")
        if rps is not None and rps < 10:
            findings.append(Finding(
                tool="wrk",
                severity=Severity.MEDIUM,
                category=Category.LOAD,
                file="<url>",
                rule_id="low-rps",
                rule_name="Low Requests Per Second",
                message=f"Achieved only {rps:.1f} req/s under load.",
                metric="rps",
                current_value=round(rps, 1),
                target_value=100,
                effort=Effort.HIGH,
                fix_hint="Profile server performance, check connection pooling, review concurrency limits.",
                raw={"rps": rps},
            ))

        return findings
