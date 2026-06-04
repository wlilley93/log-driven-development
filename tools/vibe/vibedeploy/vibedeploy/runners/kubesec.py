"""kubesec runner — security risk analysis for Kubernetes resources."""

from __future__ import annotations

import json

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.kubesec import KubesecNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class KubesecRunner(AsyncToolRunner):
    name = "kubesec"
    requires_k8s = True

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "kubesec not installed"
            return False
        k8s_files = self._scan_files("*.yaml", "*.yml")
        if not k8s_files:
            self.skip_reason = "no Kubernetes YAML files found"
            return False
        return super().should_run()

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        k8s_dirs = ["k8s", "kubernetes", "deploy", "manifests", "."]
        yaml_files = []
        for d in k8s_dirs:
            yaml_files.extend(self._scan_files(f"{d}/*.yaml", f"{d}/*.yml"))

        if not yaml_files:
            yaml_files = self._scan_files("*.yaml", "*.yml")

        if not yaml_files:
            return ToolResult(tool=self.name, status=ToolStatus.SKIPPED)

        all_findings = []
        normaliser = KubesecNormaliser()

        for yaml_file in yaml_files:
            try:
                rel_path = str(yaml_file.relative_to(self.target))
                cmd = [self.bin_path, "scan", str(yaml_file)]
                result = self._exec(cmd, timeout=30)

                if result.stdout.strip():
                    try:
                        data = json.loads(result.stdout)
                        if isinstance(data, list):
                            for item in data:
                                item["_file"] = rel_path
                                all_findings.extend(normaliser.normalise(item))
                        else:
                            data["_file"] = rel_path
                            all_findings.extend(normaliser.normalise(data))
                    except json.JSONDecodeError:
                        continue
            except Exception:
                continue

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=all_findings,
        )
