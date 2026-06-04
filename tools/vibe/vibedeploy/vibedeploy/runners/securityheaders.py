"""securityheaders runner — checks HTTP security headers via URL fetch."""

from __future__ import annotations

from urllib.parse import urlparse
from urllib.request import urlopen, Request
from urllib.error import URLError

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.normalisers.securityheaders import SecurityHeadersNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class SecurityHeadersRunner(AsyncToolRunner):
    name = "securityheaders"
    requires_url = True

    def should_run(self) -> bool:
        if not self.config.url:
            self.skip_reason = "requires --url"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        url = self.config.url
        if not url:
            return self._make_error_result("No URL configured")

        if "://" not in url:
            url = f"https://{url}"

        parsed = urlparse(url)
        hostname = parsed.hostname or url

        # Fetch headers from the URL
        try:
            req = Request(url, headers={"User-Agent": "vibedeploy/1.0"})
            with urlopen(req, timeout=15) as resp:
                headers = dict(resp.headers)
                status_code = resp.status
        except URLError as e:
            return self._make_error_result(f"Could not fetch {url}: {e}")
        except Exception as e:
            return self._make_error_result(f"HTTP request failed for {url}: {e}")

        normaliser = SecurityHeadersNormaliser()
        findings = normaliser.normalise({
            "headers": headers,
            "hostname": hostname,
            "url": url,
            "status_code": status_code,
        })

        return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=findings)
