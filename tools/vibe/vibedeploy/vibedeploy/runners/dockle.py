"""dockle runner — Docker image best practice linter."""

from __future__ import annotations

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.dockle import DockleNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class DockleRunner(AsyncToolRunner):
    name = "dockle"
    requires_docker = True

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "dockle not installed"
            return False
        if not self._file_exists("Dockerfile", "docker-compose.yml", "docker-compose.yaml"):
            self.skip_reason = "no Dockerfile or docker-compose found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        # Determine image name from tool config or use a default based on target directory
        image_name = None
        tool_cfg = self.tool_config or {}
        if isinstance(tool_cfg, dict):
            image_name = tool_cfg.get("image")

        if not image_name:
            # Try to infer image name from the target directory name
            from pathlib import Path
            image_name = Path(self.target).name.lower()

        cmd = [self.bin_path, "--format", "json", image_name]
        try:
            data, stderr = self._exec_json(cmd)
        except Exception as exc:
            return self._make_error_result(f"dockle execution failed: {exc}")

        if data is None:
            return self._make_error_result(f"dockle produced no JSON output: {stderr[:200]}")

        normaliser = DockleNormaliser()
        findings = normaliser.normalise(data)

        status = ToolStatus.SUCCESS if not stderr else ToolStatus.PARTIAL
        return ToolResult(tool=self.name, status=status, findings=findings)
