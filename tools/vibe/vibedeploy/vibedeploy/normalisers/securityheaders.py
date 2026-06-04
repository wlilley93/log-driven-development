"""Normaliser for security headers check output."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser


# Required security headers: (header_name, severity_if_missing, fix_hint, effort)
_REQUIRED_HEADERS = [
    (
        "Content-Security-Policy",
        Severity.HIGH,
        "Add a Content-Security-Policy header to prevent XSS and data injection attacks",
        Effort.HIGH,
    ),
    (
        "Strict-Transport-Security",
        Severity.HIGH,
        "Add Strict-Transport-Security: max-age=31536000; includeSubDomains",
        Effort.TRIVIAL,
    ),
    (
        "X-Content-Type-Options",
        Severity.MEDIUM,
        "Add X-Content-Type-Options: nosniff to prevent MIME-type sniffing",
        Effort.TRIVIAL,
    ),
    (
        "X-Frame-Options",
        Severity.MEDIUM,
        "Add X-Frame-Options: DENY or SAMEORIGIN to prevent clickjacking",
        Effort.TRIVIAL,
    ),
    (
        "Permissions-Policy",
        Severity.MEDIUM,
        "Add Permissions-Policy header to control browser feature access",
        Effort.LOW,
    ),
    (
        "Referrer-Policy",
        Severity.LOW,
        "Add Referrer-Policy: strict-origin-when-cross-origin (or stricter)",
        Effort.TRIVIAL,
    ),
]

# Deprecated or insecure headers that should not be present
_DEPRECATED_HEADERS = [
    (
        "X-Powered-By",
        Severity.LOW,
        "Remove X-Powered-By header to avoid information disclosure",
        Effort.TRIVIAL,
    ),
    (
        "Server",
        Severity.INFO,
        "Consider removing or minimizing the Server header to reduce fingerprinting",
        Effort.TRIVIAL,
    ),
]

# Insecure header values
_INSECURE_VALUES = {
    "X-Frame-Options": [
        ("ALLOWALL", Severity.HIGH, "X-Frame-Options: ALLOWALL disables clickjacking protection"),
    ],
    "Access-Control-Allow-Origin": [
        ("*", Severity.MEDIUM, "Wildcard CORS origin may be overly permissive"),
    ],
    "Content-Security-Policy": [
        ("unsafe-inline", Severity.MEDIUM, "CSP allows unsafe-inline which weakens XSS protection"),
        ("unsafe-eval", Severity.MEDIUM, "CSP allows unsafe-eval which weakens XSS protection"),
    ],
}


class SecurityHeadersNormaliser(BaseNormaliser):
    tool_name = "securityheaders"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings: list[Finding] = []

        headers = raw_data.get("headers", {})
        hostname = raw_data.get("hostname", "unknown")

        # Normalise header keys to case-insensitive lookup
        header_map: dict[str, str] = {}
        header_values: dict[str, str] = {}
        for key, value in headers.items():
            header_map[key.lower()] = key
            header_values[key.lower()] = value

        # Check for missing required headers
        for header_name, severity, fix_hint, effort in _REQUIRED_HEADERS:
            if header_name.lower() not in header_map:
                findings.append(Finding(
                    tool=self.tool_name,
                    severity=severity,
                    category=Category.HTTP_HEADERS,
                    file=hostname,
                    rule_id=f"securityheaders-missing-{header_name.lower().replace('-', '_')}",
                    rule_name=f"Missing {header_name}",
                    message=f"Missing security header: {header_name}",
                    effort=effort,
                    fix_hint=fix_hint,
                    docs_url=f"https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/{header_name}",
                ))

        # Check for deprecated headers that should be removed
        for header_name, severity, fix_hint, effort in _DEPRECATED_HEADERS:
            if header_name.lower() in header_map:
                value = header_values.get(header_name.lower(), "")
                findings.append(Finding(
                    tool=self.tool_name,
                    severity=severity,
                    category=Category.HTTP_HEADERS,
                    file=hostname,
                    rule_id=f"securityheaders-deprecated-{header_name.lower().replace('-', '_')}",
                    rule_name=f"Deprecated Header: {header_name}",
                    message=f"Header {header_name} should be removed"
                            + (f" (value: {value[:100]})" if value else ""),
                    effort=effort,
                    fix_hint=fix_hint,
                ))

        # Check for insecure header values
        for header_name, checks in _INSECURE_VALUES.items():
            value = header_values.get(header_name.lower(), "")
            if not value:
                continue
            for bad_value, severity, message in checks:
                if bad_value.lower() in value.lower():
                    findings.append(Finding(
                        tool=self.tool_name,
                        severity=severity,
                        category=Category.HTTP_HEADERS,
                        file=hostname,
                        rule_id=f"securityheaders-insecure-{header_name.lower().replace('-', '_')}-{bad_value.lower().replace('-', '_').replace('*', 'wildcard')}",
                        rule_name=f"Insecure {header_name} Value",
                        message=f"{message} (current value: {value[:200]})",
                        effort=Effort.MEDIUM,
                        fix_hint=f"Review and tighten the {header_name} header value",
                    ))

        # Check HSTS configuration details
        hsts_value = header_values.get("strict-transport-security", "")
        if hsts_value:
            self._check_hsts_config(hsts_value, hostname, findings)

        return findings

    def _check_hsts_config(
        self, hsts_value: str, hostname: str, findings: list[Finding]
    ) -> None:
        """Check HSTS header configuration details."""
        hsts_lower = hsts_value.lower()

        # Check max-age
        if "max-age=" in hsts_lower:
            try:
                max_age_str = hsts_lower.split("max-age=")[1].split(";")[0].strip()
                max_age = int(max_age_str)
                if max_age < 31536000:  # Less than 1 year
                    findings.append(Finding(
                        tool=self.tool_name,
                        severity=Severity.LOW,
                        category=Category.HTTP_HEADERS,
                        file=hostname,
                        rule_id="securityheaders-hsts-short-maxage",
                        rule_name="Short HSTS max-age",
                        message=f"HSTS max-age is {max_age} seconds ({max_age // 86400} days) — "
                                "recommended minimum is 31536000 (1 year)",
                        effort=Effort.TRIVIAL,
                        fix_hint="Set max-age to at least 31536000 (1 year)",
                    ))
                if max_age == 0:
                    findings.append(Finding(
                        tool=self.tool_name,
                        severity=Severity.HIGH,
                        category=Category.HTTP_HEADERS,
                        file=hostname,
                        rule_id="securityheaders-hsts-zero-maxage",
                        rule_name="HSTS Disabled (max-age=0)",
                        message="HSTS is effectively disabled with max-age=0",
                        effort=Effort.TRIVIAL,
                        fix_hint="Set max-age to 31536000 to enable HSTS",
                    ))
            except (ValueError, IndexError):
                pass

        # Check for includeSubDomains
        if "includesubdomains" not in hsts_lower:
            findings.append(Finding(
                tool=self.tool_name,
                severity=Severity.LOW,
                category=Category.HTTP_HEADERS,
                file=hostname,
                rule_id="securityheaders-hsts-no-subdomains",
                rule_name="HSTS Missing includeSubDomains",
                message="HSTS header does not include includeSubDomains directive",
                effort=Effort.TRIVIAL,
                fix_hint="Add includeSubDomains to HSTS header for subdomain protection",
            ))
