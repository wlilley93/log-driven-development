"""grype runner — vulnerability scanning for container images and filesystems."""

from __future__ import annotations

import json

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.grype import GrypeNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class GrypeRunner(AsyncToolRunner):
    name = "grype"

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "grype not installed"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        cmd = [self.bin_path, f"dir:{self.target}", "-o", "json"]

        try:
            result = self._exec(cmd, timeout=self.config.timeout * 3)
        except Exception as e:
            return self._make_error_result(f"grype execution failed: {e}")

        if result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                normaliser = GrypeNormaliser()
                findings = normaliser.normalise(data)
                return ToolResult(
                    tool=self.name,
                    status=ToolStatus.SUCCESS,
                    findings=findings,
                )
            except json.JSONDecodeError:
                pass

        if result.returncode not in (0, 1):
            return self._make_error_result(
                f"grype exited with code {result.returncode}: {result.stderr[:300]}"
            )

        return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=[])
