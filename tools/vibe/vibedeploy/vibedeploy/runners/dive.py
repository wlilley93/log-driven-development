"""dive runner — analyze Docker image layers for wasted space."""

from __future__ import annotations

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.dive import DiveNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class DiveRunner(AsyncToolRunner):
    name = "dive"
    requires_docker = True

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "dive not installed"
            return False
        if not self._file_exists("Dockerfile", "docker-compose.yml", "docker-compose.yaml"):
            self.skip_reason = "no Dockerfile or docker-compose found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        # Determine image name from tool config or infer from target directory
        image_name = None
        tool_cfg = self.tool_config or {}
        if isinstance(tool_cfg, dict):
            image_name = tool_cfg.get("image")

        if not image_name:
            from pathlib import Path
            image_name = Path(self.target).name.lower()

        cmd = [self.bin_path, image_name, "--ci", "--json", "/dev/stdout"]

        try:
            data, stderr = self._exec_json(cmd, timeout=self.config.timeout * 2)
        except Exception as exc:
            return self._make_error_result(f"dive execution failed: {exc}")

        if data is None:
            return self._make_error_result(f"dive produced no JSON output: {stderr[:200]}")

        normaliser = DiveNormaliser()
        findings = normaliser.normalise(data)

        # dive exits 1 when CI checks fail (findings), which is expected
        status = ToolStatus.SUCCESS
        return ToolResult(tool=self.name, status=status, findings=findings)
