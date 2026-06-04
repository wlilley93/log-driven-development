"""helm lint runner — validate Helm chart structure and templates."""

from __future__ import annotations

import re

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner


class HelmLintRunner(AsyncToolRunner):
    name = "helm_lint"

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "helm not installed"
            return False
        if not self._file_exists("Chart.yaml", "Chart.yml"):
            self.skip_reason = "no Chart.yaml found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        cmd = [self.bin_path, "lint", self.target]
        result = self._exec(cmd)

        findings: list[Finding] = []
        # helm lint outputs findings to both stdout and stderr
        output = (result.stdout or "") + "\n" + (result.stderr or "")

        for line in output.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            # Parse helm lint output lines:
            # [ERROR] templates/: ...
            # [WARNING] templates/deployment.yaml: ...
            # [INFO] ...
            match = re.match(r"\[(ERROR|WARNING|INFO)\]\s+(.+?):\s+(.*)", line)
            if match:
                level = match.group(1)
                location = match.group(2)
                message = match.group(3)

                severity = self._map_level(level)

                findings.append(Finding(
                    tool=self.name,
                    severity=severity,
                    category=Category.IAC,
                    file=location,
                    line=None,
                    rule_id=f"helm-{level.lower()}",
                    rule_name=f"Helm Lint {level.capitalize()}",
                    message=message,
                    effort=Effort.LOW,
                    blocks_deploy=severity in (Severity.CRITICAL, Severity.HIGH),
                ))

        status = ToolStatus.SUCCESS if result.returncode == 0 else ToolStatus.PARTIAL
        return ToolResult(tool=self.name, status=status, findings=findings)

    @staticmethod
    def _map_level(level: str) -> Severity:
        """Map helm lint level to Severity."""
        mapping = {
            "ERROR": Severity.HIGH,
            "WARNING": Severity.MEDIUM,
            "INFO": Severity.LOW,
        }
        return mapping.get(level.upper(), Severity.MEDIUM)
