"""kubeval runner — validate Kubernetes manifests against API schemas."""

from __future__ import annotations

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.kubeval import KubevalNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class KubevalRunner(AsyncToolRunner):
    name = "kubeval"
    requires_k8s = True

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "kubeval not installed"
            return False
        return super().should_run()

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        yaml_files = self._scan_files("*.yaml", "*.yml")
        if not yaml_files:
            return ToolResult(tool=self.name, status=ToolStatus.SKIPPED)

        file_args = [str(f) for f in yaml_files]
        cmd = [self.bin_path, "--output", "json"] + file_args
        data, stderr = self._exec_json(cmd)

        if data is None:
            # kubeval may output NDJSON (one object per line)
            result = self._exec(cmd)
            if result.stdout.strip():
                import json
                lines = result.stdout.strip().split("\n")
                all_results = []
                for line in lines:
                    try:
                        all_results.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
                if all_results:
                    data = all_results

        if data is None:
            return self._make_error_result(f"kubeval failed: {stderr[:200]}")

        normaliser = KubevalNormaliser()
        if isinstance(data, list):
            all_findings = []
            for item in data:
                all_findings.extend(normaliser.normalise(item))
            findings = all_findings
        else:
            findings = normaliser.normalise(data)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
        )
