"""Normaliser for Mozilla Observatory API output."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser


# Observatory grade → severity mapping
_GRADE_SEVERITY = {
    "A+": Severity.INFO,
    "A": Severity.INFO,
    "A-": Severity.LOW,
    "B+": Severity.LOW,
    "B": Severity.MEDIUM,
    "B-": Severity.MEDIUM,
    "C+": Severity.MEDIUM,
    "C": Severity.MEDIUM,
    "C-": Severity.HIGH,
    "D+": Severity.HIGH,
    "D": Severity.HIGH,
    "D-": Severity.HIGH,
    "F": Severity.CRITICAL,
}

# Test result → severity mapping for individual tests
_TEST_RESULT_SEVERITY = {
    "pass": Severity.INFO,
    "info": Severity.INFO,
    "notice": Severity.LOW,
    "warning": Severity.MEDIUM,
    "fail": Severity.HIGH,
    "critical": Severity.CRITICAL,
}


class ObservatoryNormaliser(BaseNormaliser):
    tool_name = "observatory"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings: list[Finding] = []

        data = raw_data.get("data", {})
        hostname = raw_data.get("hostname", "unknown")

        # Overall grade finding
        grade = data.get("grade")
        score = data.get("score")

        if grade:
            severity = _GRADE_SEVERITY.get(grade, Severity.MEDIUM)
            blocks = grade == "F"

            message = f"Mozilla Observatory grade for {hostname}: {grade}"
            if score is not None:
                message += f" (score: {score}/100)"

            findings.append(Finding(
                tool=self.tool_name,
                severity=severity,
                category=Category.HTTP_HEADERS,
                file=hostname,
                rule_id=f"observatory-grade-{grade.lower().replace('+', 'plus').replace('-', 'minus')}",
                rule_name=f"Observatory Grade: {grade}",
                message=message,
                blocks_deploy=blocks,
                effort=Effort.MEDIUM if severity >= Severity.HIGH else Effort.LOW,
                fix_hint=_get_grade_fix_hint(grade),
                docs_url=f"https://observatory.mozilla.org/analyze/{hostname}",
                raw={"grade": grade, "score": score},
            ))

        # Individual test results
        tests = data.get("tests", {})
        if isinstance(tests, dict):
            for test_name, test_data in tests.items():
                if not isinstance(test_data, dict):
                    continue

                result = test_data.get("result", "")
                pass_status = test_data.get("pass", True)
                score_modifier = test_data.get("score_modifier", 0)
                score_description = test_data.get("score_description", "")

                # Skip passing tests
                if pass_status and score_modifier >= 0:
                    continue

                test_severity = Severity.MEDIUM
                if not pass_status:
                    if score_modifier <= -20:
                        test_severity = Severity.HIGH
                    elif score_modifier <= -10:
                        test_severity = Severity.MEDIUM
                    else:
                        test_severity = Severity.LOW

                test_message = score_description or result or f"Failed test: {test_name}"

                findings.append(Finding(
                    tool=self.tool_name,
                    severity=test_severity,
                    category=Category.HTTP_HEADERS,
                    file=hostname,
                    rule_id=f"observatory-{test_name}",
                    rule_name=_format_test_name(test_name),
                    message=test_message,
                    effort=_get_test_effort(test_name),
                    fix_hint=_get_test_fix_hint(test_name),
                    docs_url=f"https://observatory.mozilla.org/analyze/{hostname}",
                    raw=test_data,
                ))

        return findings


def _format_test_name(test_name: str) -> str:
    """Format a test name to a human-readable string."""
    return test_name.replace("-", " ").replace("_", " ").title()


def _get_grade_fix_hint(grade: str) -> str | None:
    """Return a fix hint based on the Observatory grade."""
    if grade in ("A+", "A"):
        return None
    if grade in ("A-", "B+", "B"):
        return "Review failing security header tests and add missing headers"
    if grade in ("B-", "C+", "C", "C-"):
        return "Multiple security headers are missing or misconfigured — add CSP, HSTS, X-Frame-Options"
    return "Significant HTTP security header issues — implement Content-Security-Policy, HSTS, and other critical headers"


def _get_test_fix_hint(test_name: str) -> str | None:
    """Return a fix hint based on the test name."""
    hints = {
        "content-security-policy": "Add a Content-Security-Policy header to restrict resource loading",
        "cookies": "Set Secure, HttpOnly, and SameSite attributes on cookies",
        "cross-origin-resource-sharing": "Review CORS configuration — avoid overly permissive Access-Control-Allow-Origin",
        "public-key-pinning": "Consider using Certificate Transparency instead of HPKP",
        "redirection": "Ensure HTTP redirects to HTTPS with a 301 redirect",
        "referrer-policy": "Add Referrer-Policy header (e.g., strict-origin-when-cross-origin)",
        "strict-transport-security": "Add Strict-Transport-Security header with max-age=31536000; includeSubDomains",
        "subresource-integrity": "Add integrity attributes to external script and link tags",
        "x-content-type-options": "Add X-Content-Type-Options: nosniff header",
        "x-frame-options": "Add X-Frame-Options: DENY or SAMEORIGIN header",
        "x-xss-protection": "Add X-XSS-Protection: 0 header (modern browsers use CSP instead)",
    }
    return hints.get(test_name)


def _get_test_effort(test_name: str) -> Effort:
    """Estimate effort for fixing a given test."""
    easy_fixes = {
        "x-content-type-options",
        "x-frame-options",
        "x-xss-protection",
        "referrer-policy",
        "strict-transport-security",
    }
    if test_name in easy_fixes:
        return Effort.TRIVIAL
    if test_name == "content-security-policy":
        return Effort.HIGH
    return Effort.LOW
