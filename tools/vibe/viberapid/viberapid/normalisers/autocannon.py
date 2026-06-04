"""Normaliser for autocannon load test output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser


class AutocannonNormaliser(BaseNormaliser):
    """Convert autocannon JSON output to Finding objects.

    autocannon JSON shape (with -j flag):
    {
      "url": "http://localhost:3000",
      "connections": 10,
      "sampleInt": 1000,
      "pipelining": 1,
      "duration": 30,
      "start": "2024-01-01T00:00:00.000Z",
      "finish": "2024-01-01T00:00:30.000Z",
      "errors": 5,
      "timeouts": 2,
      "mismatches": 0,
      "non2xx": 10,
      "resets": 0,
      "statusCodeStats": { "200": { "count": 4990 }, "500": { "count": 10 } },
      "latency": {
        "average": 45.2,
        "mean": 45.2,
        "stddev": 12.3,
        "min": 5,
        "max": 1200,
        "p0_001": 5,
        "p0_01": 6,
        "p0_1": 8,
        "p1": 10,
        "p2_5": 12,
        "p10": 20,
        "p25": 30,
        "p50": 40,
        "p75": 55,
        "p90": 70,
        "p97_5": 100,
        "p99": 200,
        "p99_9": 500,
        "p99_99": 1000,
        "p99_999": 1200,
        "totalCount": 5000
      },
      "requests": {
        "average": 166.5,
        "mean": 166.5,
        "stddev": 5.2,
        "min": 150,
        "max": 180,
        "total": 5000,
        "sent": 5000,
        "p0_001": 150,
        ...
      },
      "throughput": {
        "average": 1500000,
        "mean": 1500000,
        ...
      }
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        findings: list[Finding] = []
        latency = raw_data.get("latency", {})
        requests = raw_data.get("requests", {})

        # --- p99 latency ---
        p99 = latency.get("p99")
        p95 = latency.get("p97_5")  # autocannon uses p97.5 not p95
        p50 = latency.get("p50")

        if p99 is not None:
            p99_s = p99 / 1000.0
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
                    tool="autocannon",
                    severity=severity,
                    category=Category.LOAD,
                    file="<url>",
                    rule_id="p99-latency",
                    rule_name="p99 Latency",
                    message=f"p99 latency is {p99:.0f}ms ({p99_s:.2f}s). Target: < 500ms.",
                    metric="p99_latency",
                    current_value=round(p99, 1),
                    target_value=500,
                    effort=Effort.HIGH,
                    fix_hint="Profile slow endpoints, add caching, optimise database queries, consider horizontal scaling.",
                    saving_estimate=f"Reduce p99 latency from {p99:.0f}ms to < 500ms",
                    raw={"p99": p99, "p97_5": p95, "p50": p50},
                ))

        # --- Error rate ---
        errors = raw_data.get("errors", 0)
        timeouts = raw_data.get("timeouts", 0)
        non2xx = raw_data.get("non2xx", 0)
        total_requests = requests.get("total", 0)

        if total_requests > 0:
            total_errors = errors + timeouts + non2xx
            error_pct = (total_errors / total_requests) * 100

            if error_pct > 1.0:
                severity = Severity.CRITICAL
            elif error_pct > 0.5:
                severity = Severity.HIGH
            elif error_pct > 0.1:
                severity = Severity.MEDIUM
            else:
                severity = None

            if severity:
                findings.append(Finding(
                    tool="autocannon",
                    severity=severity,
                    category=Category.LOAD,
                    file="<url>",
                    rule_id="error-rate",
                    rule_name="HTTP Error Rate",
                    message=(
                        f"Error rate is {error_pct:.2f}% "
                        f"(errors: {errors}, timeouts: {timeouts}, non-2xx: {non2xx}). "
                        f"Target: < 0.1%."
                    ),
                    metric="error_rate",
                    current_value=round(error_pct, 2),
                    target_value=0.1,
                    effort=Effort.HIGH,
                    fix_hint="Investigate failing requests, check for timeouts, connection resets, or server errors under load.",
                    saving_estimate=f"Reduce error rate from {error_pct:.2f}% to < 0.1%",
                    raw={
                        "errors": errors,
                        "timeouts": timeouts,
                        "non2xx": non2xx,
                        "total": total_requests,
                    },
                ))

        # --- RPS ---
        rps = requests.get("average") or requests.get("mean")
        if rps is not None and rps < 10:
            findings.append(Finding(
                tool="autocannon",
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
                raw={"rps": rps},
            ))

        return findings
