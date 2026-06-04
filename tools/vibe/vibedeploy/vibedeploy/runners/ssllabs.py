"""ssllabs runner — SSL Labs API grading for SSL/TLS configuration."""

from __future__ import annotations

import json
import time
from urllib.parse import urlparse
from urllib.request import urlopen, Request
from urllib.error import URLError

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner


# SSL Labs grade → severity mapping
_GRADE_SEVERITY = {
    "A+": Severity.INFO,
    "A": Severity.INFO,
    "A-": Severity.LOW,
    "B": Severity.MEDIUM,
    "C": Severity.MEDIUM,
    "D": Severity.HIGH,
    "E": Severity.HIGH,
    "F": Severity.CRITICAL,
    "T": Severity.CRITICAL,  # Trust issues
    "M": Severity.CRITICAL,  # Certificate name mismatch
}

_SSL_LABS_API = "https://api.ssllabs.com/api/v3"


class SsllabsRunner(AsyncToolRunner):
    name = "ssllabs"
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

        findings: list[Finding] = []

        try:
            result = self._analyze(hostname)
        except Exception as e:
            return self._make_error_result(f"SSL Labs API error: {e}")

        if not result:
            return self._make_error_result("SSL Labs API returned no results")

        status_str = result.get("status", "")
        if status_str == "ERROR":
            error_msg = result.get("statusMessage", "Unknown error")
            return self._make_error_result(f"SSL Labs analysis error: {error_msg}")

        endpoints = result.get("endpoints", [])
        if not endpoints:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.MEDIUM,
                category=Category.SSL_TLS,
                file=hostname,
                rule_id="ssllabs-no-endpoints",
                rule_name="No Endpoints Found",
                message=f"SSL Labs found no endpoints for {hostname}",
                effort=Effort.MEDIUM,
                fix_hint="Verify the domain resolves and SSL is configured",
            ))
            return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=findings)

        for endpoint in endpoints:
            ip_address = endpoint.get("ipAddress", "unknown")
            grade = endpoint.get("grade", "")
            grade_trust = endpoint.get("gradeTrustIgnored", "")

            if not grade:
                status_msg = endpoint.get("statusMessage", "")
                if status_msg:
                    findings.append(Finding(
                        tool=self.name,
                        severity=Severity.MEDIUM,
                        category=Category.SSL_TLS,
                        file=f"{hostname} ({ip_address})",
                        rule_id="ssllabs-endpoint-error",
                        rule_name="Endpoint Analysis Error",
                        message=f"SSL Labs could not grade {hostname} ({ip_address}): {status_msg}",
                        effort=Effort.MEDIUM,
                    ))
                continue

            severity = _GRADE_SEVERITY.get(grade, Severity.MEDIUM)
            blocks = grade in ("F", "T", "M")

            findings.append(Finding(
                tool=self.name,
                severity=severity,
                category=Category.SSL_TLS,
                file=f"{hostname} ({ip_address})",
                rule_id=f"ssllabs-grade-{grade.lower().replace('+', 'plus').replace('-', 'minus')}",
                rule_name=f"SSL Labs Grade: {grade}",
                message=f"SSL Labs grade for {hostname} ({ip_address}): {grade}"
                        + (f" (trust-ignored: {grade_trust})" if grade_trust and grade_trust != grade else ""),
                blocks_deploy=blocks,
                effort=Effort.MEDIUM if severity >= Severity.HIGH else Effort.LOW,
                fix_hint=_get_grade_fix_hint(grade),
                docs_url=f"https://www.ssllabs.com/ssltest/analyze.html?d={hostname}",
                raw=endpoint,
            ))

            # Check for specific issues in endpoint details
            details = endpoint.get("details", {})
            if details:
                self._check_endpoint_details(details, hostname, ip_address, findings)

        return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=findings)

    def _analyze(self, hostname: str) -> dict | None:
        """Call SSL Labs API and wait for analysis to complete."""
        # Start analysis (use cached results if available)
        api_url = (
            f"{_SSL_LABS_API}/analyze"
            f"?host={hostname}&fromCache=on&maxAge=24&all=done"
        )

        max_polls = 30
        poll_interval = 10

        for _ in range(max_polls):
            try:
                req = Request(api_url, headers={"User-Agent": "vibedeploy/1.0"})
                with urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode())
            except (URLError, json.JSONDecodeError, OSError):
                return None

            status = data.get("status", "")
            if status in ("READY", "ERROR"):
                return data
            if status in ("DNS", "IN_PROGRESS"):
                time.sleep(poll_interval)
                continue
            # Unknown status
            return data

        return None

    def _check_endpoint_details(
        self,
        details: dict,
        hostname: str,
        ip_address: str,
        findings: list[Finding],
    ) -> None:
        """Extract additional findings from SSL Labs endpoint details."""
        file_ref = f"{hostname} ({ip_address})"

        # Check protocol support
        protocols = details.get("protocols", [])
        for proto in protocols:
            name = proto.get("name", "")
            version = proto.get("version", "")
            proto_str = f"{name} {version}"

            if name == "SSL" or (name == "TLS" and version in ("1.0", "1.1")):
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.HIGH,
                    category=Category.SSL_TLS,
                    file=file_ref,
                    rule_id=f"ssllabs-deprecated-{name.lower()}{version.replace('.', '')}",
                    rule_name=f"Deprecated Protocol: {proto_str}",
                    message=f"Server supports deprecated {proto_str}",
                    effort=Effort.MEDIUM,
                    fix_hint=f"Disable {proto_str} in server configuration",
                ))

        # Check for vulnerabilities
        vuln_checks = {
            "poodle": ("POODLE vulnerability detected", Severity.HIGH),
            "heartbleed": ("Heartbleed vulnerability detected", Severity.CRITICAL),
            "freak": ("FREAK vulnerability detected", Severity.HIGH),
            "logjam": ("Logjam vulnerability detected", Severity.HIGH),
            "drownVulnerable": ("DROWN vulnerability detected", Severity.CRITICAL),
        }

        for key, (msg, sev) in vuln_checks.items():
            if details.get(key):
                findings.append(Finding(
                    tool=self.name,
                    severity=sev,
                    category=Category.SSL_TLS,
                    file=file_ref,
                    rule_id=f"ssllabs-vuln-{key.lower()}",
                    rule_name=msg,
                    message=f"{msg} on {hostname}",
                    blocks_deploy=sev == Severity.CRITICAL,
                    effort=Effort.MEDIUM,
                    fix_hint="Update server software and TLS configuration",
                ))

        # Check HSTS
        hsts_policy = details.get("hstsPolicy", {})
        hsts_status = hsts_policy.get("status", "")
        if hsts_status != "present":
            findings.append(Finding(
                tool=self.name,
                severity=Severity.MEDIUM,
                category=Category.SSL_TLS,
                file=file_ref,
                rule_id="ssllabs-no-hsts",
                rule_name="Missing HSTS",
                message=f"HSTS not configured for {hostname}",
                effort=Effort.TRIVIAL,
                fix_hint="Add Strict-Transport-Security header with max-age=31536000",
            ))


def _get_grade_fix_hint(grade: str) -> str | None:
    """Return a fix hint based on the SSL Labs grade."""
    hints = {
        "A+": None,
        "A": "Consider enabling HSTS preload for A+ grade",
        "A-": "Review cipher suite order and enable HSTS for a higher grade",
        "B": "Disable weak cipher suites and deprecated protocols (TLS 1.0/1.1)",
        "C": "Significant TLS configuration issues — disable legacy protocols, weak ciphers",
        "D": "Major TLS issues — upgrade server configuration, use modern cipher suites",
        "E": "Severe TLS configuration issues — immediate remediation required",
        "F": "Critical SSL/TLS failure — certificate or configuration is fundamentally broken",
        "T": "Certificate trust issues — use a certificate from a trusted CA",
        "M": "Certificate name mismatch — ensure the certificate covers the correct domain",
    }
    return hints.get(grade)
