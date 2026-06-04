"""polaris runner — Kubernetes best practices and policy checking."""

from __future__ import annotations

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.polaris import PolarisNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class PolarisRunner(AsyncToolRunner):
    name = "polaris"
    requires_k8s = True

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "polaris not installed"
            return False
        return super().should_run()

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        cmd = [
            self.bin_path, "audit",
            "--audit-path", self.target,
            "--format", "json",
        ]
        data, stderr = self._exec_json(cmd, timeout=120)

        if data is None:
            return self._make_error_result(f"polaris audit failed: {stderr[:200]}")

        normaliser = PolarisNormaliser()
        findings = normaliser.normalise(data)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
        )
