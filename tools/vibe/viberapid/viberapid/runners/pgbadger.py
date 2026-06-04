"""Runner for pgbadger — PostgreSQL log analyser for slow query patterns."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.pgbadger import PgbadgerNormaliser
from viberapid.runners.base import AsyncToolRunner


class PgbadgerRunner(AsyncToolRunner):
    """Run pgbadger to analyse PostgreSQL log files for slow query patterns.

    Expects either:
    - tools.pgbadger.log_file in config pointing to a PostgreSQL log file
    - A PostgreSQL log file auto-detected in the project directory
    """

    name = "pgbadger"

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "pgbadger not installed"
            return False

        log_file = self._resolve_log_file()
        if not log_file:
            self.skip_reason = (
                "no PostgreSQL log file found — set tools.pgbadger.log_file in config"
            )
            return False

        return True

    def _resolve_log_file(self) -> str | None:
        """Find the PostgreSQL log file from config or auto-detection."""
        tc = self.tool_config
        explicit = tc.get("log_file")
        if explicit:
            path = Path(explicit)
            if not path.is_absolute():
                path = Path(self.target) / path
            if path.exists():
                return str(path)
            return None

        # Auto-detect common PostgreSQL log locations
        candidates = [
            "postgresql.log",
            "pg.log",
            "log/postgresql.log",
            "logs/postgresql.log",
        ]
        for candidate in candidates:
            path = Path(self.target) / candidate
            if path.exists():
                return str(path)

        return None

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        log_file = self._resolve_log_file()
        if not log_file:
            return self._make_error_result("no PostgreSQL log file found")

        tc = self.tool_config
        log_format = tc.get("log_format", "stderr")  # stderr, csv, syslog

        output_file = None

        try:
            with tempfile.NamedTemporaryFile(
                prefix="viberapid-pgbadger-",
                suffix=".json",
                delete=False,
            ) as of:
                output_file = of.name

            bin_path = self.bin_path
            cmd = [
                bin_path,
                "--format", log_format,
                "--outfile", output_file,
                "--json",
                log_file,
            ]

            # Add extra args from config
            extra_args = tc.get("extra_args", [])
            if isinstance(extra_args, list):
                cmd.extend(extra_args)

            result = self._exec(cmd)

            # Parse output
            output_path = Path(output_file)
            if not output_path.exists() or output_path.stat().st_size == 0:
                # pgbadger may output to stdout in some modes
                if result.stdout.strip():
                    try:
                        data = json.loads(result.stdout)
                    except json.JSONDecodeError:
                        return self._make_error_result(
                            f"pgbadger did not produce valid JSON output. "
                            f"stderr: {result.stderr[:500]}"
                        )
                else:
                    return self._make_error_result(
                        f"pgbadger did not produce output. "
                        f"exit code: {result.returncode}, "
                        f"stderr: {result.stderr[:500]}"
                    )
            else:
                with open(output_path) as f:
                    data = json.load(f)

            normaliser = PgbadgerNormaliser()
            findings = normaliser.normalise(data)

            # Extract summary metrics
            metrics: dict = {
                "log_file": log_file,
                "log_format": log_format,
            }
            if isinstance(data, dict):
                overall = data.get("overall_stat", {})
                if isinstance(overall, dict):
                    metrics["total_queries"] = overall.get("queries_number", 0)
                    metrics["total_duration_ms"] = overall.get("queries_duration", 0)
                    metrics["unique_queries"] = overall.get(
                        "unique_query", overall.get("unique_normalized_query", 0)
                    )

            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS,
                findings=findings,
                metrics=metrics,
            )

        except Exception as exc:
            return self._make_error_result(f"pgbadger failed: {exc}")

        finally:
            if output_file:
                Path(output_file).unlink(missing_ok=True)
