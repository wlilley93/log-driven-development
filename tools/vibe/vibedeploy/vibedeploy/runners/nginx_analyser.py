"""nginx_analyser — custom runner analyzing nginx.conf for deploy issues."""

from __future__ import annotations

import re
from pathlib import Path

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner


class NginxAnalyserRunner(AsyncToolRunner):
    name = "nginx_analyser"

    def should_run(self) -> bool:
        if not self._file_exists("nginx.conf", "conf/nginx.conf", "etc/nginx/nginx.conf"):
            nginx_files = self._scan_files("**/*.conf")
            has_nginx_conf = any("nginx" in str(f).lower() for f in nginx_files)
            if not has_nginx_conf:
                self.skip_reason = "no nginx configuration found"
                return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        findings: list[Finding] = []
        target = Path(self.target)

        # Collect all nginx config files
        config_files: list[tuple[str, str]] = []
        for candidate in ("nginx.conf", "conf/nginx.conf", "etc/nginx/nginx.conf"):
            path = target / candidate
            if path.exists():
                config_files.append((candidate, self._read_file(path)))

        # Also check for additional nginx configs
        for f in self._scan_files("**/*.conf"):
            if "nginx" in str(f).lower():
                try:
                    rel = str(f.relative_to(target))
                except ValueError:
                    rel = str(f)
                if not any(rel == cf[0] for cf in config_files):
                    config_files.append((rel, self._read_file(f)))

        if not config_files:
            return ToolResult(tool=self.name, status=ToolStatus.SKIPPED)

        for config_name, content in config_files:
            self._check_server_tokens(content, config_name, findings)
            self._check_rate_limiting(content, config_name, findings)
            self._check_ssl_redirect(content, config_name, findings)
            self._check_security_headers(content, config_name, findings)
            self._check_client_max_body_size(content, config_name, findings)
            self._check_timeouts(content, config_name, findings)
            self._check_gzip(content, config_name, findings)

        return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=findings)

    def _check_server_tokens(
        self, content: str, config_name: str, findings: list[Finding]
    ) -> None:
        """Check for server_tokens on (information leak)."""
        if re.search(r"""server_tokens\s+on\s*;""", content):
            findings.append(Finding(
                tool=self.name,
                severity=Severity.MEDIUM,
                category=Category.WEB_SERVER,
                file=config_name,
                rule_id="nginx-server-tokens-on",
                rule_name="Server Tokens Enabled",
                message=(
                    "server_tokens is set to 'on', exposing nginx version in response headers. "
                    "This helps attackers identify vulnerable versions."
                ),
                blocks_deploy=False,
                effort=Effort.TRIVIAL,
                fix_hint="Set server_tokens off; in the http block",
            ))
        elif "server_tokens" not in content:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.LOW,
                category=Category.WEB_SERVER,
                file=config_name,
                rule_id="nginx-server-tokens-default",
                rule_name="Server Tokens Not Disabled",
                message=(
                    "server_tokens is not explicitly disabled. nginx defaults to 'on', "
                    "which exposes the server version."
                ),
                blocks_deploy=False,
                effort=Effort.TRIVIAL,
                fix_hint="Add server_tokens off; in the http block",
            ))

    def _check_rate_limiting(
        self, content: str, config_name: str, findings: list[Finding]
    ) -> None:
        """Check for rate limiting configuration."""
        has_limit_req_zone = "limit_req_zone" in content
        has_limit_req = "limit_req " in content
        has_limit_conn = "limit_conn" in content

        if not has_limit_req_zone and not has_limit_req and not has_limit_conn:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.MEDIUM,
                category=Category.WEB_SERVER,
                file=config_name,
                rule_id="nginx-no-rate-limiting",
                rule_name="No Rate Limiting",
                message=(
                    "No rate limiting directives (limit_req_zone, limit_req, limit_conn) found. "
                    "Without rate limiting, the server is vulnerable to DDoS and brute force attacks."
                ),
                blocks_deploy=False,
                effort=Effort.MEDIUM,
                fix_hint=(
                    "Add limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s; "
                    "and limit_req zone=api burst=20 nodelay;"
                ),
            ))

    def _check_ssl_redirect(
        self, content: str, config_name: str, findings: list[Finding]
    ) -> None:
        """Check for HTTP-to-HTTPS redirect."""
        has_listen_80 = re.search(r"""listen\s+80\b""", content)
        has_ssl_redirect = re.search(
            r"""return\s+301\s+https://|rewrite\s+\^\s+https://""", content
        )
        has_listen_443 = re.search(r"""listen\s+443\s+ssl""", content)

        if has_listen_80 and has_listen_443 and not has_ssl_redirect:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.HIGH,
                category=Category.WEB_SERVER,
                file=config_name,
                rule_id="nginx-no-ssl-redirect",
                rule_name="No SSL Redirect",
                message=(
                    "nginx listens on port 80 and 443 but has no HTTP-to-HTTPS redirect. "
                    "Users accessing via HTTP will send data unencrypted."
                ),
                blocks_deploy=False,
                effort=Effort.LOW,
                fix_hint=(
                    "Add a server block: server { listen 80; return 301 https://$host$request_uri; }"
                ),
            ))

    def _check_security_headers(
        self, content: str, config_name: str, findings: list[Finding]
    ) -> None:
        """Check for important security headers."""
        security_headers = {
            "X-Frame-Options": "add_header X-Frame-Options SAMEORIGIN;",
            "X-Content-Type-Options": "add_header X-Content-Type-Options nosniff;",
            "X-XSS-Protection": "add_header X-XSS-Protection \"1; mode=block\";",
            "Strict-Transport-Security": "add_header Strict-Transport-Security \"max-age=63072000; includeSubDomains\";",
            "Content-Security-Policy": "add_header Content-Security-Policy \"default-src 'self'\";",
        }

        missing_headers = []
        for header_name, example in security_headers.items():
            if header_name.lower() not in content.lower():
                missing_headers.append(header_name)

        if missing_headers:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.MEDIUM,
                category=Category.WEB_SERVER,
                file=config_name,
                rule_id="nginx-missing-security-headers",
                rule_name="Missing Security Headers",
                message=(
                    f"Missing security headers: {', '.join(missing_headers)}. "
                    f"These headers protect against common web attacks."
                ),
                blocks_deploy=False,
                effort=Effort.LOW,
                fix_hint="Add security headers using add_header directives in the server block",
            ))

    def _check_client_max_body_size(
        self, content: str, config_name: str, findings: list[Finding]
    ) -> None:
        """Check for oversized client_max_body_size."""
        match = re.search(r"""client_max_body_size\s+(\d+)([kmgKMG]?)""", content)
        if match:
            size = int(match.group(1))
            unit = match.group(2).lower()
            # Convert to MB for comparison
            size_mb = size
            if unit == "k":
                size_mb = size / 1024
            elif unit == "g":
                size_mb = size * 1024
            elif unit == "":
                size_mb = size / (1024 * 1024)

            if size_mb > 100:
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.MEDIUM,
                    category=Category.WEB_SERVER,
                    file=config_name,
                    rule_id="nginx-large-body-size",
                    rule_name="Large client_max_body_size",
                    message=(
                        f"client_max_body_size is set to {match.group(0)}, which may "
                        f"allow excessively large uploads that could exhaust server resources."
                    ),
                    blocks_deploy=False,
                    effort=Effort.TRIVIAL,
                    fix_hint="Reduce client_max_body_size to a reasonable value (e.g., 10m)",
                ))

    def _check_timeouts(
        self, content: str, config_name: str, findings: list[Finding]
    ) -> None:
        """Check for missing or overly permissive timeouts."""
        timeout_directives = [
            "client_body_timeout", "client_header_timeout",
            "send_timeout", "keepalive_timeout",
        ]

        has_any_timeout = any(d in content for d in timeout_directives)
        if not has_any_timeout:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.LOW,
                category=Category.WEB_SERVER,
                file=config_name,
                rule_id="nginx-no-timeouts",
                rule_name="No Timeout Configuration",
                message=(
                    "No explicit timeout directives found. Default timeouts may allow "
                    "slow connections to consume resources (slowloris attacks)."
                ),
                blocks_deploy=False,
                effort=Effort.LOW,
                fix_hint="Set client_body_timeout, client_header_timeout, and send_timeout",
            ))

    def _check_gzip(
        self, content: str, config_name: str, findings: list[Finding]
    ) -> None:
        """Check for gzip compression configuration."""
        if "gzip on" not in content and "gzip_static on" not in content:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.LOW,
                category=Category.WEB_SERVER,
                file=config_name,
                rule_id="nginx-no-gzip",
                rule_name="No Gzip Compression",
                message=(
                    "Gzip compression is not enabled. Enabling gzip reduces bandwidth "
                    "and improves page load times."
                ),
                blocks_deploy=False,
                effort=Effort.TRIVIAL,
                fix_hint="Add gzip on; and gzip_types text/plain application/json text/css;",
            ))
