"""ossf_scorecard runner — OSSF Scorecard for repository security analysis."""

from __future__ import annotations

import json

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.ossf_scorecard import OssfScorecardNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class OssfScorecardRunner(AsyncToolRunner):
    name = "ossf_scorecard"

    @property
    def bin_path(self) -> str:
        from vibedeploy.installer import get_tool_bin
        path = get_tool_bin(self.name)
        if path == self.name:
            return "scorecard"
        return path

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "scorecard not installed"
            return False
        if not self._file_exists(".git"):
            self.skip_reason = "not a git repository"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        cmd = [self.bin_path, "--format", "json", "--local", self.target]

        try:
            result = self._exec(cmd, timeout=self.config.timeout * 3)
        except Exception as e:
            return self._make_error_result(f"OSSF Scorecard execution failed: {e}")

        if result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                normaliser = OssfScorecardNormaliser()
                findings = normaliser.normalise(data)
                return ToolResult(
                    tool=self.name,
                    status=ToolStatus.SUCCESS,
                    findings=findings,
                )
            except json.JSONDecodeError:
                pass

        if result.returncode != 0:
            return self._make_error_result(
                f"scorecard exited with code {result.returncode}: {result.stderr[:300]}"
            )

        return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=[])
