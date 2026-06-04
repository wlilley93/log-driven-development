"""Normaliser for Artillery load test output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser


class ArtilleryNormaliser(BaseNormaliser):
    """Convert Artillery JSON report to Finding objects.

    Artillery JSON report shape:
    {
      "aggregate": {
        "counters": {
          "http.requests": 5000,
          "http.codes.200": 4900,
          "http.codes.500": 50,
          "http.codes.503": 50,
          "vusers.created": 500,
          "vusers.completed": 490,
          "vusers.failed": 10
        },
        "rates": {
          "http.request_rate": 166
        },
        "summaries": {
          "http.response_time": {
            "min": 5,
            "max": 3000,
            "mean": 150,
            "median": 120,
            "p50": 120,
            "p75": 200,
            "p90": 350,
            "p95": 500,
            "p99": 1200
          }
        },
        "histograms": { ... }
      }
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        aggregate = raw_data.get("aggregate", raw_data)
        if not isinstance(aggregate, dict):
            return []

        findings: list[Finding] = []

        # --- Latency percentiles ---
        summaries = aggregate.get("summaries", {})
        response_time = summaries.get("http.response_time", {})

        p99 = response_time.get("p99")
        p95 = response_time.get("p95")
        p50 = response_time.get("p50") or response_time.get("median")

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
                    tool="artillery",
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
                    raw={"p99": p99, "p95": p95, "p50": p50},
                ))

        if p95 is not None and (p99 is None or p99 / 1000.0 <= 0.5):
            p95_s = p95 / 1000.0
            if p95_s > 1.0:
                findings.append(Finding(
                    tool="artillery",
                    severity=Severity.HIGH if p95_s > 2.0 else Severity.MEDIUM,
                    category=Category.LOAD,
                    file="<url>",
                    rule_id="p95-latency",
                    rule_name="p95 Latency",
                    message=f"p95 latency is {p95:.0f}ms ({p95_s:.2f}s). Target: < 500ms.",
                    metric="p95_latency",
                    current_value=round(p95, 1),
                    target_value=500,
                    effort=Effort.HIGH,
                    fix_hint="Profile slow endpoints, optimise database queries, add response caching.",
                    raw={"p95": p95, "p50": p50},
                ))

        # --- Error rate ---
        counters = aggregate.get("counters", {})
        total_requests = counters.get("http.requests", 0)

        if total_requests > 0:
            # Count error codes (4xx, 5xx)
            error_count = 0
            for key, value in counters.items():
                if key.startswith("http.codes."):
                    try:
                        code = int(key.split(".")[-1])
                        if code >= 400:
                            error_count += value
                    except ValueError:
                        continue

            # Also count vuser failures
            vuser_failed = counters.get("vusers.failed", 0)

            error_pct = (error_count / total_requests) * 100
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
                    tool="artillery",
                    severity=severity,
                    category=Category.LOAD,
                    file="<url>",
                    rule_id="error-rate",
                    rule_name="HTTP Error Rate",
                    message=f"Error rate is {error_pct:.2f}% ({error_count}/{total_requests} requests). Target: < 0.1%.",
                    metric="error_rate",
                    current_value=round(error_pct, 2),
                    target_value=0.1,
                    effort=Effort.HIGH,
                    fix_hint="Investigate error codes, check for timeouts, connection limits, or server capacity issues.",
                    saving_estimate=f"Reduce error rate from {error_pct:.2f}% to < 0.1%",
                    raw={
                        "error_count": error_count,
                        "total_requests": total_requests,
                        "vuser_failed": vuser_failed,
                    },
                ))

        # --- RPS ---
        rates = aggregate.get("rates", {})
        rps = rates.get("http.request_rate")

        if rps is not None and rps < 10:
            findings.append(Finding(
                tool="artillery",
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
                raw=rates,
            ))

        return findings
