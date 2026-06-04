"""pip_audit runner — audit Python dependencies for known vulnerabilities."""

from __future__ import annotations

import json

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.pip_audit import PipAuditNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class PipAuditRunner(AsyncToolRunner):
    name = "pip_audit"

    @property
    def bin_path(self) -> str:
        from vibedeploy.installer import get_tool_bin
        path = get_tool_bin(self.name)
        if path == self.name:
            return "pip-audit"
        return path

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "pip-audit not installed"
            return False
        if not self._file_exists("requirements.txt", "pyproject.toml", "setup.py", "setup.cfg", "Pipfile.lock"):
            self.skip_reason = "no Python dependency files found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        cmd = [self.bin_path, "--format", "json"]

        # Prefer requirements.txt for explicit deps
        if self._file_exists("requirements.txt"):
            cmd.extend(["--requirement", "requirements.txt"])

        try:
            result = self._exec(cmd, timeout=self.config.timeout * 2)
        except Exception as e:
            return self._make_error_result(f"pip-audit execution failed: {e}")

        if result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                normaliser = PipAuditNormaliser()
                findings = normaliser.normalise(data)
                return ToolResult(
                    tool=self.name,
                    status=ToolStatus.SUCCESS,
                    findings=findings,
                )
            except json.JSONDecodeError:
                pass

        # pip-audit returns exit code 1 when vulnerabilities found
        if result.returncode not in (0, 1):
            return self._make_error_result(
                f"pip-audit exited with code {result.returncode}: {result.stderr[:300]}"
            )

        return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=[])
