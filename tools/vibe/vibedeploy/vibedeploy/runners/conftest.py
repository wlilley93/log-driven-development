"""conftest runner — OPA/Rego policy testing for configuration files."""

from __future__ import annotations

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.conftest import ConftestNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class ConftestRunner(AsyncToolRunner):
    name = "conftest"

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "conftest not installed"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        cmd = [self.bin_path, "test", "--output", "json", self.target]
        data, stderr = self._exec_json(cmd)

        if data is None:
            # conftest exits non-zero when policy failures exist
            result = self._exec(cmd)
            import json
            try:
                data = json.loads(result.stdout)
            except (json.JSONDecodeError, ValueError):
                return self._make_error_result(f"conftest failed: {stderr[:200] if stderr else 'no output'}")

        normaliser = ConftestNormaliser()
        findings = normaliser.normalise(data)
        status = ToolStatus.SUCCESS if not findings else ToolStatus.PARTIAL
        return ToolResult(tool=self.name, status=status, findings=findings)
