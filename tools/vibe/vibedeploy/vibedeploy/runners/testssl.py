"""testssl runner — comprehensive SSL/TLS testing via testssl.sh."""

from __future__ import annotations

import json

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.testssl import TestsslNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class TestsslRunner(AsyncToolRunner):
    name = "testssl"
    requires_url = True

    def should_run(self) -> bool:
        if not self.config.url:
            self.skip_reason = "requires --url"
            return False
        if not self._tool_exists():
            self.skip_reason = "testssl.sh not installed"
            return False
        return True

    @property
    def bin_path(self) -> str:
        # testssl.sh is the binary name, not testssl
        from vibedeploy.installer import get_tool_bin
        path = get_tool_bin(self.name)
        if path == self.name:
            return "testssl.sh"
        return path

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        url = self.config.url
        if not url:
            return self._make_error_result("No URL configured")

        cmd = [self.bin_path, "--jsonfile", "-", url]

        try:
            result = self._exec(cmd, timeout=self.config.timeout * 3)
        except Exception as e:
            return self._make_error_result(f"testssl.sh execution failed: {e}")

        findings = []
        if result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                normaliser = TestsslNormaliser()
                findings = normaliser.normalise(data)
            except json.JSONDecodeError:
                # Try line-by-line JSON (NDJSON format)
                normaliser = TestsslNormaliser()
                for line in result.stdout.strip().split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        findings.extend(normaliser.normalise(entry))
                    except json.JSONDecodeError:
                        continue

        status = ToolStatus.SUCCESS if result.returncode in (0, 1) else ToolStatus.PARTIAL
        if result.returncode not in (0, 1) and not findings:
            return self._make_error_result(
                f"testssl.sh exited with code {result.returncode}: {result.stderr[:300]}"
            )

        return ToolResult(tool=self.name, status=status, findings=findings)
