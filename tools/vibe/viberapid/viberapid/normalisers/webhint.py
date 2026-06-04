"""Normaliser for webhint output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser

# Map webhint severity numbers to our Severity enum
_SEVERITY_MAP = {
    1: Severity.LOW,       # off (but reported)
    2: Severity.LOW,       # hint
    3: Severity.MEDIUM,    # warning
    4: Severity.HIGH,      # error
}

# Map hint categories to our Category enum
_CATEGORY_MAP = {
    "cache": Category.CACHE,
    "http": Category.NETWORK,
    "security": Category.NETWORK,
    "compatibility": Category.NETWORK,
    "performance": Category.NETWORK,
    "pwa": Category.NETWORK,
    "accessibility": Category.RENDER,
}


def _classify_hint(hint_id: str) -> Category:
    """Map a webhint hint ID to a Category based on naming conventions."""
    hint_lower = hint_id.lower()
    if "cache" in hint_lower or "ttl" in hint_lower:
        return Category.CACHE
    if "header" in hint_lower or "http" in hint_lower or "security" in hint_lower:
        return Category.NETWORK
    if "compat" in hint_lower or "browser" in hint_lower:
        return Category.NETWORK
    return Category.NETWORK


class WebhintNormaliser(BaseNormaliser):
    """Convert webhint JSON output to Finding objects.

    webhint JSON output shape (array of problem objects):
    [
      {
        "resource": "https://example.com",
        "problems": [
          {
            "message": "...",
            "severity": 3,
            "hintId": "no-vulnerable-javascript-libraries",
            "category": "security",
            "location": { "line": 1, "column": 1 },
            "sourceCode": "..."
          }
        ]
      },
      ...
    ]
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, list):
            return []

        findings: list[Finding] = []

        for entry in raw_data:
            if not isinstance(entry, dict):
                continue

            resource = entry.get("resource", "<url>")
            problems = entry.get("problems", [])

            for problem in problems:
                if not isinstance(problem, dict):
                    continue

                hint_id = problem.get("hintId", "unknown")
                message = problem.get("message", "")
                sev_num = problem.get("severity", 2)
                category_str = problem.get("category", "")
                location = problem.get("location", {})

                severity = _SEVERITY_MAP.get(sev_num, Severity.LOW)
                category = _CATEGORY_MAP.get(category_str, _classify_hint(hint_id))

                # Derive effort and fix hint from hint category
                if "cache" in hint_id.lower():
                    effort = Effort.LOW
                    fix_hint = "Add appropriate Cache-Control headers to static assets."
                elif "security" in (category_str or "").lower() or "header" in hint_id.lower():
                    effort = Effort.LOW
                    fix_hint = "Add the recommended security header to your server configuration."
                elif "compat" in hint_id.lower():
                    effort = Effort.MEDIUM
                    fix_hint = "Check browser compatibility and add polyfills or fallbacks if needed."
                else:
                    effort = Effort.MEDIUM
                    fix_hint = f"Review the webhint documentation for '{hint_id}' and apply the suggested fix."

                findings.append(Finding(
                    tool="webhint",
                    severity=severity,
                    category=category,
                    file=resource,
                    rule_id=hint_id,
                    rule_name=hint_id.replace("-", " ").title(),
                    message=message,
                    line=location.get("line"),
                    col=location.get("column"),
                    effort=effort,
                    fix_hint=fix_hint,
                    raw=problem,
                ))

        return findings
