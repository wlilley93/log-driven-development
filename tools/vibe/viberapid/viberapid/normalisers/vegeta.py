"""Normaliser for Vegeta load test output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser


class VegetaNormaliser(BaseNormaliser):
    """Convert Vegeta JSON report to Finding objects.

    Vegeta JSON report shape (vegeta report -type=json):
    {
      "latencies": {
        "total": 500000000000,
        "mean": 100000000,
        "50th": 80000000,
        "90th": 200000000,
        "95th": 350000000,
        "99th": 800000000,
        "max": 2500000000,
        "min": 5000000
      },
      "bytes_in": { "total": 15000000, "mean": 3000 },
      "bytes_out": { "total": 0, "mean": 0 },
      "earliest": "2024-01-01T00:00:00Z",
      "latest": "2024-01-01T00:00:30Z",
      "end": "2024-01-01T00:00:30.1Z",
      "duration": 30000000000,
      "wait": 100000000,
      "requests": 5000,
      "rate": 166.67,
      "throughput": 165.5,
      "success": 0.98,
      "status_codes": { "200": 4900, "500": 50, "503": 50 },
      "errors": ["500 Internal Server Error", ...]
    }

    Note: Vegeta reports latencies in NANOSECONDS.
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        findings: list[Finding] = []
        latencies = raw_data.get("latencies", {})

        # Convert nanoseconds to milliseconds
        p99_ns = latencies.get("99th")
        p95_ns = latencies.get("95th")
        p50_ns = latencies.get("50th")
        mean_ns = latencies.get("mean")
        max_ns = latencies.get("max")

        # --- p99 latency ---
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
                    tool="vegeta",
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
                        "mean_ns": mean_ns,
                    },
                ))

        # --- p95 latency (only if p99 is fine) ---
        if p95_ns is not None and (p99_ns is None or p99_ns / 1_000_000 / 1000.0 <= 0.5):
            p95_ms = p95_ns / 1_000_000
            p95_s = p95_ms / 1000.0
            if p95_s > 1.0:
                findings.append(Finding(
                    tool="vegeta",
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

        # --- Success ratio / error rate ---
        success = raw_data.get("success")
        total_requests = raw_data.get("requests", 0)

        if success is not None and total_requests > 0:
            error_pct = (1.0 - success) * 100

            if error_pct > 1.0:
                severity = Severity.CRITICAL
            elif error_pct > 0.5:
                severity = Severity.HIGH
            elif error_pct > 0.1:
                severity = Severity.MEDIUM
            else:
                severity = None

            if severity:
                # Collect error status codes
                status_codes = raw_data.get("status_codes", {})
                error_codes = {
                    code: count
                    for code, count in status_codes.items()
                    if isinstance(code, str) and code.isdigit() and int(code) >= 400
                }

                findings.append(Finding(
                    tool="vegeta",
                    severity=severity,
                    category=Category.LOAD,
                    file="<url>",
                    rule_id="error-rate",
                    rule_name="HTTP Error Rate",
                    message=f"Error rate is {error_pct:.2f}% (success ratio: {success:.4f}). Target: < 0.1%.",
                    metric="error_rate",
                    current_value=round(error_pct, 2),
                    target_value=0.1,
                    effort=Effort.HIGH,
                    fix_hint="Investigate error responses, check server logs for 5xx errors under load.",
                    saving_estimate=f"Reduce error rate from {error_pct:.2f}% to < 0.1%",
                    raw={
                        "success": success,
                        "error_codes": error_codes,
                        "total_requests": total_requests,
                    },
                ))

        # --- Throughput ---
        throughput = raw_data.get("throughput")
        rate = raw_data.get("rate")

        if throughput is not None and rate is not None and rate > 0:
            if throughput < rate * 0.9:
                drop_pct = ((rate - throughput) / rate) * 100
                findings.append(Finding(
                    tool="vegeta",
                    severity=Severity.MEDIUM,
                    category=Category.LOAD,
                    file="<url>",
                    rule_id="throughput-drop",
                    rule_name="Throughput Below Target Rate",
                    message=f"Actual throughput ({throughput:.1f} req/s) is {drop_pct:.1f}% below target rate ({rate:.1f} req/s).",
                    metric="throughput",
                    current_value=round(throughput, 1),
                    target_value=round(rate, 1),
                    effort=Effort.HIGH,
                    fix_hint="Server cannot sustain the requested rate. Profile bottlenecks and scale resources.",
                    raw={"throughput": throughput, "rate": rate, "drop_pct": drop_pct},
                ))

        return findings
