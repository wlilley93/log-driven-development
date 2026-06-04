"""trufflehog runner — deep secret scanning."""

from __future__ import annotations
from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.normalisers.trufflehog import TrufflehogNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class TrufflehogRunner(AsyncToolRunner):
    name = "trufflehog"

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "trufflehog not installed"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        cmd = [self.bin_path, "filesystem", "--json", "--no-update", self.target]
        result = self._exec(cmd, timeout=self.config.timeout * 2)
        findings = []
        if result.stdout.strip():
            normaliser = TrufflehogNormaliser()
            for line in result.stdout.strip().split("\n"):
                import json
                try:
                    data = json.loads(line)
                    findings.extend(normaliser.normalise(data))
                except (json.JSONDecodeError, Exception):
                    continue
        status = ToolStatus.SUCCESS if result.returncode in (0, 1) else ToolStatus.PARTIAL
        return ToolResult(tool=self.name, status=status, findings=findings)
