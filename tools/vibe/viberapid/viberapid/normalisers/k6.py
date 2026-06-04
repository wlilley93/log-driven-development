"""Normaliser for k6 load test output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser


class K6Normaliser(BaseNormaliser):
    """Convert k6 JSON summary output to Finding objects.

    k6 end-of-test summary JSON shape:
    {
      "metrics": {
        "http_req_duration": {
          "type": "trend",
          "contains": "time",
          "values": {
            "avg": 123.45,
            "min": 10.2,
            "med": 100.5,
            "max": 2500.0,
            "p(90)": 200.0,
            "p(95)": 350.0,
            "p(99)": 800.0
          },
          "thresholds": { "p(99)<500": { "ok": false } }
        },
        "http_req_failed": {
          "type": "rate",
          "contains": "default",
          "values": { "rate": 0.02, "passes": 100, "fails": 2 }
        },
        "http_reqs": {
          "type": "counter",
          "contains": "default",
          "values": { "count": 5000, "rate": 166.67 }
        },
        "iterations": {
          "type": "counter",
          "contains": "default",
          "values": { "count": 5000, "rate": 166.67 }
        }
      }
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        metrics = raw_data.get("metrics", {})
        findings: list[Finding] = []

        # --- p99 latency ---
        duration = metrics.get("http_req_duration", {})
        duration_values = duration.get("values", {})
        p99 = duration_values.get("p(99)")
        p95 = duration_values.get("p(95)")
        p50 = duration_values.get("med") or duration_values.get("p(50)")

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
                    tool="k6",
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

        # --- p95 latency (if no p99 finding, still report p95 issues) ---
        if p95 is not None and (p99 is None or p99 / 1000.0 <= 0.5):
            p95_s = p95 / 1000.0
            if p95_s > 1.0:
                findings.append(Finding(
                    tool="k6",
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
        failed = metrics.get("http_req_failed", {})
        failed_values = failed.get("values", {})
        error_rate = failed_values.get("rate")

        if error_rate is not None:
            error_pct = error_rate * 100
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
                    tool="k6",
                    severity=severity,
                    category=Category.LOAD,
                    file="<url>",
                    rule_id="error-rate",
                    rule_name="HTTP Error Rate",
                    message=f"Error rate is {error_pct:.2f}% under load. Target: < 0.1%.",
                    metric="error_rate",
                    current_value=round(error_pct, 2),
                    target_value=0.1,
                    effort=Effort.HIGH,
                    fix_hint="Investigate failing requests, check for timeouts, connection resets, or server errors under load.",
                    saving_estimate=f"Reduce error rate from {error_pct:.2f}% to < 0.1%",
                    raw=failed_values,
                ))

        # --- RPS (informational if very low) ---
        reqs = metrics.get("http_reqs", {})
        reqs_values = reqs.get("values", {})
        rps = reqs_values.get("rate")

        if rps is not None and rps < 10:
            findings.append(Finding(
                tool="k6",
                severity=Severity.MEDIUM,
                category=Category.LOAD,
                file="<url>",
                rule_id="low-rps",
                rule_name="Low Requests Per Second",
                message=f"Achieved only {rps:.1f} req/s. Server may be bottlenecked.",
                metric="rps",
                current_value=round(rps, 1),
                target_value=100,
                effort=Effort.HIGH,
                fix_hint="Profile server performance, check connection pooling, review concurrency limits.",
                raw=reqs_values,
            ))

        # --- Threshold violations ---
        thresholds = duration.get("thresholds", {})
        for threshold_name, threshold_result in thresholds.items():
            if isinstance(threshold_result, dict) and not threshold_result.get("ok", True):
                findings.append(Finding(
                    tool="k6",
                    severity=Severity.HIGH,
                    category=Category.LOAD,
                    file="<url>",
                    rule_id="threshold-violation",
                    rule_name="k6 Threshold Violation",
                    message=f"Threshold '{threshold_name}' failed.",
                    effort=Effort.HIGH,
                    fix_hint=f"Investigate why the threshold '{threshold_name}' was exceeded.",
                    raw={"threshold": threshold_name, "result": threshold_result},
                ))

        return findings
