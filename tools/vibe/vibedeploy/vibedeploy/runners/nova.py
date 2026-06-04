"""nova runner — Helm chart version checking for outdated releases."""

from __future__ import annotations

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.nova import NovaNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class NovaRunner(AsyncToolRunner):
    name = "nova"
    requires_k8s = True

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "nova not installed"
            return False
        return super().should_run()

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        cmd = [self.bin_path, "find", "--format", "json"]
        data, stderr = self._exec_json(cmd, timeout=120)

        if data is None:
            return self._make_error_result(f"nova failed: {stderr[:200]}")

        normaliser = NovaNormaliser()
        findings = normaliser.normalise(data)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
        )
