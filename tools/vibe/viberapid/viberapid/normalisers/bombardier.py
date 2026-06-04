"""Normaliser for Bombardier load test output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser


class BombardierNormaliser(BaseNormaliser):
    """Convert Bombardier JSON output to Finding objects.

    Bombardier JSON shape (--format json --print result):
    {
      "spec": {
        "numberOfConnections": 50,
        "testType": "duration",
        "testDurationSeconds": 30,
        "method": "GET",
        "url": "http://localhost:3000",
        ...
      },
      "result": {
        "bytesRead": 15000000,
        "bytesWritten": 500000,
        "timeTakenSeconds": 30.05,
        "req1xx": 0,
        "req2xx": 4950,
        "req3xx": 0,
        "req4xx": 20,
        "req5xx": 30,
        "others": 0,
        "latency": {
          "mean": 45200000,
          "stddev": 12300000,
          "max": 1200000000,
          "percentiles": {
            "50": 40000000,
            "75": 55000000,
            "90": 70000000,
            "95": 100000000,
            "99": 200000000
          }
        },
        "rps": {
          "mean": 166.5,
          "stddev": 5.2,
          "max": 180.0,
          "percentiles": {
            "50": 165.0,
            "75": 170.0,
            "90": 175.0,
            "95": 178.0,
            "99": 180.0
          }
        }
      }
    }

    Note: Bombardier reports latencies in NANOSECONDS.
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        result = raw_data.get("result", raw_data)
        if not isinstance(result, dict):
            return []

        findings: list[Finding] = []
        latency = result.get("latency", {})
        percentiles = latency.get("percentiles", {})

        # --- p99 latency (nanoseconds -> milliseconds) ---
        p99_ns = percentiles.get("99")
        p95_ns = percentiles.get("95")
        p50_ns = percentiles.get("50")

        if p99_ns is not None:
            p99_ms = p99_ns / 1_000_000
            p99_s = p99_ms / 1000.0
            if p99_s > 2.0:
                severity = Severity.CRITICAL
            elif p99_s > 1.0:
                severity = Severity.HIGH
            elif p99_s > 0.5:
                severity = Severity.MEDIUM
            else:
                severity = None

            if severity:
                findings.append(Finding(
                    tool="bombardier",
                    severity=severity,
                    category=Category.LOAD,
                    file="<url>",
                    rule_id="p99-latency",
                    rule_name="p99 Latency",
                    message=f"p99 latency is {p99_ms:.0f}ms ({p99_s:.2f}s). Target: < 500ms.",
                    metric="p99_latency",
                    current_value=round(p99_ms, 1),
                    target_value=500,
                    effort=Effort.HIGH,
                    fix_hint="Profile slow endpoints, add caching, optimise database queries, consider horizontal scaling.",
                    saving_estimate=f"Reduce p99 latency from {p99_ms:.0f}ms to < 500ms",
                    raw={
                        "p99_ns": p99_ns,
                        "p95_ns": p95_ns,
                        "p50_ns": p50_ns,
                    },
                ))

        # --- p95 latency (only if p99 is fine) ---
        if p95_ns is not None and (p99_ns is None or p99_ns / 1_000_000 / 1000.0 <= 0.5):
            p95_ms = p95_ns / 1_000_000
            p95_s = p95_ms / 1000.0
            if p95_s > 1.0:
                findings.append(Finding(
                    tool="bombardier",
                    severity=Severity.HIGH if p95_s > 2.0 else Severity.MEDIUM,
                    category=Category.LOAD,
                    file="<url>",
                    rule_id="p95-latency",
                    rule_name="p95 Latency",
                    message=f"p95 latency is {p95_ms:.0f}ms ({p95_s:.2f}s). Target: < 500ms.",
                    metric="p95_latency",
                    current_value=round(p95_ms, 1),
                    target_value=500,
                    effort=Effort.HIGH,
                    fix_hint="Profile slow endpoints, optimise database queries, add response caching.",
                    raw={"p95_ns": p95_ns, "p50_ns": p50_ns},
                ))

        # --- Error rate ---
        req_2xx = result.get("req2xx", 0)
        req_3xx = result.get("req3xx", 0)
        req_4xx = result.get("req4xx", 0)
        req_5xx = result.get("req5xx", 0)
        others = result.get("others", 0)

        total = req_2xx + req_3xx + req_4xx + req_5xx + others
        total_errors = req_4xx + req_5xx + others

        if total > 0 and total_errors > 0:
            error_pct = (total_errors / total) * 100

            if error_pct > 1.0:
                severity = Severity.CRITICAL
            elif error_pct > 0.5:
                severity = Severity.HIGH
            elif error_pct > 0.1:
                severity = Severity.MEDIUM
            else:
                severity = Severity.LOW

            findings.append(Finding(
                tool="bombardier",
                severity=severity,
                category=Category.LOAD,
                file="<url>",
                rule_id="error-rate",
                rule_name="HTTP Error Rate",
                message=(
                    f"Error rate is {error_pct:.2f}% "
                    f"(4xx: {req_4xx}, 5xx: {req_5xx}, other: {others}). "
                    f"Target: < 0.1%."
                ),
                metric="error_rate",
                current_value=round(error_pct, 2),
                target_value=0.1,
                effort=Effort.HIGH,
                fix_hint="Investigate failing requests, check for timeouts, connection resets, or server errors under load.",
                saving_estimate=f"Reduce error rate from {error_pct:.2f}% to < 0.1%",
                raw={
                    "req_4xx": req_4xx,
                    "req_5xx": req_5xx,
                    "others": others,
                    "total": total,
                },
            ))

        # --- RPS ---
        rps_data = result.get("rps", {})
        rps = rps_data.get("mean")

        if rps is not None and rps < 10:
            findings.append(Finding(
                tool="bombardier",
                severity=Severity.MEDIUM,
                category=Category.LOAD,
                file="<url>",
                rule_id="low-rps",
                rule_name="Low Requests Per Second",
                message=f"Achieved only {rps:.1f} req/s under load. Server may be bottlenecked.",
                metric="rps",
                current_value=round(rps, 1),
                target_value=100,
                effort=Effort.HIGH,
                fix_hint="Profile server performance, check connection pooling, review concurrency limits.",
                raw=rps_data,
            ))

        return findings
