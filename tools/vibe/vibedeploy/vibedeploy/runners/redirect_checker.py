"""redirect_checker — custom runner checking HTTP→HTTPS redirects and open redirect patterns."""

from __future__ import annotations

import re
from urllib.parse import urlparse
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner


# Open redirect patterns in redirect URLs
_OPEN_REDIRECT_PATTERNS = [
    re.compile(r"[?&](redirect|return|next|url|goto|target|rurl|dest|destination|redir|redirect_uri|continue|return_url|returnTo|forward|go|out|view|link)=", re.IGNORECASE),
]


class RedirectCheckerRunner(AsyncToolRunner):
    name = "redirect_checker"
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

        findings: list[Finding] = []

        # Check HTTP → HTTPS redirect
        self._check_http_to_https(hostname, parsed, findings)

        # Check for open redirect vulnerabilities
        self._check_open_redirects(url, hostname, findings)

        # Check redirect chain length
        self._check_redirect_chain(url, hostname, findings)

        return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=findings)

    def _check_http_to_https(
        self, hostname: str, parsed_url: urlparse, findings: list[Finding]
    ) -> None:
        """Check that HTTP automatically redirects to HTTPS."""
        # Construct HTTP version of the URL
        http_url = f"http://{hostname}"
        if parsed_url.port and parsed_url.port not in (80, 443):
            http_url += f":{parsed_url.port}"
        http_url += parsed_url.path or "/"

        try:
            req = Request(http_url, headers={"User-Agent": "vibedeploy/1.0"})
            # Use a custom opener that does not follow redirects
            import urllib.request
            import http.client

            class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, headers, newurl):
                    return None

            opener = urllib.request.build_opener(NoRedirectHandler)
            try:
                response = opener.open(req, timeout=10)
                status = response.status
                location = response.headers.get("Location", "")
            except HTTPError as e:
                status = e.code
                location = e.headers.get("Location", "")

        except URLError as e:
            # Connection refused on HTTP is acceptable (HTTPS-only)
            if "Connection refused" in str(e) or "No connection" in str(e):
                return
            # Network unreachable, etc.
            findings.append(Finding(
                tool=self.name,
                severity=Severity.LOW,
                category=Category.HTTP_HEADERS,
                file=hostname,
                rule_id="redirect-http-unreachable",
                rule_name="HTTP Endpoint Unreachable",
                message=f"Could not connect to HTTP endpoint {http_url}: {e}",
                effort=Effort.LOW,
                fix_hint="Verify HTTP endpoint is accessible for redirect testing",
            ))
            return
        except Exception:
            return

        # Check if we got a redirect to HTTPS
        if status in (301, 302, 303, 307, 308):
            if location.startswith("https://"):
                # Good — redirect to HTTPS
                if status == 302:
                    findings.append(Finding(
                        tool=self.name,
                        severity=Severity.LOW,
                        category=Category.HTTP_HEADERS,
                        file=hostname,
                        rule_id="redirect-http-302",
                        rule_name="HTTP→HTTPS Uses 302",
                        message=f"HTTP→HTTPS redirect uses 302 (temporary) instead of 301 (permanent)",
                        effort=Effort.TRIVIAL,
                        fix_hint="Use 301 (permanent) redirect from HTTP to HTTPS for SEO and security",
                    ))
                # 301 or 308 is ideal
                return
            else:
                # Redirects but not to HTTPS
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.HIGH,
                    category=Category.HTTP_HEADERS,
                    file=hostname,
                    rule_id="redirect-http-not-https",
                    rule_name="HTTP Redirect Not to HTTPS",
                    message=f"HTTP redirects to {location[:200]} instead of HTTPS",
                    effort=Effort.TRIVIAL,
                    fix_hint="Configure HTTP redirect to point to the HTTPS version of the site",
                ))
        elif status == 200:
            # No redirect — HTTP serves content directly
            findings.append(Finding(
                tool=self.name,
                severity=Severity.HIGH,
                category=Category.HTTP_HEADERS,
                file=hostname,
                rule_id="redirect-no-http-to-https",
                rule_name="Missing HTTP→HTTPS Redirect",
                message=f"No HTTP→HTTPS redirect configured for {hostname} — HTTP serves content directly",
                effort=Effort.TRIVIAL,
                fix_hint="Configure a 301 redirect from HTTP to HTTPS in your web server or load balancer",
            ))

    def _check_open_redirects(
        self, url: str, hostname: str, findings: list[Finding]
    ) -> None:
        """Test common open redirect patterns."""
        # Test a set of common open redirect payloads
        test_payloads = [
            f"{url}?redirect=https://evil.com",
            f"{url}?next=https://evil.com",
            f"{url}?url=https://evil.com",
            f"{url}?goto=https://evil.com",
            f"{url}?return_url=https://evil.com",
        ]

        for test_url in test_payloads:
            try:
                req = Request(test_url, headers={"User-Agent": "vibedeploy/1.0"})

                import urllib.request

                class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
                    def redirect_request(self, req, fp, code, msg, headers, newurl):
                        return None

                opener = urllib.request.build_opener(NoRedirectHandler)
                try:
                    response = opener.open(req, timeout=10)
                    location = response.headers.get("Location", "")
                    status = response.status
                except HTTPError as e:
                    location = e.headers.get("Location", "")
                    status = e.code

                # Check if the server redirected to the evil URL
                if status in (301, 302, 303, 307, 308) and location:
                    evil_parsed = urlparse(location)
                    if evil_parsed.hostname and evil_parsed.hostname != hostname:
                        if "evil.com" in evil_parsed.hostname:
                            param_name = urlparse(test_url).query.split("=")[0]
                            findings.append(Finding(
                                tool=self.name,
                                severity=Severity.CRITICAL,
                                category=Category.HTTP_HEADERS,
                                file=hostname,
                                rule_id="redirect-open-redirect",
                                rule_name="Open Redirect Vulnerability",
                                message=(
                                    f"Open redirect detected: {param_name} parameter "
                                    f"causes redirect to external domain ({location[:200]})"
                                ),
                                blocks_deploy=True,
                                effort=Effort.MEDIUM,
                                fix_hint=(
                                    "Validate redirect URLs server-side — only allow redirects "
                                    "to the same domain or a whitelist of trusted domains"
                                ),
                            ))
                            # One finding is enough to flag the issue
                            return

            except (URLError, Exception):
                continue

    def _check_redirect_chain(
        self, url: str, hostname: str, findings: list[Finding]
    ) -> None:
        """Check the redirect chain length."""
        max_redirects = 10
        current_url = url
        visited: list[str] = []
        redirect_count = 0

        for _ in range(max_redirects + 1):
            if current_url in visited:
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.HIGH,
                    category=Category.HTTP_HEADERS,
                    file=hostname,
                    rule_id="redirect-loop",
                    rule_name="Redirect Loop Detected",
                    message=f"Redirect loop detected: {' → '.join(visited[-5:])} → {current_url}",
                    effort=Effort.MEDIUM,
                    fix_hint="Fix the redirect configuration to eliminate the loop",
                ))
                return

            visited.append(current_url)

            try:
                req = Request(current_url, headers={"User-Agent": "vibedeploy/1.0"})

                import urllib.request

                class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
                    def redirect_request(self, req, fp, code, msg, headers, newurl):
                        return None

                opener = urllib.request.build_opener(NoRedirectHandler)
                try:
                    response = opener.open(req, timeout=10)
                    status = response.status
                    location = response.headers.get("Location", "")
                except HTTPError as e:
                    status = e.code
                    location = e.headers.get("Location", "")

                if status in (301, 302, 303, 307, 308) and location:
                    redirect_count += 1
                    current_url = location
                else:
                    break

            except (URLError, Exception):
                break

        if redirect_count > 3:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.LOW,
                category=Category.HTTP_HEADERS,
                file=hostname,
                rule_id="redirect-chain-long",
                rule_name="Long Redirect Chain",
                message=f"Redirect chain has {redirect_count} hops: {' → '.join(visited[:6])}",
                effort=Effort.LOW,
                fix_hint="Reduce the redirect chain to 1-2 hops for better performance",
            ))
