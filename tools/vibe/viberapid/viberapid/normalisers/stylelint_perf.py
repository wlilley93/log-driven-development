"""Normaliser for stylelint performance-focused output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser

# Map stylelint rule IDs to severity, effort, and human-readable descriptions
_RULE_META: dict[str, dict[str, Any]] = {
    "selector-max-compound-selectors": {
        "severity": Severity.MEDIUM,
        "effort": Effort.MEDIUM,
        "name": "Deep compound selector",
        "hint": (
            "Reduce selector depth by flattening with BEM naming or utility classes. "
            "Deep selectors force the browser to match more DOM nodes during style recalculation."
        ),
    },
    "selector-max-id": {
        "severity": Severity.MEDIUM,
        "effort": Effort.LOW,
        "name": "ID selector in CSS",
        "hint": (
            "Replace `#id` selectors with `.class` selectors. ID selectors have "
            "unnecessarily high specificity and make overrides difficult."
        ),
    },
    "selector-max-universal": {
        "severity": Severity.HIGH,
        "effort": Effort.LOW,
        "name": "Universal selector (*)",
        "hint": (
            "Avoid the universal selector `*` as it matches every element in the DOM. "
            "Use targeted class selectors instead for better rendering performance."
        ),
    },
    "selector-no-qualifying-type": {
        "severity": Severity.LOW,
        "effort": Effort.LOW,
        "name": "Qualifying type selector",
        "hint": (
            "Remove the type qualifier from the selector (e.g., use `.btn` instead of "
            "`div.btn`). Type-qualified selectors increase specificity without benefit."
        ),
    },
    "max-nesting-depth": {
        "severity": Severity.MEDIUM,
        "effort": Effort.MEDIUM,
        "name": "Excessive nesting depth",
        "hint": (
            "Reduce nesting to 3 levels or fewer. Deep nesting creates overly specific "
            "selectors that are hard to override and slow to match."
        ),
    },
    "selector-max-specificity": {
        "severity": Severity.MEDIUM,
        "effort": Effort.MEDIUM,
        "name": "High selector specificity",
        "hint": (
            "Lower the specificity of this selector. Aim for a maximum of 0,3,0. "
            "Use single-class selectors where possible and avoid chaining."
        ),
    },
    "no-descending-specificity": {
        "severity": Severity.LOW,
        "effort": Effort.MEDIUM,
        "name": "Descending specificity order",
        "hint": (
            "Reorder selectors so that lower-specificity rules come before "
            "higher-specificity ones. Descending specificity causes unexpected cascade behaviour."
        ),
    },
    "declaration-no-important": {
        "severity": Severity.MEDIUM,
        "effort": Effort.MEDIUM,
        "name": "!important declaration",
        "hint": (
            "Remove `!important` by fixing the underlying specificity issue. "
            "Excessive !important usage leads to specificity wars and unmaintainable CSS."
        ),
    },
}


class StylelintPerfNormaliser(BaseNormaliser):
    """Convert stylelint JSON output to Finding objects.

    stylelint --formatter json outputs:
    [
      {
        "source": "src/styles/main.css",
        "warnings": [
          {
            "line": 42,
            "column": 5,
            "rule": "selector-max-compound-selectors",
            "severity": "warning",
            "text": "Expected selector to have no more than 3 compound selectors"
          }
        ],
        "deprecations": [],
        "invalidOptionWarnings": []
      }
    ]
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, list):
            return []

        findings: list[Finding] = []

        for entry in raw_data:
            if not isinstance(entry, dict):
                continue

            filepath = entry.get("source", "unknown")
            warnings = entry.get("warnings", [])

            if not isinstance(warnings, list):
                continue

            for warning in warnings:
                if not isinstance(warning, dict):
                    continue

                rule = warning.get("rule", "unknown")
                line = warning.get("line")
                col = warning.get("column")
                text = warning.get("text", "")

                meta = _RULE_META.get(rule, {})
                severity = meta.get("severity", Severity.LOW)
                effort = meta.get("effort", Effort.LOW)
                rule_name = meta.get("name", rule)
                fix_hint = meta.get("hint")

                findings.append(Finding(
                    tool="stylelint-perf",
                    severity=severity,
                    category=Category.CSS,
                    file=filepath,
                    rule_id=rule,
                    rule_name=rule_name,
                    message=f"{filepath}:{line}:{col} - {text}",
                    line=line,
                    col=col,
                    fix_hint=fix_hint,
                    effort=effort,
                    raw=warning,
                ))

        return findings
