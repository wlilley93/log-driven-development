"""httpx_probe runner — HTTP probing for deploy target analysis."""

from __future__ import annotations

import json

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.normalisers.httpx_probe import HttpxProbeNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class HttpxProbeRunner(AsyncToolRunner):
    name = "httpx_probe"
    requires_url = True

    @property
    def bin_path(self) -> str:
        from vibedeploy.installer import get_tool_bin
        path = get_tool_bin(self.name)
        if path == self.name:
            return "httpx"
        return path

    def should_run(self) -> bool:
        if not self.config.url:
            self.skip_reason = "requires --url"
            return False
        if not self._tool_exists():
            self.skip_reason = "httpx not installed"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        url = self.config.url
        if not url:
            return self._make_error_result("No URL configured")

        # Ensure URL has scheme
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"

        cmd = [
            self.bin_path,
            "-json",
            "-status-code",
            "-title",
            "-tech-detect",
            "-follow-redirects",
            "-timeout", "10",
        ]

        try:
            result = self._exec(cmd, input_data=url, timeout=30)
        except Exception as e:
            return self._make_error_result(f"httpx execution failed: {e}")

        findings = []
        normaliser = HttpxProbeNormaliser()

        if result.stdout.strip():
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    data["_url"] = url
                    findings.extend(normaliser.normalise(data))
                except json.JSONDecodeError:
                    continue

        # If no output at all, the URL may be unreachable
        if not result.stdout.strip():
            findings.append(Finding(
                tool=self.name,
                severity=Severity.CRITICAL,
                category=Category.DNS_NETWORK,
                file=".",
                rule_id="httpx-unreachable",
                rule_name="URL Unreachable",
                message=f"Could not reach {url}. The server may be down or not yet deployed.",
                blocks_deploy=True,
                effort=Effort.HIGH,
                fix_hint="Verify the server is running and DNS is correctly configured",
            ))

        status = ToolStatus.SUCCESS if result.returncode == 0 else ToolStatus.PARTIAL

        return ToolResult(tool=self.name, status=status, findings=findings)
