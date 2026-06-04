"""checkov runner — scan Terraform, CloudFormation, Docker, and k8s for misconfigurations."""

from __future__ import annotations

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.checkov import CheckovNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class CheckovRunner(AsyncToolRunner):
    name = "checkov"

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "checkov not installed"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        cmd = [self.bin_path, "-d", self.target, "--output", "json", "--quiet"]
        data, stderr = self._exec_json(cmd, timeout=self.config.timeout * 2)
        if data is None:
            # checkov returns exit code 1 when findings exist but still produces JSON
            # Try parsing stderr as well, or re-run with capture
            result = self._exec(cmd, timeout=self.config.timeout * 2)
            import json
            try:
                data = json.loads(result.stdout)
            except (json.JSONDecodeError, ValueError):
                return self._make_error_result(f"checkov failed: {stderr[:200] if stderr else 'no output'}")

        normaliser = CheckovNormaliser()
        findings = normaliser.normalise(data)
        status = ToolStatus.SUCCESS if not findings else ToolStatus.PARTIAL
        return ToolResult(tool=self.name, status=status, findings=findings)
