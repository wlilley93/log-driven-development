"""dotenv-linter runner — lint .env files for formatting and security issues."""

from __future__ import annotations

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.normalisers.dotenv_linter import DotenvLinterNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class DotenvLinterRunner(AsyncToolRunner):
    name = "dotenv_linter"

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "dotenv-linter not installed"
            return False
        if not self._file_exists(".env", ".env.example", ".env.production", ".env.staging"):
            self.skip_reason = "no .env files found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        env_files = self._scan_files(".env*")
        if not env_files:
            return ToolResult(tool=self.name, status=ToolStatus.SKIPPED)

        all_findings = []
        for env_file in env_files:
            try:
                result = self._exec([self.bin_path, str(env_file)])
                if result.stdout.strip():
                    normaliser = DotenvLinterNormaliser()
                    findings = normaliser.normalise({"output": result.stdout, "file": str(env_file.relative_to(self.target))})
                    all_findings.extend(findings)
            except Exception:
                continue

        return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=all_findings)
