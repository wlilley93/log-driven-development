"""chamber runner — check for AWS Parameter Store secrets management."""

from __future__ import annotations
from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner


class ChamberRunner(AsyncToolRunner):
    name = "chamber"
    requires_cloud = True

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "chamber not installed"
            return False
        return super().should_run()

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        # chamber is a secrets management tool — check if it's configured
        result = self._exec([self.bin_path, "list-services"], timeout=30)
        if result.returncode != 0:
            return ToolResult(tool=self.name, status=ToolStatus.SKIPPED)
        return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=[])
