"""sqlfluff runner — lint SQL files for style and correctness."""

from __future__ import annotations

import json

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.sqlfluff import SqlfluffNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class SqlfluffRunner(AsyncToolRunner):
    name = "sqlfluff"

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "sqlfluff not installed (pip install sqlfluff)"
            return False
        if not self._scan_files("*.sql"):
            self.skip_reason = "no SQL files found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        sql_files = self._scan_files("*.sql")
        if not sql_files:
            return ToolResult(tool=self.name, status=ToolStatus.SKIPPED)

        # Build command — lint all SQL files with JSON output
        cmd = [self.bin_path, "lint", "--format", "json"]

        # Add dialect from config if specified
        tool_cfg = self.tool_config
        dialect = tool_cfg.get("dialect")
        if dialect:
            cmd.extend(["--dialect", dialect])

        # Add config file if exists
        for config_name in (".sqlfluff", "setup.cfg", "pyproject.toml"):
            if self._file_exists(config_name):
                break
        else:
            # No config file — set a reasonable default dialect
            if not dialect:
                cmd.extend(["--dialect", "ansi"])

        # Add file paths (limit to avoid command-line length issues)
        file_paths = [str(f) for f in sql_files[:100]]
        cmd.extend(file_paths)

        try:
            result = self._exec(cmd, timeout=self.config.timeout)
        except Exception as exc:
            return self._make_error_result(f"sqlfluff execution failed: {str(exc)[:200]}")

        # sqlfluff lint returns 0 if clean, 1 if violations found, 2+ on errors
        output = result.stdout.strip()
        if not output:
            if result.returncode >= 2:
                return self._make_error_result(
                    f"sqlfluff error: {result.stderr.strip()[:200]}"
                )
            return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=[])

        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            return self._make_error_result(
                f"Failed to parse sqlfluff JSON output: {output[:200]}"
            )

        normaliser = SqlfluffNormaliser()
        findings = normaliser.normalise(data)

        status = ToolStatus.SUCCESS if result.returncode in (0, 1) else ToolStatus.PARTIAL

        return ToolResult(
            tool=self.name,
            status=status,
            findings=findings,
            error=result.stderr.strip()[:200] if result.stderr.strip() else None,
        )
