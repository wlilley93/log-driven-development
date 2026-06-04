"""observatory runner — Mozilla Observatory HTTP security header grading."""

from __future__ import annotations

import json
import time
from urllib.parse import urlparse
from urllib.request import urlopen, Request
from urllib.error import URLError

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.normalisers.observatory import ObservatoryNormaliser
from vibedeploy.runners.base import AsyncToolRunner

_OBSERVATORY_API = "https://observatory.mozilla.org/api/v2/analyze"


class ObservatoryRunner(AsyncToolRunner):
    name = "observatory"
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

        parsed = urlparse(url if "://" in url else f"https://{url}")
        hostname = parsed.hostname
        if not hostname:
            return self._make_error_result(f"Could not parse hostname from URL: {url}")

        # Call Mozilla Observatory API
        try:
            data = self._fetch_analysis(hostname)
        except Exception as e:
            return self._make_error_result(f"Observatory API error: {e}")

        if not data:
            return self._make_error_result(
                f"Mozilla Observatory returned no results for {hostname}"
            )

        normaliser = ObservatoryNormaliser()
        findings = normaliser.normalise({"data": data, "hostname": hostname})

        return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=findings)

    def _fetch_analysis(self, hostname: str) -> dict | None:
        """Fetch analysis from Mozilla Observatory API."""
        api_url = f"{_OBSERVATORY_API}?host={hostname}"

        # Initiate or retrieve cached scan
        try:
            req = Request(
                api_url,
                headers={"User-Agent": "vibedeploy/1.0"},
            )
            with urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
        except (URLError, json.JSONDecodeError, OSError):
            return None

        # If scan is in progress, poll for results
        scan_status = data.get("status")
        if scan_status in ("PENDING", "RUNNING", "ABORTED"):
            max_polls = 12
            poll_interval = 5
            for _ in range(max_polls):
                time.sleep(poll_interval)
                try:
                    req = Request(
                        api_url,
                        headers={"User-Agent": "vibedeploy/1.0"},
                    )
                    with urlopen(req, timeout=30) as resp:
                        data = json.loads(resp.read().decode())
                    if data.get("status") not in ("PENDING", "RUNNING"):
                        break
                except (URLError, json.JSONDecodeError, OSError):
                    return None

        return data
