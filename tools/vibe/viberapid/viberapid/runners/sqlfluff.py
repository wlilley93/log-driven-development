"""Runner for sqlfluff — lints SQL files for anti-patterns and style issues."""

from __future__ import annotations

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.sqlfluff import SqlfluffNormaliser
from viberapid.runners.base import AsyncToolRunner


class SqlfluffRunner(AsyncToolRunner):
    """Run sqlfluff to lint SQL files for anti-patterns and style violations."""

    name = "sqlfluff"
    requires_python = True

    def should_run(self) -> bool:
        sql_files = self._glob_files("*.sql")
        if not sql_files:
            self.skip_reason = "no .sql files found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        bin_path = self.bin_path
        target = self.target

        # Determine which files to lint
        sql_files = self._glob_files("*.sql")
        if not sql_files:
            return self._make_error_result("no .sql files found")

        # Build command — lint all SQL files under the target directory
        cmd = [bin_path, "lint", "--format", "json", target]

        data, stderr = self._exec_json(cmd)

        # sqlfluff exits non-zero when there are lint violations, which is expected.
        # Only treat as error if there is no parseable output at all.
        if data is None:
            # Try running without JSON to see if the tool itself failed
            return self._make_error_result(
                f"sqlfluff failed to produce JSON output. stderr: {stderr[:500]}"
            )

        normaliser = SqlfluffNormaliser()
        findings = normaliser.normalise(data)

        violation_count = 0
        file_count = 0
        if isinstance(data, list):
            file_count = len(data)
            for file_entry in data:
                for violation in file_entry.get("violations", []):
                    violation_count += 1

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "files_scanned": file_count,
                "total_violations": violation_count,
                "sql_files_in_project": len(sql_files),
            },
        )
