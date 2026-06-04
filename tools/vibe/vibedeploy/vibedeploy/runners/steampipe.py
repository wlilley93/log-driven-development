"""steampipe runner — cloud compliance checks via SQL."""

from __future__ import annotations

import json

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.steampipe import SteampipeNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class SteampipeRunner(AsyncToolRunner):
    name = "steampipe"
    requires_cloud = True

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "steampipe not installed"
            return False
        return super().should_run()

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        # Run steampipe check with JSON output
        # Default to AWS CIS benchmark if no specific mod is configured
        benchmark = self.tool_config.get("benchmark", "aws_compliance.benchmark.cis_v150")

        cmd = [
            self.bin_path,
            "check",
            benchmark,
            "--output", "json",
            "--progress=false",
        ]
        result = self._exec(cmd, timeout=self.config.timeout * 4)

        if result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                normaliser = SteampipeNormaliser()
                findings = normaliser.normalise(data)
                status = ToolStatus.SUCCESS if result.returncode == 0 else ToolStatus.PARTIAL
                return ToolResult(tool=self.name, status=status, findings=findings)
            except json.JSONDecodeError:
                pass

        if result.returncode != 0:
            return self._make_error_result(f"steampipe failed: {result.stderr[:200]}")

        return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=[])
