"""Normaliser for pghero PostgreSQL diagnostic output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser


class PgheroNormaliser(BaseNormaliser):
    """Convert pghero diagnostic query results to Finding objects.

    Expected raw_data shape:
    {
      "missing_indexes": [
        {"schemaname": "public", "table_name": "orders", "seq_scan": 5000,
         "seq_tup_read": 1000000, "idx_scan": 0, "estimated_rows": 50000}
      ],
      "unused_indexes": [
        {"schemaname": "public", "table_name": "users", "index_name": "idx_users_old",
         "index_scans": 0, "index_size_bytes": 1048576}
      ],
      "duplicate_indexes": [
        {"total_size": "2 MB", "schemaname": "public", "tablename": "orders",
         "indexes": ["idx_a", "idx_b"], "definitions": ["...", "..."]}
      ],
      "bloated_tables": [
        {"schemaname": "public", "table_name": "logs", "n_dead_tup": 50000,
         "n_live_tup": 100000, "dead_tuple_pct": 50.0, ...}
      ],
      "slow_queries": [
        {"query": "SELECT ...", "calls": 1000, "total_time_ms": 50000,
         "mean_time_ms": 50, "max_time_ms": 2000, "rows": 500000}
      ]
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        findings: list[Finding] = []

        # --- Missing indexes ---
        for row in raw_data.get("missing_indexes", []):
            if not isinstance(row, dict):
                continue

            table = row.get("table_name", "<unknown>")
            schema = row.get("schemaname", "public")
            seq_scan = row.get("seq_scan", 0)
            seq_tup_read = row.get("seq_tup_read", 0)
            estimated_rows = row.get("estimated_rows", 0)

            severity = Severity.HIGH if seq_tup_read > 100000 else Severity.MEDIUM

            findings.append(Finding(
                tool="pghero",
                severity=severity,
                category=Category.DATABASE,
                file=f"{schema}.{table}",
                rule_id="pghero/missing-index",
                rule_name="Missing Index",
                message=(
                    f"Table '{schema}.{table}' has {seq_scan} sequential scans "
                    f"reading {seq_tup_read:,} tuples with no index scans. "
                    f"Estimated {estimated_rows:,} rows."
                ),
                metric="seq_tup_read",
                current_value=float(seq_tup_read),
                effort=Effort.MEDIUM,
                fix_hint=(
                    f"Add an index to '{schema}.{table}' on the columns used in "
                    "WHERE, JOIN, and ORDER BY clauses. Run EXPLAIN ANALYZE on "
                    "frequent queries to identify the best columns to index."
                ),
                saving_estimate=(
                    f"Adding an index could eliminate {seq_tup_read:,} sequential "
                    "tuple reads per scan"
                ),
                raw=row,
            ))

        # --- Unused indexes ---
        for row in raw_data.get("unused_indexes", []):
            if not isinstance(row, dict):
                continue

            table = row.get("table_name", "<unknown>")
            schema = row.get("schemaname", "public")
            index_name = row.get("index_name", "<unknown>")
            size_bytes = row.get("index_size_bytes", 0)
            size_mb = size_bytes / (1024 * 1024) if size_bytes else 0

            severity = Severity.MEDIUM if size_mb > 10 else Severity.LOW

            findings.append(Finding(
                tool="pghero",
                severity=severity,
                category=Category.DATABASE,
                file=f"{schema}.{table}",
                rule_id="pghero/unused-index",
                rule_name="Unused Index",
                message=(
                    f"Index '{index_name}' on '{schema}.{table}' has never been used "
                    f"and occupies {size_mb:.1f} MB."
                ),
                metric="index_size_mb",
                current_value=round(size_mb, 1),
                effort=Effort.LOW,
                fix_hint=(
                    f"Consider dropping index '{index_name}' with "
                    f"DROP INDEX {index_name}; to reclaim {size_mb:.1f} MB "
                    "and reduce write overhead."
                ),
                saving_estimate=f"Reclaim {size_mb:.1f} MB and reduce write overhead",
                raw=row,
            ))

        # --- Duplicate indexes ---
        for row in raw_data.get("duplicate_indexes", []):
            if not isinstance(row, dict):
                continue

            table = row.get("tablename", "<unknown>")
            schema = row.get("schemaname", "public")
            indexes = row.get("indexes", [])
            total_size = row.get("total_size", "unknown")

            findings.append(Finding(
                tool="pghero",
                severity=Severity.MEDIUM,
                category=Category.DATABASE,
                file=f"{schema}.{table}",
                rule_id="pghero/duplicate-index",
                rule_name="Duplicate Indexes",
                message=(
                    f"Table '{schema}.{table}' has duplicate indexes: "
                    f"{', '.join(indexes) if isinstance(indexes, list) else indexes}. "
                    f"Combined size: {total_size}."
                ),
                effort=Effort.LOW,
                fix_hint=(
                    "Drop the redundant indexes to save disk space and reduce write "
                    "overhead. Keep the most general index that covers query patterns."
                ),
                saving_estimate=f"Reclaim {total_size} of duplicate index space",
                raw=row,
            ))

        # --- Bloated tables ---
        for row in raw_data.get("bloated_tables", []):
            if not isinstance(row, dict):
                continue

            table = row.get("table_name", "<unknown>")
            schema = row.get("schemaname", "public")
            n_dead = row.get("n_dead_tup", 0)
            dead_pct = row.get("dead_tuple_pct", 0)

            if dead_pct > 50:
                severity = Severity.HIGH
            elif dead_pct > 20:
                severity = Severity.MEDIUM
            else:
                severity = Severity.LOW

            findings.append(Finding(
                tool="pghero",
                severity=severity,
                category=Category.DATABASE,
                file=f"{schema}.{table}",
                rule_id="pghero/table-bloat",
                rule_name="Table Bloat",
                message=(
                    f"Table '{schema}.{table}' has {n_dead:,} dead tuples "
                    f"({dead_pct:.1f}% bloat). Autovacuum may be falling behind."
                ),
                metric="dead_tuple_pct",
                current_value=float(dead_pct),
                target_value=10.0,
                effort=Effort.LOW,
                fix_hint=(
                    f"Run VACUUM ANALYZE {schema}.{table}; or tune autovacuum "
                    "settings (autovacuum_vacuum_scale_factor, "
                    "autovacuum_vacuum_threshold) for this table."
                ),
                saving_estimate=(
                    f"Vacuuming could reclaim space from {n_dead:,} dead tuples"
                ),
                raw=row,
            ))

        # --- Slow queries ---
        for row in raw_data.get("slow_queries", []):
            if not isinstance(row, dict):
                continue

            query = row.get("query", "<unknown>")
            mean_ms = row.get("mean_time_ms", 0)
            max_ms = row.get("max_time_ms", 0)
            calls = row.get("calls", 0)
            total_ms = row.get("total_time_ms", 0)

            # Truncate query for display
            query_display = query[:200] + "..." if len(query) > 200 else query

            if mean_ms > 1000:
                severity = Severity.HIGH
            elif mean_ms > 500:
                severity = Severity.MEDIUM
            else:
                severity = Severity.LOW

            findings.append(Finding(
                tool="pghero",
                severity=severity,
                category=Category.DATABASE,
                file="<database>",
                rule_id="pghero/slow-query",
                rule_name="Slow Query",
                message=(
                    f"Query averaging {mean_ms:.0f}ms (max {max_ms:.0f}ms) "
                    f"over {calls} calls, {total_ms:.0f}ms total: {query_display}"
                ),
                metric="mean_query_time_ms",
                current_value=float(mean_ms),
                target_value=100.0,
                effort=Effort.MEDIUM,
                fix_hint=(
                    "Run EXPLAIN ANALYZE on this query. Look for sequential scans, "
                    "missing indexes, or inefficient joins. Consider adding indexes "
                    "or rewriting the query."
                ),
                saving_estimate=(
                    f"Optimising could save ~{total_ms / 1000:.1f}s total across "
                    f"{calls} calls"
                ),
                raw=row,
            ))

        return findings
