"""squawk runner — lint SQL migrations for unsafe operations."""

from __future__ import annotations

import json

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.squawk import SquawkNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class SquawkRunner(AsyncToolRunner):
    name = "squawk"

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "squawk not installed"
            return False
        # Check for migration directories or SQL files
        has_migrations = (
            self._file_exists("migrations", "db/migrate", "db/migrations", "supabase/migrations")
            or bool(self._scan_files("*.sql"))
        )
        if not has_migrations:
            self.skip_reason = "no migration files or SQL files found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        sql_files = self._scan_files(
            "migrations/**/*.sql",
            "db/migrate/**/*.sql",
            "db/migrations/**/*.sql",
            "supabase/migrations/**/*.sql",
            "*.sql",
        )
        if not sql_files:
            return ToolResult(tool=self.name, status=ToolStatus.SKIPPED)

        all_findings = []
        normaliser = SquawkNormaliser()
        errors = []

        for sql_file in sql_files:
            try:
                relative_path = sql_file.relative_to(self.target)
                cmd = [self.bin_path, "--reporter", "json", str(sql_file)]
                result = self._exec(cmd)

                output = result.stdout.strip()
                if output:
                    try:
                        data = json.loads(output)
                        # Inject file path into each violation if missing
                        if isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict) and "file" not in item:
                                    item["file"] = str(relative_path)
                        findings = normaliser.normalise(data)
                        all_findings.extend(findings)
                    except json.JSONDecodeError:
                        errors.append(f"Failed to parse squawk output for {relative_path}")

                # Also check stderr for additional warnings
                if result.stderr.strip() and result.returncode not in (0, 1):
                    errors.append(result.stderr.strip()[:200])

            except Exception as exc:
                errors.append(f"Error scanning {sql_file}: {str(exc)[:100]}")
                continue

        status = ToolStatus.SUCCESS
        if errors and not all_findings:
            status = ToolStatus.PARTIAL

        return ToolResult(
            tool=self.name,
            status=status,
            findings=all_findings,
            error="; ".join(errors) if errors else None,
        )
