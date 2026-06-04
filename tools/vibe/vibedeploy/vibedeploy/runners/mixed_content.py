"""mixed_content — custom runner checking for mixed content (HTTP resources on HTTPS pages)."""

from __future__ import annotations

import re
from urllib.parse import urlparse
from urllib.request import urlopen, Request
from urllib.error import URLError

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner


# Patterns to match HTTP resource references in HTML
_HTTP_RESOURCE_PATTERNS = [
    # src attributes
    re.compile(r'(?:src|href|action|data|poster|background)\s*=\s*["\']http://', re.IGNORECASE),
    # url() in inline CSS
    re.compile(r'url\(\s*["\']?http://', re.IGNORECASE),
    # srcset attributes
    re.compile(r'srcset\s*=\s*["\'][^"\']*http://', re.IGNORECASE),
]

# More specific extraction patterns
_HTTP_URL_EXTRACT = re.compile(
    r'(?:src|href|action|data|poster|background)\s*=\s*["\']'
    r'(http://[^"\'>\s]+)',
    re.IGNORECASE,
)

_CSS_URL_EXTRACT = re.compile(
    r'url\(\s*["\']?(http://[^"\')\s]+)',
    re.IGNORECASE,
)


class MixedContentRunner(AsyncToolRunner):
    name = "mixed_content"
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

        # Only check HTTPS pages for mixed content
        if parsed.scheme != "https":
            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS,
                findings=[Finding(
                    tool=self.name,
                    severity=Severity.HIGH,
                    category=Category.HTTP_HEADERS,
                    file=hostname,
                    rule_id="mixed-content-no-https",
                    rule_name="Site Not Using HTTPS",
                    message=f"Site {url} is not served over HTTPS — mixed content checks require HTTPS",
                    effort=Effort.MEDIUM,
                    fix_hint="Configure the site to serve over HTTPS first",
                )],
            )

        # Fetch the page
        try:
            req = Request(url, headers={"User-Agent": "vibedeploy/1.0"})
            with urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")
        except URLError as e:
            return self._make_error_result(f"Could not fetch {url}: {e}")
        except Exception as e:
            return self._make_error_result(f"HTTP request failed for {url}: {e}")

        findings: list[Finding] = []

        # Extract all HTTP URLs from HTML attributes
        http_urls_attr = set(_HTTP_URL_EXTRACT.findall(html))
        http_urls_css = set(_CSS_URL_EXTRACT.findall(html))
        all_http_urls = http_urls_attr | http_urls_css

        # Filter out data: and javascript: pseudo-URLs that might match,
        # and exclude common safe patterns (protocol-relative already ok)
        for http_url in sorted(all_http_urls):
            http_url = http_url.strip()
            if not http_url.startswith("http://"):
                continue

            # Determine resource type
            resource_type = self._classify_resource(http_url)
            is_active = resource_type in ("script", "stylesheet", "iframe", "object", "form")

            severity = Severity.HIGH if is_active else Severity.MEDIUM

            findings.append(Finding(
                tool=self.name,
                severity=severity,
                category=Category.HTTP_HEADERS,
                file=hostname,
                rule_id=f"mixed-content-{'active' if is_active else 'passive'}",
                rule_name=f"Mixed Content ({'Active' if is_active else 'Passive'})",
                message=f"{'Active' if is_active else 'Passive'} mixed content: "
                        f"HTTP {resource_type} loaded on HTTPS page: {http_url[:200]}",
                effort=Effort.TRIVIAL,
                fix_hint=f"Change {http_url[:100]} to use HTTPS, or use protocol-relative URL (//)",
            ))

        # Check for meta tag that might upgrade insecure requests
        has_upgrade = "upgrade-insecure-requests" in html.lower()
        if all_http_urls and not has_upgrade:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.LOW,
                category=Category.HTTP_HEADERS,
                file=hostname,
                rule_id="mixed-content-no-upgrade-meta",
                rule_name="Missing upgrade-insecure-requests",
                message="Page has HTTP resources but no upgrade-insecure-requests CSP directive",
                effort=Effort.TRIVIAL,
                fix_hint="Add Content-Security-Policy: upgrade-insecure-requests header or meta tag",
            ))

        return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=findings)

    @staticmethod
    def _classify_resource(url: str) -> str:
        """Classify a URL into a resource type based on its extension or path."""
        url_lower = url.lower().split("?")[0].split("#")[0]

        if url_lower.endswith((".js", ".mjs")):
            return "script"
        if url_lower.endswith((".css",)):
            return "stylesheet"
        if url_lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".bmp")):
            return "image"
        if url_lower.endswith((".woff", ".woff2", ".ttf", ".eot", ".otf")):
            return "font"
        if url_lower.endswith((".mp4", ".webm", ".ogg", ".avi")):
            return "video"
        if url_lower.endswith((".mp3", ".wav", ".flac", ".aac")):
            return "audio"
        if url_lower.endswith((".html", ".htm")):
            return "iframe"
        if url_lower.endswith((".swf",)):
            return "object"

        return "resource"
