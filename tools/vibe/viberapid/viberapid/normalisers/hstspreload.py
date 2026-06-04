"""Normaliser for hstspreload output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser


# Known issue codes from hstspreload and their severity/fix mappings
_ISSUE_DETAILS: dict[str, tuple[Severity, str, str]] = {
    # Missing or invalid HSTS header
    "response.no_header": (
        Severity.HIGH,
        "Add a Strict-Transport-Security header to all HTTPS responses.",
        "Add HSTS header to enable transport security and prevent downgrade attacks",
    ),
    "header.no_max_age": (
        Severity.HIGH,
        "Add max-age directive to the Strict-Transport-Security header (min 31536000 for preload).",
        "Add max-age to HSTS header for preload eligibility",
    ),
    "header.max_age_too_low": (
        Severity.HIGH,
        "Increase max-age to at least 31536000 (1 year). The HSTS preload list requires max-age >= 1 year.",
        "Increase HSTS max-age to >= 1 year for preload eligibility",
    ),
    "header.no_include_sub_domains": (
        Severity.HIGH,
        "Add includeSubDomains directive to the HSTS header. Preload requires all subdomains to be covered.",
        "Add includeSubDomains to protect all subdomains via HSTS",
    ),
    "header.no_preload": (
        Severity.MEDIUM,
        "Add the preload directive to the HSTS header to signal readiness for the preload list.",
        "Add preload directive to opt in to the HSTS preload list",
    ),
    # Redirect issues
    "redirects.http_first_redirect_to_https": (
        Severity.MEDIUM,
        "Ensure the HTTP-to-HTTPS redirect goes directly to the same host before redirecting elsewhere.",
        "Fix redirect chain: HTTP must redirect to HTTPS on the same host first",
    ),
    "redirects.too_many_redirects": (
        Severity.MEDIUM,
        "Reduce the redirect chain. The HSTS preload checker follows a limited number of redirects.",
        "Reduce the number of redirects in the chain",
    ),
    "redirects.no_redirect": (
        Severity.HIGH,
        "Configure HTTP to redirect to HTTPS. All HTTP traffic must be redirected to enforce HSTS.",
        "Add HTTP-to-HTTPS redirect to enforce transport security",
    ),
    # TLS/Connection issues
    "response.connection_error": (
        Severity.CRITICAL,
        "Fix the HTTPS connection. The server must be reachable over HTTPS with a valid certificate.",
        "Fix HTTPS connectivity to enable HSTS",
    ),
    "response.certificate_error": (
        Severity.CRITICAL,
        "Fix the TLS certificate. Ensure it is valid, not expired, and issued by a trusted CA.",
        "Fix TLS certificate issues blocking HSTS",
    ),
    # Domain issues
    "domain.is_subdomain": (
        Severity.LOW,
        "HSTS preload submissions must be for the root domain, not a subdomain. Submit the root domain instead.",
        "Submit the root domain for HSTS preload, not a subdomain",
    ),
}

# Default fix hint for unknown issue codes
_DEFAULT_FIX_HINT = "Review the HSTS preload requirements at hstspreload.org and fix the reported issue."


class HSTSPreloadNormaliser(BaseNormaliser):
    """Convert hstspreload JSON output to Finding objects.

    hstspreload JSON shape (varies by implementation):
    {
      "domain": "example.com",
      "status": "eligible" | "not_eligible" | "preloaded" | "unknown",
      "issues": [
        {
          "code": "header.max_age_too_low",
          "message": "max-age must be at least 31536000 (1 year)",
          "summary": "..."
        },
        ...
      ],
      "warnings": [
        {
          "code": "header.no_preload",
          "message": "No preload directive found",
          "summary": "..."
        },
        ...
      ]
    }

    Alternative shape (some versions):
    {
      "domain": "example.com",
      "eligible": false,
      "errors": [ { "code": "...", "message": "..." } ],
      "warnings": [ { "code": "...", "message": "..." } ]
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        findings: list[Finding] = []
        domain = raw_data.get("domain", "<url>")

        # Handle both "issues" and "errors" keys (different hstspreload versions)
        issues = raw_data.get("issues", []) or raw_data.get("errors", []) or []
        warnings = raw_data.get("warnings", []) or []

        # Process issues (errors)
        for issue in issues:
            if not isinstance(issue, dict):
                # Handle plain string issues
                if isinstance(issue, str):
                    issue = {"code": "unknown", "message": issue}
                else:
                    continue

            code = issue.get("code", "unknown")
            message = issue.get("message", "") or issue.get("summary", "")

            details = _ISSUE_DETAILS.get(code)
            if details:
                severity, fix_hint, saving = details
            else:
                severity = Severity.HIGH
                fix_hint = _DEFAULT_FIX_HINT
                saving = f"Fix HSTS issue: {code}"

            findings.append(Finding(
                tool="hstspreload",
                severity=severity,
                category=Category.NETWORK,
                file=domain,
                rule_id=f"hsts-{code}",
                rule_name=f"HSTS: {code.replace('.', ' ').replace('_', ' ').title()}",
                message=message or f"HSTS preload issue: {code}",
                effort=Effort.LOW,
                fix_hint=fix_hint,
                saving_estimate=saving,
                raw=issue,
            ))

        # Process warnings
        for warning in warnings:
            if not isinstance(warning, dict):
                if isinstance(warning, str):
                    warning = {"code": "unknown-warning", "message": warning}
                else:
                    continue

            code = warning.get("code", "unknown-warning")
            message = warning.get("message", "") or warning.get("summary", "")

            details = _ISSUE_DETAILS.get(code)
            if details:
                severity, fix_hint, saving = details
                # Downgrade severity for warnings
                if severity == Severity.CRITICAL:
                    severity = Severity.HIGH
                elif severity == Severity.HIGH:
                    severity = Severity.MEDIUM
            else:
                severity = Severity.LOW
                fix_hint = _DEFAULT_FIX_HINT
                saving = f"Address HSTS warning: {code}"

            findings.append(Finding(
                tool="hstspreload",
                severity=severity,
                category=Category.NETWORK,
                file=domain,
                rule_id=f"hsts-warn-{code}",
                rule_name=f"HSTS Warning: {code.replace('.', ' ').replace('_', ' ').title()}",
                message=message or f"HSTS preload warning: {code}",
                effort=Effort.LOW,
                fix_hint=fix_hint,
                saving_estimate=saving,
                raw=warning,
            ))

        # If no issues or warnings but status indicates a problem, add an info finding
        status = raw_data.get("status", "")
        eligible = raw_data.get("eligible")
        if not issues and not warnings:
            if status == "preloaded" or eligible is True:
                findings.append(Finding(
                    tool="hstspreload",
                    severity=Severity.INFO,
                    category=Category.NETWORK,
                    file=domain,
                    rule_id="hsts-preloaded",
                    rule_name="HSTS Preload Status",
                    message=f"Domain {domain} is already on or eligible for the HSTS preload list.",
                    effort=Effort.LOW,
                    fix_hint="No action needed. The domain has proper HSTS configuration.",
                    saving_estimate="HSTS preload provides automatic HTTPS enforcement in all major browsers",
                    raw={"status": status, "domain": domain},
                ))
            elif status in ("not_eligible", "unknown") or eligible is False:
                findings.append(Finding(
                    tool="hstspreload",
                    severity=Severity.MEDIUM,
                    category=Category.NETWORK,
                    file=domain,
                    rule_id="hsts-not-eligible",
                    rule_name="HSTS Preload Not Eligible",
                    message=(
                        f"Domain {domain} is not eligible for the HSTS preload list. "
                        "Ensure the HSTS header includes max-age >= 31536000, includeSubDomains, and preload directives."
                    ),
                    effort=Effort.LOW,
                    fix_hint=(
                        "Set the Strict-Transport-Security header to: "
                        "max-age=63072000; includeSubDomains; preload"
                    ),
                    saving_estimate="HSTS preload prevents SSL-stripping attacks and enforces HTTPS in all major browsers",
                    raw={"status": status, "domain": domain},
                ))

        return findings
