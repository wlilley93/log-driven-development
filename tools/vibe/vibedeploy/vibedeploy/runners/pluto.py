"""pluto runner — detect deprecated and removed Kubernetes API versions."""

from __future__ import annotations

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.pluto import PlutoNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class PlutoRunner(AsyncToolRunner):
    name = "pluto"
    requires_k8s = True

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "pluto not installed"
            return False
        k8s_files = self._scan_files("*.yaml", "*.yml")
        if not k8s_files:
            self.skip_reason = "no Kubernetes YAML files found"
            return False
        return super().should_run()

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        cmd = [
            self.bin_path, "detect-files",
            "-d", self.target,
            "-o", "json",
        ]
        data, stderr = self._exec_json(cmd, timeout=60)

        if data is None:
            # pluto may exit non-zero when deprecated APIs found but still output JSON
            result = self._exec(cmd, timeout=60)
            if result.stdout.strip():
                import json
                try:
                    data = json.loads(result.stdout)
                except json.JSONDecodeError:
                    return self._make_error_result(f"pluto failed: {stderr[:200]}")

        if data is None:
            return self._make_error_result(f"pluto failed: {stderr[:200]}")

        normaliser = PlutoNormaliser()
        # pluto returns { "items": [...] } or a list directly
        findings = normaliser.normalise(data)

        status = ToolStatus.SUCCESS
        return ToolResult(
            tool=self.name,
            status=status,
            findings=findings,
        )
