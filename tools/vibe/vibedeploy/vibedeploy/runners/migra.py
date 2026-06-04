"""migra runner — detect unsafe schema changes via schema diff."""

from __future__ import annotations

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.migra import MigraNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class MigraRunner(AsyncToolRunner):
    name = "migra"

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "migra not installed (pip install migra)"
            return False
        # migra needs database connection strings or schema files to diff;
        # check if config provides them or if there are SQL schema files
        tool_cfg = self.tool_config
        has_source = tool_cfg.get("source_url") or tool_cfg.get("source_schema")
        has_target = tool_cfg.get("target_url") or tool_cfg.get("target_schema")
        has_schemas = bool(self._scan_files("schema.sql", "*.schema.sql", "schema/*.sql"))
        if not (has_source and has_target) and not has_schemas:
            self.skip_reason = "migra requires source/target database URLs or schema files in config"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        tool_cfg = self.tool_config
        source = tool_cfg.get("source_url")
        target = tool_cfg.get("target_url")

        if not source or not target:
            # Fall back to schema file diffing if available
            schema_files = self._scan_files("schema.sql", "*.schema.sql")
            if len(schema_files) >= 2:
                source = str(schema_files[0])
                target = str(schema_files[1])
            else:
                return ToolResult(
                    tool=self.name,
                    status=ToolStatus.SKIPPED,
                    error="migra requires two database URLs or schema files to diff",
                )

        # Build migra command
        cmd = [self.bin_path, "--unsafe"]
        if tool_cfg.get("schema"):
            cmd.extend(["--schema", tool_cfg.get("schema")])
        cmd.extend([source, target])

        try:
            result = self._exec(cmd, timeout=self.config.timeout)
        except Exception as exc:
            return self._make_error_result(f"migra execution failed: {str(exc)[:200]}")

        normaliser = MigraNormaliser()

        # migra returns 0 if schemas match, 2 if they differ, 1 on error
        if result.returncode == 0 and not result.stdout.strip():
            return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=[])

        if result.returncode == 1:
            return self._make_error_result(
                f"migra error: {result.stderr.strip()[:200] or result.stdout.strip()[:200]}"
            )

        # Parse diff output (returncode == 2 means schemas differ)
        findings = normaliser.normalise({
            "output": result.stdout,
            "file": "schema-diff",
        })

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            error=result.stderr.strip()[:200] if result.stderr.strip() else None,
        )
