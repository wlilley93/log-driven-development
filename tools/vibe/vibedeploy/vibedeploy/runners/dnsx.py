"""dnsx runner — DNS resolution checks for deploy targets."""

from __future__ import annotations

import json

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.normalisers.dnsx import DnsxNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class DnsxRunner(AsyncToolRunner):
    name = "dnsx"
    requires_url = True

    def should_run(self) -> bool:
        if not self.config.url:
            self.skip_reason = "requires --url"
            return False
        if not self._tool_exists():
            self.skip_reason = "dnsx not installed"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        url = self.config.url
        if not url:
            return self._make_error_result("No URL configured")

        # Extract hostname from URL
        hostname = self._extract_hostname(url)
        if not hostname:
            return self._make_error_result(f"Could not extract hostname from URL: {url}")

        cmd = [self.bin_path, "-json", "-resp", "-a", "-aaaa", "-cname", "-mx", "-ns", "-txt"]

        try:
            result = self._exec(cmd, input_data=hostname, timeout=30)
        except Exception as e:
            return self._make_error_result(f"dnsx execution failed: {e}")

        findings = []
        normaliser = DnsxNormaliser()

        if result.stdout.strip():
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    data["_hostname"] = hostname
                    findings.extend(normaliser.normalise(data))
                except json.JSONDecodeError:
                    continue

        # If no output at all, DNS resolution may have failed
        if not result.stdout.strip() and result.returncode != 0:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.CRITICAL,
                category=Category.DNS_NETWORK,
                file=".",
                rule_id="dns-resolution-failed",
                rule_name="DNS Resolution Failed",
                message=f"DNS resolution failed for {hostname}. The domain may not be configured.",
                blocks_deploy=True,
                effort=Effort.MEDIUM,
                fix_hint=f"Verify DNS records exist for {hostname}",
            ))

        status = ToolStatus.SUCCESS if result.returncode == 0 else ToolStatus.PARTIAL

        return ToolResult(tool=self.name, status=status, findings=findings)

    @staticmethod
    def _extract_hostname(url: str) -> str | None:
        """Extract hostname from URL."""
        from urllib.parse import urlparse
        try:
            parsed = urlparse(url if "://" in url else f"https://{url}")
            return parsed.hostname
        except Exception:
            return None
