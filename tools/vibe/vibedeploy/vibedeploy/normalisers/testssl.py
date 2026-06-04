"""Normaliser for testssl.sh JSON output."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser


# testssl.sh severity mapping
_SEVERITY_MAP = {
    "OK": Severity.INFO,
    "INFO": Severity.INFO,
    "LOW": Severity.LOW,
    "MEDIUM": Severity.MEDIUM,
    "HIGH": Severity.HIGH,
    "CRITICAL": Severity.CRITICAL,
    "WARN": Severity.HIGH,
    "FATAL": Severity.CRITICAL,
    "NOT ok": Severity.HIGH,
}


class TestsslNormaliser(BaseNormaliser):
    tool_name = "testssl"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings = []

        # testssl.sh can output a list of scan results or a single object
        items = raw_data if isinstance(raw_data, list) else [raw_data]

        for item in items:
            if not isinstance(item, dict):
                continue

            test_id = item.get("id", "unknown")
            severity_text = item.get("severity", "INFO")
            finding_text = item.get("finding", "")

            # Skip informational OK entries unless they contain warnings
            if severity_text == "OK" and "VULNERABLE" not in finding_text.upper():
                continue

            severity = _SEVERITY_MAP.get(severity_text.upper(), Severity.MEDIUM)

            # Skip pure INFO entries to reduce noise
            if severity == Severity.INFO:
                continue

            ip = item.get("ip", "")
            port = item.get("port", "")
            host = f"{ip}:{port}" if ip and port else ip or "target"

            blocks = severity in (Severity.CRITICAL,)

            # Determine fix hint based on common test IDs
            fix_hint = _get_fix_hint(test_id, finding_text)

            findings.append(Finding(
                tool=self.tool_name,
                severity=severity,
                category=Category.SSL_TLS,
                file=host,
                rule_id=f"testssl-{test_id}",
                rule_name=test_id,
                message=finding_text or f"SSL/TLS issue: {test_id}",
                blocks_deploy=blocks,
                effort=Effort.MEDIUM,
                fix_hint=fix_hint,
                raw=item,
            ))

        return findings


def _get_fix_hint(test_id: str, finding: str) -> str | None:
    """Return a fix hint based on the testssl test ID."""
    test_lower = test_id.lower()
    finding_lower = finding.lower()

    if "heartbleed" in test_lower:
        return "Upgrade OpenSSL to a patched version (>= 1.0.1g)"
    if "poodle" in test_lower:
        return "Disable SSLv3 in your TLS configuration"
    if "beast" in test_lower:
        return "Prefer TLS 1.2+ cipher suites; disable CBC ciphers for TLS 1.0"
    if "freak" in test_lower:
        return "Remove export-grade cipher suites from server configuration"
    if "logjam" in test_lower:
        return "Use 2048-bit or larger DH parameters"
    if "sweet32" in test_lower:
        return "Disable 3DES cipher suites (DES-CBC3-SHA)"
    if "rc4" in test_lower:
        return "Disable all RC4 cipher suites"
    if "sslv2" in test_lower or "sslv3" in test_lower:
        return "Disable SSLv2/SSLv3; use TLS 1.2 or TLS 1.3 only"
    if "tls1" in test_lower and ("1_0" in test_lower or "1.0" in finding_lower):
        return "Disable TLS 1.0; use TLS 1.2+ only"
    if "tls1" in test_lower and ("1_1" in test_lower or "1.1" in finding_lower):
        return "Disable TLS 1.1; use TLS 1.2+ only"
    if "cert" in test_lower and "expir" in finding_lower:
        return "Renew the SSL certificate before it expires"
    if "hsts" in test_lower:
        return "Add Strict-Transport-Security header with a long max-age"

    return None
