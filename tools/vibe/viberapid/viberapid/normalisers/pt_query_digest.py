"""Normaliser for pt-query-digest (Percona Toolkit) output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser


class PtQueryDigestNormaliser(BaseNormaliser):
    """Convert pt-query-digest parsed report data to Finding objects.

    Expected raw_data shape:
    {
      "slow_log": "/path/to/slow-query.log",
      "total_queries": 500,
      "queries": [
        {
          "rank": 1,
          "query_id": "0xABC123...",
          "total_time_s": 100.0,
          "pct_total": 50.0,
          "calls": 500,
          "avg_time_s": 0.2,
          "variance_to_mean": 0.01,
          "item": "SELECT orders",
          "sample_query": "SELECT * FROM orders WHERE ...",
          "min_time_s": 0.01,
          "max_time_s": 5.0,
          "p95_time_s": 0.8,
          "rows_examined_min": 100,
          "rows_examined_max": 500000,
          "qps": 1.5
        }
      ]
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        findings: list[Finding] = []
        queries = raw_data.get("queries", [])

        if not isinstance(queries, list):
            return []

        for query in queries:
            if not isinstance(query, dict):
                continue

            total_time_s = query.get("total_time_s", 0)
            avg_time_s = query.get("avg_time_s", 0)
            calls = query.get("calls", 0)
            pct_total = query.get("pct_total", 0)
            item = query.get("item", "<unknown>")
            sample_query = query.get("sample_query", "")
            max_time_s = query.get("max_time_s", 0)
            p95_time_s = query.get("p95_time_s", 0)
            rows_max = query.get("rows_examined_max", 0)

            # Classify severity based on average query time and total impact
            if avg_time_s > 5.0:
                severity = Severity.CRITICAL
            elif avg_time_s > 1.0:
                severity = Severity.HIGH
            elif avg_time_s > 0.5 or pct_total > 20:
                severity = Severity.MEDIUM
            elif avg_time_s > 0.1:
                severity = Severity.LOW
            else:
                continue  # Skip queries under 100ms avg

            # Build message
            query_display = (
                sample_query[:200] + "..."
                if sample_query and len(sample_query) > 200
                else sample_query or item
            )

            findings.append(Finding(
                tool="pt_query_digest",
                severity=severity,
                category=Category.DATABASE,
                file=raw_data.get("slow_log", "<slow-query.log>"),
                rule_id="pt-query-digest/slow-query",
                rule_name="Slow MySQL Query",
                message=(
                    f"{item}: avg {avg_time_s:.3f}s, max {max_time_s:.3f}s, "
                    f"{calls} calls ({pct_total:.1f}% of total time). "
                    f"Query: {query_display}"
                ),
                metric="avg_query_time_s",
                current_value=round(avg_time_s, 3),
                target_value=0.1,
                effort=_classify_effort(avg_time_s, rows_max),
                fix_hint=_build_fix_hint(avg_time_s, rows_max, item),
                saving_estimate=(
                    f"Optimising could save ~{total_time_s:.1f}s total "
                    f"across {calls} calls"
                ),
                raw=query,
            ))

            # --- High variance detection ---
            variance = query.get("variance_to_mean", 0)
            if variance > 2.0 and calls > 10:
                findings.append(Finding(
                    tool="pt_query_digest",
                    severity=Severity.MEDIUM,
                    category=Category.DATABASE,
                    file=raw_data.get("slow_log", "<slow-query.log>"),
                    rule_id="pt-query-digest/high-variance",
                    rule_name="High Query Time Variance",
                    message=(
                        f"{item}: variance-to-mean ratio is {variance:.2f} "
                        f"(avg {avg_time_s:.3f}s, max {max_time_s:.3f}s, "
                        f"p95 {p95_time_s:.3f}s). Performance is unpredictable."
                    ),
                    effort=Effort.MEDIUM,
                    fix_hint=(
                        "High variance indicates intermittent slowness. Check for "
                        "lock contention, table-level locks, replication lag, "
                        "or query plan instability (force index hints if needed)."
                    ),
                    raw=query,
                ))

            # --- Full table scan detection ---
            if rows_max > 100000 and avg_time_s > 0.5:
                findings.append(Finding(
                    tool="pt_query_digest",
                    severity=Severity.HIGH,
                    category=Category.DATABASE,
                    file=raw_data.get("slow_log", "<slow-query.log>"),
                    rule_id="pt-query-digest/full-scan",
                    rule_name="Possible Full Table Scan",
                    message=(
                        f"{item}: examines up to {rows_max:,} rows. "
                        "This likely indicates a missing index or full table scan."
                    ),
                    metric="rows_examined_max",
                    current_value=float(rows_max),
                    effort=Effort.MEDIUM,
                    fix_hint=(
                        "Run EXPLAIN on this query to confirm a full table scan. "
                        "Add an appropriate index on the columns in the WHERE, JOIN, "
                        "and ORDER BY clauses."
                    ),
                    saving_estimate=(
                        f"Adding an index could reduce rows examined from "
                        f"{rows_max:,} to a fraction"
                    ),
                    raw=query,
                ))

        return findings


def _classify_effort(avg_time_s: float, rows_max: int) -> Effort:
    """Classify the effort required to optimise this query."""
    if avg_time_s > 5.0 or rows_max > 1000000:
        return Effort.HIGH
    if avg_time_s > 1.0 or rows_max > 100000:
        return Effort.MEDIUM
    return Effort.LOW


def _build_fix_hint(avg_time_s: float, rows_max: int, item: str) -> str:
    """Build a targeted fix hint based on query characteristics."""
    if rows_max > 100000:
        return (
            f"Query '{item}' examines many rows ({rows_max:,}). "
            "Add indexes on columns used in WHERE, JOIN, and ORDER BY clauses. "
            "Use EXPLAIN to confirm index usage."
        )
    if avg_time_s > 5.0:
        return (
            f"Query '{item}' is critically slow ({avg_time_s:.3f}s avg). "
            "Consider query rewriting, denormalisation, caching with Redis/Memcached, "
            "or moving to a read replica."
        )
    if avg_time_s > 1.0:
        return (
            f"Query '{item}' averages {avg_time_s:.3f}s. "
            "Check for missing indexes, unnecessary JOINs, SELECT * usage, "
            "or subqueries that could be converted to JOINs."
        )
    return (
        f"Query '{item}' averages {avg_time_s:.3f}s. "
        "Review the query plan with EXPLAIN and look for optimisation opportunities."
    )
