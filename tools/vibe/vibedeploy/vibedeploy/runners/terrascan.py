"""terrascan runner — detect compliance and security violations in IaC."""

from __future__ import annotations

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.terrascan import TerrascanNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class TerrascanRunner(AsyncToolRunner):
    name = "terrascan"

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "terrascan not installed"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        cmd = [self.bin_path, "scan", "-d", self.target, "--output", "json"]
        data, stderr = self._exec_json(cmd)

        if data is None:
            # terrascan exits non-zero when violations found
            result = self._exec(cmd)
            import json
            try:
                data = json.loads(result.stdout)
            except (json.JSONDecodeError, ValueError):
                return self._make_error_result(f"terrascan failed: {stderr[:200] if stderr else 'no output'}")

        normaliser = TerrascanNormaliser()
        findings = normaliser.normalise(data)
        status = ToolStatus.SUCCESS if not findings else ToolStatus.PARTIAL
        return ToolResult(tool=self.name, status=status, findings=findings)
