"""Runner for pghero — PostgreSQL performance diagnostics via direct SQL queries."""

from __future__ import annotations

import os

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.pghero import PgheroNormaliser
from viberapid.runners.base import AsyncToolRunner


class PgheroRunner(AsyncToolRunner):
    """Run PostgreSQL diagnostic queries to detect missing indexes, duplicates, bloat, and slow queries.

    Requires DATABASE_URL environment variable or tools.pghero.database_url in config.
    Uses psycopg2 for direct database access — no external binary needed.
    """

    name = "pghero"
    requires_python = True

    def should_run(self) -> bool:
        db_url = self._get_database_url()
        if not db_url:
            self.skip_reason = (
                "no DATABASE_URL env var or tools.pghero.database_url in config"
            )
            return False

        try:
            import psycopg2  # noqa: F401
        except ImportError:
            self.skip_reason = "psycopg2 not installed (pip install psycopg2-binary)"
            return False

        return True

    def _get_database_url(self) -> str | None:
        """Resolve the database URL from config or environment."""
        tc = self.tool_config
        url = tc.get("database_url")
        if url:
            return url
        return os.environ.get("DATABASE_URL")

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        import psycopg2

        db_url = self._get_database_url()
        if not db_url:
            return self._make_error_result("no DATABASE_URL available")

        try:
            conn = psycopg2.connect(db_url)
            conn.autocommit = True
            cur = conn.cursor()

            raw_data: dict = {}

            # --- Missing indexes (tables with seq scans but no index scans) ---
            cur.execute("""
                SELECT
                    schemaname,
                    relname AS table_name,
                    seq_scan,
                    seq_tup_read,
                    idx_scan,
                    n_live_tup AS estimated_rows
                FROM pg_stat_user_tables
                WHERE seq_scan > 0
                  AND (idx_scan IS NULL OR idx_scan = 0)
                  AND n_live_tup > 100
                ORDER BY seq_tup_read DESC
                LIMIT 50;
            """)
            columns = [desc[0] for desc in cur.description]
            raw_data["missing_indexes"] = [
                dict(zip(columns, row)) for row in cur.fetchall()
            ]

            # --- Unused indexes ---
            cur.execute("""
                SELECT
                    s.schemaname,
                    s.relname AS table_name,
                    s.indexrelname AS index_name,
                    s.idx_scan AS index_scans,
                    pg_relation_size(s.indexrelid) AS index_size_bytes
                FROM pg_stat_user_indexes s
                JOIN pg_index i ON s.indexrelid = i.indexrelid
                WHERE s.idx_scan = 0
                  AND NOT i.indisunique
                  AND NOT i.indisprimary
                  AND pg_relation_size(s.indexrelid) > 0
                ORDER BY pg_relation_size(s.indexrelid) DESC
                LIMIT 50;
            """)
            columns = [desc[0] for desc in cur.description]
            raw_data["unused_indexes"] = [
                dict(zip(columns, row)) for row in cur.fetchall()
            ]

            # --- Duplicate indexes ---
            cur.execute("""
                SELECT
                    pg_size_pretty(sum(pg_relation_size(idx))::bigint) AS total_size,
                    schemaname,
                    tablename,
                    array_agg(indexname) AS indexes,
                    array_agg(pg_get_indexdef(idx)) AS definitions
                FROM (
                    SELECT
                        n.nspname AS schemaname,
                        ct.relname AS tablename,
                        ci.relname AS indexname,
                        i.indexrelid AS idx,
                        (i.indrelid::text || E'\\n' || i.indclass::text || E'\\n'
                         || i.indkey::text || E'\\n'
                         || coalesce(pg_get_expr(i.indexprs, i.indrelid), '')
                         || E'\\n' || coalesce(pg_get_expr(i.indpred, i.indrelid), '')
                        ) AS index_key
                    FROM pg_index i
                    JOIN pg_class ct ON ct.oid = i.indrelid
                    JOIN pg_class ci ON ci.oid = i.indexrelid
                    JOIN pg_namespace n ON n.oid = ct.relnamespace
                    WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
                ) sub
                GROUP BY schemaname, tablename, index_key
                HAVING count(*) > 1
                ORDER BY sum(pg_relation_size(idx)) DESC
                LIMIT 20;
            """)
            columns = [desc[0] for desc in cur.description]
            raw_data["duplicate_indexes"] = [
                dict(zip(columns, row)) for row in cur.fetchall()
            ]

            # --- Table bloat ---
            cur.execute("""
                SELECT
                    schemaname,
                    relname AS table_name,
                    n_dead_tup,
                    n_live_tup,
                    CASE WHEN n_live_tup > 0
                         THEN round(100.0 * n_dead_tup / n_live_tup, 1)
                         ELSE 0
                    END AS dead_tuple_pct,
                    last_autovacuum,
                    last_autoanalyze
                FROM pg_stat_user_tables
                WHERE n_dead_tup > 1000
                  AND (n_live_tup > 0 AND (100.0 * n_dead_tup / n_live_tup) > 10)
                ORDER BY n_dead_tup DESC
                LIMIT 30;
            """)
            columns = [desc[0] for desc in cur.description]
            raw_data["bloated_tables"] = [
                dict(zip(columns, row)) for row in cur.fetchall()
            ]

            # --- Slow queries (from pg_stat_statements if available) ---
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'
                );
            """)
            has_pg_stat_statements = cur.fetchone()[0]

            if has_pg_stat_statements:
                cur.execute("""
                    SELECT
                        query,
                        calls,
                        round(total_exec_time::numeric, 2) AS total_time_ms,
                        round(mean_exec_time::numeric, 2) AS mean_time_ms,
                        round(max_exec_time::numeric, 2) AS max_time_ms,
                        rows
                    FROM pg_stat_statements
                    WHERE userid = (SELECT oid FROM pg_roles WHERE rolname = current_user)
                      AND calls > 5
                      AND mean_exec_time > 100
                    ORDER BY mean_exec_time DESC
                    LIMIT 20;
                """)
                columns = [desc[0] for desc in cur.description]
                raw_data["slow_queries"] = [
                    dict(zip(columns, row)) for row in cur.fetchall()
                ]
            else:
                raw_data["slow_queries"] = []

            # --- Table sizes ---
            cur.execute("""
                SELECT
                    schemaname,
                    relname AS table_name,
                    pg_total_relation_size(relid) AS total_size_bytes,
                    pg_table_size(relid) AS table_size_bytes,
                    pg_indexes_size(relid) AS indexes_size_bytes,
                    n_live_tup AS estimated_rows
                FROM pg_stat_user_tables
                ORDER BY pg_total_relation_size(relid) DESC
                LIMIT 20;
            """)
            columns = [desc[0] for desc in cur.description]
            raw_data["table_sizes"] = [
                dict(zip(columns, row)) for row in cur.fetchall()
            ]

            cur.close()
            conn.close()

            normaliser = PgheroNormaliser()
            findings = normaliser.normalise(raw_data)

            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS,
                findings=findings,
                metrics={
                    "missing_index_tables": len(raw_data["missing_indexes"]),
                    "unused_indexes": len(raw_data["unused_indexes"]),
                    "duplicate_index_groups": len(raw_data["duplicate_indexes"]),
                    "bloated_tables": len(raw_data["bloated_tables"]),
                    "slow_queries": len(raw_data["slow_queries"]),
                    "pg_stat_statements_available": has_pg_stat_statements,
                },
            )

        except psycopg2.Error as exc:
            return self._make_error_result(f"PostgreSQL connection error: {exc}")
        except Exception as exc:
            return self._make_error_result(f"pghero failed: {exc}")
