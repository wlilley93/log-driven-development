"""Normaliser for PurgeCSS output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser


def _format_bytes(size_bytes: int | float) -> str:
    """Format byte count to human-readable string."""
    if size_bytes >= 1_048_576:
        return f"{size_bytes / 1_048_576:.1f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{int(size_bytes)} B"


class PurgecssNormaliser(BaseNormaliser):
    """Convert PurgeCSS analysis to Finding objects.

    Input shape (built by the runner):
    {
      "files": [
        {
          "file": "styles/main.css",
          "original_size": 85000,
          "purged_size": 32000,
          "savings": 53000,
          "savings_pct": 62.3
        }
      ],
      "total_original": 120000,
      "total_purged": 48000,
      "total_savings": 72000
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        findings: list[Finding] = []

        for entry in raw_data.get("files", []):
            if not isinstance(entry, dict):
                continue

            filepath = entry.get("file", "unknown")
            original = entry.get("original_size", 0)
            purged = entry.get("purged_size", 0)
            savings = entry.get("savings", 0)
            pct = entry.get("savings_pct", 0)

            if pct > 60:
                severity = Severity.HIGH
                rule_id = "high-unused-css"
                rule_name = "High unused CSS (>60%)"
            elif pct > 30:
                severity = Severity.MEDIUM
                rule_id = "medium-unused-css"
                rule_name = "Medium unused CSS (>30%)"
            elif pct > 10:
                severity = Severity.LOW
                rule_id = "low-unused-css"
                rule_name = "Low unused CSS (>10%)"
            else:
                severity = Severity.INFO
                rule_id = "minimal-unused-css"
                rule_name = "Minimal unused CSS"

            findings.append(Finding(
                tool="purgecss",
                severity=severity,
                category=Category.CSS,
                file=filepath,
                rule_id=rule_id,
                rule_name=rule_name,
                message=(
                    f"'{filepath}' has {pct:.1f}% unused CSS. "
                    f"Original: {_format_bytes(original)}, "
                    f"after purging: {_format_bytes(purged)}, "
                    f"potential savings: {_format_bytes(savings)}."
                ),
                metric="unused_css_pct",
                current_value=float(pct),
                target_value=10.0,
                fix_hint=_get_fix_hint(filepath, pct),
                saving_estimate=f"{_format_bytes(savings)} CSS reduction",
                effort=Effort.MEDIUM if pct > 30 else Effort.LOW,
                raw=entry,
            ))

        return findings


def _get_fix_hint(filepath: str, pct: float) -> str:
    """Generate a relevant fix hint."""
    if pct > 60:
        return (
            f"'{filepath}' has very high unused CSS. Consider: "
            f"(1) Enable PurgeCSS or Tailwind's purge in your build pipeline, "
            f"(2) Split into separate files loaded only on routes that need them, "
            f"(3) Remove unused utility classes and dead selectors."
        )
    if pct > 30:
        return (
            f"Enable CSS purging in your build tool (PostCSS, Webpack, etc.) "
            f"to remove unused selectors from '{filepath}'. "
            f"If using Tailwind, ensure the `content` paths cover all template files."
        )
    return (
        f"'{filepath}' has a small amount of unused CSS. Consider enabling CSS "
        f"purging in production builds for marginal savings."
    )
