"""tfsec runner — static analysis for Terraform code."""

from __future__ import annotations

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.tfsec import TfsecNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class TfsecRunner(AsyncToolRunner):
    name = "tfsec"

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "tfsec not installed"
            return False
        if not self._scan_files("*.tf"):
            self.skip_reason = "no Terraform files (*.tf) found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        cmd = [self.bin_path, "--format", "json", self.target]
        data, stderr = self._exec_json(cmd)

        if data is None:
            # tfsec exits non-zero when findings exist; retry raw parse
            result = self._exec(cmd)
            import json
            try:
                data = json.loads(result.stdout)
            except (json.JSONDecodeError, ValueError):
                return self._make_error_result(f"tfsec failed: {stderr[:200] if stderr else 'no output'}")

        normaliser = TfsecNormaliser()
        findings = normaliser.normalise(data)
        status = ToolStatus.SUCCESS if not findings else ToolStatus.PARTIAL
        return ToolResult(tool=self.name, status=status, findings=findings)
