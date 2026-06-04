"""cfn-lint runner — validate CloudFormation templates."""

from __future__ import annotations

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.cfn_lint import CfnLintNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class CfnLintRunner(AsyncToolRunner):
    name = "cfn_lint"

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "cfn-lint not installed"
            return False
        # Look for CloudFormation template files
        has_templates = (
            self._file_exists("template.yaml", "template.json", "template.yml")
            or bool(self._scan_files("*.template.json"))
            or bool(self._scan_files("*.template.yaml"))
            or bool(self._scan_files("*.template.yml"))
            or bool(self._scan_files("cloudformation*.json"))
            or bool(self._scan_files("cloudformation*.yaml"))
            or bool(self._scan_files("cloudformation*.yml"))
        )
        if not has_templates:
            self.skip_reason = "no CloudFormation template files found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        # Find all CloudFormation template files
        templates = []
        for pattern in ("template.yaml", "template.yml", "template.json",
                        "*.template.json", "*.template.yaml", "*.template.yml",
                        "cloudformation*.json", "cloudformation*.yaml", "cloudformation*.yml"):
            templates.extend(self._scan_files(pattern))

        if not templates:
            return ToolResult(tool=self.name, status=ToolStatus.SKIPPED)

        all_findings = []
        normaliser = CfnLintNormaliser()

        for template in templates:
            cmd = [self.bin_path, "--format", "json", str(template)]
            data, stderr = self._exec_json(cmd)

            if data is None:
                # cfn-lint exits non-zero when findings exist
                result = self._exec(cmd)
                import json
                try:
                    data = json.loads(result.stdout)
                except (json.JSONDecodeError, ValueError):
                    continue

            if data:
                all_findings.extend(normaliser.normalise(data))

        status = ToolStatus.SUCCESS if not all_findings else ToolStatus.PARTIAL
        return ToolResult(tool=self.name, status=status, findings=all_findings)
