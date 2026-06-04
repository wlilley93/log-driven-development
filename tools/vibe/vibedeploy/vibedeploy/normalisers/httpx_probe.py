"""Normaliser for httpx JSON output."""

from __future__ import annotations

import re
from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser


class HttpxProbeNormaliser(BaseNormaliser):
    tool_name = "httpx_probe"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings: list[Finding] = []
        url = raw_data.get("_url", raw_data.get("url", "unknown"))
        status_code = raw_data.get("status_code", raw_data.get("status-code", 0))
        title = raw_data.get("title", "")
        tech = raw_data.get("tech", [])
        final_url = raw_data.get("final_url", raw_data.get("url", ""))
        scheme = raw_data.get("scheme", "")
        tls = raw_data.get("tls", {})
        header = raw_data.get("header", {})

        # Check for non-200 status
        if status_code and status_code >= 500:
            findings.append(Finding(
                tool=self.tool_name,
                severity=Severity.CRITICAL,
                category=Category.DNS_NETWORK,
                file=".",
                rule_id="httpx-server-error",
                rule_name="Server Error Response",
                message=f"URL {url} returned HTTP {status_code}. The server is returning errors.",
                blocks_deploy=True,
                effort=Effort.HIGH,
                fix_hint="Check server logs and fix the application error",
            ))
        elif status_code and 400 <= status_code < 500:
            findings.append(Finding(
                tool=self.tool_name,
                severity=Severity.MEDIUM,
                category=Category.DNS_NETWORK,
                file=".",
                rule_id="httpx-client-error",
                rule_name="Client Error Response",
                message=f"URL {url} returned HTTP {status_code}. The endpoint may not exist.",
                blocks_deploy=False,
                effort=Effort.LOW,
            ))

        # Check if HTTP (not HTTPS)
        if scheme == "http" and "localhost" not in url and "127.0.0.1" not in url:
            findings.append(Finding(
                tool=self.tool_name,
                severity=Severity.HIGH,
                category=Category.DNS_NETWORK,
                file=".",
                rule_id="httpx-no-tls",
                rule_name="No TLS/HTTPS",
                message=f"URL {url} is served over HTTP without TLS encryption.",
                blocks_deploy=False,
                effort=Effort.MEDIUM,
                fix_hint="Configure TLS certificate (Let's Encrypt) and redirect HTTP to HTTPS",
            ))

        # Check for self-signed cert
        if tls:
            issuer = tls.get("issuer_dn", "")
            subject = tls.get("subject_dn", "")
            if issuer and subject and issuer == subject:
                findings.append(Finding(
                    tool=self.tool_name,
                    severity=Severity.HIGH,
                    category=Category.DNS_NETWORK,
                    file=".",
                    rule_id="httpx-self-signed-cert",
                    rule_name="Self-Signed TLS Certificate",
                    message=(
                        f"TLS certificate for {url} appears to be self-signed. "
                        f"Browsers will show security warnings."
                    ),
                    blocks_deploy=False,
                    effort=Effort.LOW,
                    fix_hint="Replace with a certificate from a trusted CA (e.g., Let's Encrypt)",
                ))

        # Check for information disclosure in headers
        if isinstance(header, dict):
            server_header = header.get("server", "")
            if server_header:
                version_pattern = re.compile(r"""\d+\.\d+""")
                if version_pattern.search(server_header):
                    findings.append(Finding(
                        tool=self.tool_name,
                        severity=Severity.LOW,
                        category=Category.DNS_NETWORK,
                        file=".",
                        rule_id="httpx-server-version-leak",
                        rule_name="Server Version Disclosure",
                        message=f"Server header reveals version: '{server_header}'",
                        blocks_deploy=False,
                        effort=Effort.TRIVIAL,
                        fix_hint="Remove or obscure the Server header version information",
                    ))

            # Check for missing security headers
            security_headers = {
                "x-frame-options": "X-Frame-Options",
                "x-content-type-options": "X-Content-Type-Options",
                "strict-transport-security": "Strict-Transport-Security",
            }
            missing = []
            for h_key, h_name in security_headers.items():
                if h_key not in header:
                    missing.append(h_name)

            if missing:
                findings.append(Finding(
                    tool=self.tool_name,
                    severity=Severity.MEDIUM,
                    category=Category.DNS_NETWORK,
                    file=".",
                    rule_id="httpx-missing-security-headers",
                    rule_name="Missing HTTP Security Headers",
                    message=f"Missing security headers: {', '.join(missing)}",
                    blocks_deploy=False,
                    effort=Effort.LOW,
                    fix_hint="Add security headers to your web server or reverse proxy configuration",
                ))

        return findings
