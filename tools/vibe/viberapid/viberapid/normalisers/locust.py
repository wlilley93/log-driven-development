"""Normaliser for locust load test CSV output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser


class LocustNormaliser(BaseNormaliser):
    """Convert locust CSV stats output to Finding objects.

    Expected raw_data shape:
    {
      "stats": [
        {
          "Type": "GET",
          "Name": "/",
          "Request Count": "5000",
          "Failure Count": "50",
          "Median Response Time": "120",
          "Average Response Time": "150",
          "Min Response Time": "5",
          "Max Response Time": "3200",
          "Average Content Size": "2048",
          "Requests/s": "166.5",
          "Failures/s": "1.7",
          "50%": "120",
          "66%": "150",
          "75%": "180",
          "80%": "200",
          "90%": "350",
          "95%": "500",
          "98%": "800",
          "99%": "1200",
          "99.9%": "2500",
          "99.99%": "3000",
          "100%": "3200"
        },
        {
          "Name": "Aggregated",
          ...
        }
      ],
      "failures": [
        {
          "Method": "GET",
          "Name": "/",
          "Error": "ConnectionError(...)",
          "Occurrences": "50"
        }
      ]
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        stats_rows = raw_data.get("stats", [])
        failure_rows = raw_data.get("failures", [])

        if not isinstance(stats_rows, list):
            return []

        findings: list[Finding] = []

        # Find the Aggregated row for overall metrics
        aggregated = None
        for row in stats_rows:
            if not isinstance(row, dict):
                continue
            if row.get("Name") == "Aggregated":
                aggregated = row
                break

        if aggregated is None:
            return []

        total_requests = _safe_int(aggregated.get("Request Count"))
        failure_count = _safe_int(aggregated.get("Failure Count"))

        # --- p99 latency ---
        p99 = _safe_float(aggregated.get("99%"))
        p95 = _safe_float(aggregated.get("95%"))
        p50 = _safe_float(aggregated.get("50%"))

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
                    tool="locust",
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
                    fix_hint=(
                        "Profile slow endpoints, add caching, optimise database queries, "
                        "consider horizontal scaling."
                    ),
                    saving_estimate=f"Reduce p99 latency from {p99:.0f}ms to < 500ms",
                    raw={"p99": p99, "p95": p95, "p50": p50},
                ))

        # --- p95 latency (only if p99 is acceptable) ---
        if p95 is not None and (p99 is None or p99 / 1000.0 <= 0.5):
            p95_s = p95 / 1000.0
            if p95_s > 1.0:
                findings.append(Finding(
                    tool="locust",
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
                    fix_hint=(
                        "Profile slow endpoints, optimise database queries, "
                        "add response caching."
                    ),
                    raw={"p95": p95, "p50": p50},
                ))

        # --- Error rate ---
        if total_requests and total_requests > 0 and failure_count is not None:
            error_pct = (failure_count / total_requests) * 100
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
                    tool="locust",
                    severity=severity,
                    category=Category.LOAD,
                    file="<url>",
                    rule_id="error-rate",
                    rule_name="HTTP Error Rate",
                    message=(
                        f"Error rate is {error_pct:.2f}% "
                        f"({failure_count}/{total_requests} requests). Target: < 0.1%."
                    ),
                    metric="error_rate",
                    current_value=round(error_pct, 2),
                    target_value=0.1,
                    effort=Effort.HIGH,
                    fix_hint=(
                        "Investigate failing requests, check for timeouts, connection "
                        "resets, or server errors under load."
                    ),
                    saving_estimate=f"Reduce error rate from {error_pct:.2f}% to < 0.1%",
                    raw={
                        "failure_count": failure_count,
                        "total_requests": total_requests,
                    },
                ))

        # --- RPS (informational if very low) ---
        rps = _safe_float(aggregated.get("Requests/s"))
        if rps is not None and rps < 10:
            findings.append(Finding(
                tool="locust",
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
                fix_hint=(
                    "Profile server performance, check connection pooling, "
                    "review concurrency limits."
                ),
                raw={"rps": rps},
            ))

        # --- Per-endpoint high latency (non-aggregated rows) ---
        for row in stats_rows:
            if not isinstance(row, dict):
                continue
            name = row.get("Name", "")
            if name == "Aggregated" or not name:
                continue

            endpoint_p99 = _safe_float(row.get("99%"))
            if endpoint_p99 is not None and endpoint_p99 > 2000:
                findings.append(Finding(
                    tool="locust",
                    severity=Severity.HIGH,
                    category=Category.LOAD,
                    file="<url>",
                    rule_id="endpoint-slow",
                    rule_name="Slow Endpoint",
                    message=(
                        f"Endpoint '{name}' has p99 latency of {endpoint_p99:.0f}ms "
                        f"({endpoint_p99 / 1000:.2f}s). Consider targeted optimisation."
                    ),
                    metric="endpoint_p99_latency",
                    current_value=round(endpoint_p99, 1),
                    target_value=500,
                    effort=Effort.HIGH,
                    fix_hint=(
                        f"Profile the '{name}' endpoint specifically. Check for N+1 "
                        "queries, missing indexes, or heavy computation."
                    ),
                    raw=row,
                ))

        # --- Specific failure types ---
        if isinstance(failure_rows, list):
            for failure in failure_rows:
                if not isinstance(failure, dict):
                    continue
                error_msg = failure.get("Error", "Unknown error")
                method = failure.get("Method", "")
                name = failure.get("Name", "")
                occurrences = _safe_int(failure.get("Occurrences"))

                if occurrences and occurrences > 10:
                    findings.append(Finding(
                        tool="locust",
                        severity=Severity.HIGH,
                        category=Category.LOAD,
                        file="<url>",
                        rule_id="repeated-failure",
                        rule_name="Repeated Failure Pattern",
                        message=(
                            f"{method} {name}: '{error_msg}' occurred {occurrences} times."
                        ),
                        effort=Effort.MEDIUM,
                        fix_hint=(
                            f"Investigate the repeated failure at {method} {name}. "
                            "Check server logs for the root cause."
                        ),
                        raw=failure,
                    ))

        return findings


def _safe_float(value: str | float | None) -> float | None:
    """Safely convert a CSV cell to float."""
    if value is None or value == "" or value == "N/A":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: str | int | None) -> int | None:
    """Safely convert a CSV cell to int."""
    if value is None or value == "" or value == "N/A":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
