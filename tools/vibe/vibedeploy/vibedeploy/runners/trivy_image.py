"""trivy_image runner — scan Docker images for vulnerabilities."""

from __future__ import annotations

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.trivy_image import TrivyImageNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class TrivyImageRunner(AsyncToolRunner):
    name = "trivy_image"
    requires_docker = True

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "trivy not installed"
            return False
        if not self._file_exists("Dockerfile", "docker-compose.yml", "docker-compose.yaml"):
            self.skip_reason = "no Dockerfile found"
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

        cmd = [
            self.bin_path, "image",
            "--format", "json",
            "--severity", "CRITICAL,HIGH,MEDIUM,LOW",
            "--no-progress",
            image_name,
        ]

        try:
            data, stderr = self._exec_json(cmd, timeout=self.config.timeout * 3)
        except Exception as exc:
            return self._make_error_result(f"trivy execution failed: {exc}")

        if data is None:
            # trivy may write warnings to stderr but still produce no JSON if the image is not found
            return self._make_error_result(f"trivy produced no JSON output: {stderr[:300]}")

        normaliser = TrivyImageNormaliser()
        findings = normaliser.normalise(data)

        status = ToolStatus.SUCCESS
        return ToolResult(tool=self.name, status=status, findings=findings)
