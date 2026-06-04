"""detect-secrets runner — find secrets in source code."""

from __future__ import annotations
from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.normalisers.detect_secrets import DetectSecretsNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class DetectSecretsRunner(AsyncToolRunner):
    name = "detect_secrets"

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "detect-secrets not installed"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        cmd = [self.bin_path, "scan", "--all-files"]
        data, stderr = self._exec_json(cmd)
        if data is None:
            return self._make_error_result(f"detect-secrets failed: {stderr[:200]}")

        normaliser = DetectSecretsNormaliser()
        findings = normaliser.normalise(data)
        status = ToolStatus.SUCCESS if not stderr else ToolStatus.PARTIAL
        return ToolResult(tool=self.name, status=status, findings=findings)
