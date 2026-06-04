"""atlas runner — schema inspection and migration linting."""

from __future__ import annotations

import json

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.atlas import AtlasNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class AtlasRunner(AsyncToolRunner):
    name = "atlas"

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "atlas not installed"
            return False
        # Atlas needs either migration files or a config (atlas.hcl)
        has_config = self._file_exists("atlas.hcl", "atlas.yaml", "atlas.yml")
        has_migrations = self._file_exists("migrations", "db/migrations")
        has_sql = bool(self._scan_files("*.sql"))
        if not (has_config or has_migrations or has_sql):
            self.skip_reason = "no atlas.hcl config or migration files found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        tool_cfg = self.tool_config

        # Prefer atlas migrate lint if migration directory exists
        migration_dir = tool_cfg.get("migration_dir")
        if not migration_dir:
            for candidate in ("migrations", "db/migrations"):
                if self._file_exists(candidate):
                    migration_dir = candidate
                    break

        if migration_dir:
            return self._run_migrate_lint(migration_dir, tool_cfg)
        else:
            return self._run_schema_inspect(tool_cfg)

    def _run_migrate_lint(self, migration_dir: str, tool_cfg) -> ToolResult:
        """Run atlas migrate lint on a migration directory."""
        cmd = [self.bin_path, "migrate", "lint", "--format", "{{ json . }}"]

        # Add migration directory
        cmd.extend(["--dir", f"file://{migration_dir}"])

        # Add dev URL if configured (required for lint)
        dev_url = tool_cfg.get("dev_url", tool_cfg.get("dev_database_url"))
        if dev_url:
            cmd.extend(["--dev-url", dev_url])
        else:
            # Without dev URL, atlas lint may not work fully
            cmd.extend(["--dev-url", "sqlite://dev?mode=memory"])

        # Add latest N migrations to lint
        latest = tool_cfg.get("latest", "1")
        cmd.extend(["--latest", str(latest)])

        try:
            result = self._exec(cmd, timeout=self.config.timeout)
        except Exception as exc:
            return self._make_error_result(f"atlas migrate lint failed: {str(exc)[:200]}")

        output = result.stdout.strip()
        if not output:
            if result.returncode != 0:
                return self._make_error_result(
                    f"atlas error: {result.stderr.strip()[:200]}"
                )
            return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=[])

        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            return self._make_error_result(
                f"Failed to parse atlas JSON: {output[:200]}"
            )

        normaliser = AtlasNormaliser()
        findings = normaliser.normalise(data)

        status = ToolStatus.SUCCESS if result.returncode == 0 else ToolStatus.PARTIAL

        return ToolResult(
            tool=self.name,
            status=status,
            findings=findings,
            error=result.stderr.strip()[:200] if result.stderr.strip() else None,
        )

    def _run_schema_inspect(self, tool_cfg) -> ToolResult:
        """Run atlas schema inspect for schema analysis."""
        cmd = [self.bin_path, "schema", "inspect", "--format", "{{ json . }}"]

        # Add database URL
        db_url = tool_cfg.get("url", tool_cfg.get("database_url"))
        if db_url:
            cmd.extend(["--url", db_url])
        else:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.SKIPPED,
                error="atlas schema inspect requires a database URL in config",
            )

        try:
            result = self._exec(cmd, timeout=self.config.timeout)
        except Exception as exc:
            return self._make_error_result(f"atlas schema inspect failed: {str(exc)[:200]}")

        if result.returncode != 0:
            return self._make_error_result(
                f"atlas schema inspect error: {result.stderr.strip()[:200]}"
            )

        # Schema inspect output is informational — no violations unless we
        # perform further analysis. Return success with no findings.
        return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=[])
