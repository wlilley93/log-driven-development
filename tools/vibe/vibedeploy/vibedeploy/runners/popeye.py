"""popeye runner — Kubernetes cluster resource sanitizer."""

from __future__ import annotations

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.popeye import PopeyeNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class PopeyeRunner(AsyncToolRunner):
    name = "popeye"
    requires_k8s = True

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "popeye not installed"
            return False
        return super().should_run()

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        cmd = [self.bin_path, "--out", "json"]
        data, stderr = self._exec_json(cmd, timeout=120)

        if data is None:
            return self._make_error_result(f"popeye failed: {stderr[:200]}")

        normaliser = PopeyeNormaliser()
        findings = normaliser.normalise(data)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
        )
