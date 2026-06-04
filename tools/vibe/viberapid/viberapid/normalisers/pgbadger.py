"""Normaliser for pgbadger PostgreSQL log analysis output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser


class PgbadgerNormaliser(BaseNormaliser):
    """Convert pgbadger JSON output to Finding objects.

    pgbadger JSON output varies by version but generally includes:
    {
      "overall_stat": {
        "queries_number": 150000,
        "queries_duration": 85000,
        "unique_query": 200,
        "errors_number": 50
      },
      "normalised_info": {
        "SELECT ... FROM orders WHERE ...": {
          "count": 5000,
          "duration": 25000,
          "min_duration": 1.2,
          "max_duration": 3500.0,
          "mean_duration": 5.0,
          "samples": [...]
        }
      },
      "slowest_queries": [
        {
          "query": "SELECT ...",
          "duration": 3500.0,
          "db": "mydb",
          "user": "appuser",
          "date": "2024-01-15 10:30:00"
        }
      ],
      "most_frequent_queries": {
        "SELECT ... FROM users WHERE ...": {
          "count": 50000,
          "duration": 10000
        }
      },
      "error_info": {
        "ERROR: relation \"foo\" does not exist": {
          "count": 25
        }
      }
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        findings: list[Finding] = []

        # --- Slowest queries ---
        slowest = raw_data.get("slowest_queries", [])
        if isinstance(slowest, list):
            for entry in slowest:
                if not isinstance(entry, dict):
                    continue

                query = entry.get("query", "<unknown>")
                duration_ms = _safe_float(entry.get("duration"))
                db = entry.get("db", "")

                if duration_ms is None or duration_ms < 100:
                    continue

                query_display = query[:200] + "..." if len(query) > 200 else query

                if duration_ms > 5000:
                    severity = Severity.CRITICAL
                elif duration_ms > 1000:
                    severity = Severity.HIGH
                elif duration_ms > 500:
                    severity = Severity.MEDIUM
                else:
                    severity = Severity.LOW

                findings.append(Finding(
                    tool="pgbadger",
                    severity=severity,
                    category=Category.DATABASE,
                    file=f"<database:{db}>" if db else "<database>",
                    rule_id="pgbadger/slow-query",
                    rule_name="Slow Query Detected",
                    message=(
                        f"Query took {duration_ms:.0f}ms: {query_display}"
                    ),
                    metric="query_duration_ms",
                    current_value=round(duration_ms, 1),
                    target_value=100.0,
                    effort=Effort.MEDIUM,
                    fix_hint=(
                        "Run EXPLAIN ANALYZE on this query. Look for sequential scans, "
                        "missing indexes, or large sort operations. Consider adding "
                        "indexes or restructuring the query."
                    ),
                    raw=entry,
                ))

        # --- Normalised query hotspots (high total time) ---
        normalised = raw_data.get("normalised_info", {})
        if isinstance(normalised, dict):
            for query_pattern, stats in normalised.items():
                if not isinstance(stats, dict):
                    continue

                count = _safe_int(stats.get("count"))
                total_duration = _safe_float(stats.get("duration"))
                mean_duration = _safe_float(stats.get("mean_duration"))
                max_duration = _safe_float(stats.get("max_duration"))

                if total_duration is None or total_duration < 1000:
                    continue

                query_display = (
                    query_pattern[:200] + "..."
                    if len(query_pattern) > 200
                    else query_pattern
                )

                if mean_duration and mean_duration > 500:
                    severity = Severity.HIGH
                elif total_duration > 30000:
                    severity = Severity.HIGH
                elif total_duration > 10000:
                    severity = Severity.MEDIUM
                else:
                    severity = Severity.LOW

                findings.append(Finding(
                    tool="pgbadger",
                    severity=severity,
                    category=Category.DATABASE,
                    file="<database>",
                    rule_id="pgbadger/query-hotspot",
                    rule_name="Query Hotspot",
                    message=(
                        f"Query pattern called {count} times, "
                        f"total {total_duration:.0f}ms "
                        f"(mean {mean_duration:.1f}ms, max {max_duration:.0f}ms): "
                        f"{query_display}"
                    ),
                    metric="total_query_time_ms",
                    current_value=round(total_duration, 1),
                    effort=Effort.MEDIUM,
                    fix_hint=(
                        "This query pattern is a significant time consumer. "
                        "Consider caching results, adding indexes, or batching "
                        "multiple calls into fewer queries."
                    ),
                    saving_estimate=(
                        f"Optimising could save ~{total_duration / 1000:.1f}s "
                        f"total across {count} calls"
                    ),
                    raw={"query": query_pattern, **stats},
                ))

        # --- Most frequent queries (N+1 detection) ---
        frequent = raw_data.get("most_frequent_queries", {})
        if isinstance(frequent, dict):
            for query_pattern, stats in frequent.items():
                if not isinstance(stats, dict):
                    continue

                count = _safe_int(stats.get("count"))
                if count is None or count < 1000:
                    continue

                # Skip if already covered by normalised_info
                query_display = (
                    query_pattern[:200] + "..."
                    if len(query_pattern) > 200
                    else query_pattern
                )

                if count > 10000:
                    severity = Severity.HIGH
                elif count > 5000:
                    severity = Severity.MEDIUM
                else:
                    severity = Severity.LOW

                findings.append(Finding(
                    tool="pgbadger",
                    severity=severity,
                    category=Category.DATABASE,
                    file="<database>",
                    rule_id="pgbadger/high-frequency-query",
                    rule_name="High-Frequency Query (Possible N+1)",
                    message=(
                        f"Query pattern executed {count:,} times. "
                        f"May indicate an N+1 query problem: {query_display}"
                    ),
                    metric="query_call_count",
                    current_value=float(count),
                    effort=Effort.MEDIUM,
                    fix_hint=(
                        "Investigate whether this query is being called in a loop. "
                        "Consider using JOINs, batch queries, eager loading, "
                        "or application-level caching."
                    ),
                    raw={"query": query_pattern, **stats},
                ))

        # --- Database errors ---
        errors = raw_data.get("error_info", {})
        if isinstance(errors, dict):
            for error_msg, stats in errors.items():
                if not isinstance(stats, dict):
                    continue

                count = _safe_int(stats.get("count"))
                if count is None or count < 5:
                    continue

                severity = Severity.HIGH if count > 100 else Severity.MEDIUM

                findings.append(Finding(
                    tool="pgbadger",
                    severity=severity,
                    category=Category.DATABASE,
                    file="<database>",
                    rule_id="pgbadger/repeated-error",
                    rule_name="Repeated Database Error",
                    message=(
                        f"Error occurred {count} times: "
                        f"{error_msg[:200]}{'...' if len(error_msg) > 200 else ''}"
                    ),
                    effort=Effort.MEDIUM,
                    fix_hint=(
                        "Investigate the root cause of this recurring error. "
                        "Check for missing tables/columns, permission issues, "
                        "or connection problems."
                    ),
                    raw={"error": error_msg, **stats},
                ))

        return findings


def _safe_float(value: Any) -> float | None:
    """Safely convert a value to float."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    """Safely convert a value to int."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
