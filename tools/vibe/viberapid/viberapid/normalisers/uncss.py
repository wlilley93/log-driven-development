"""Normaliser for UnCSS output."""

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


class UncssNormaliser(BaseNormaliser):
    """Convert UnCSS analysis to Finding objects.

    Input shape (built by the runner):
    {
      "files": [
        {
          "file": "styles/main.css",
          "original_size": 85000,
          "cleaned_size": 28000,
          "savings": 57000,
          "savings_pct": 67.1
        }
      ],
      "total_original": 120000,
      "total_cleaned": 42000,
      "total_savings": 78000
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
            cleaned = entry.get("cleaned_size", 0)
            savings = entry.get("savings", 0)
            pct = entry.get("savings_pct", 0)

            # Skip files where uncss encountered errors
            if entry.get("error") and savings == 0:
                continue

            if pct > 60:
                severity = Severity.HIGH
                rule_id = "high-unused-css"
                rule_name = "High unused CSS detected by UnCSS (>60%)"
            elif pct > 30:
                severity = Severity.MEDIUM
                rule_id = "medium-unused-css"
                rule_name = "Medium unused CSS detected by UnCSS (>30%)"
            elif pct > 10:
                severity = Severity.LOW
                rule_id = "low-unused-css"
                rule_name = "Low unused CSS detected by UnCSS (>10%)"
            else:
                # Minimal unused CSS, not worth reporting
                continue

            findings.append(Finding(
                tool="uncss",
                severity=severity,
                category=Category.CSS,
                file=filepath,
                rule_id=rule_id,
                rule_name=rule_name,
                message=(
                    f"'{filepath}' has {pct:.1f}% unused CSS rules. "
                    f"Original: {_format_bytes(original)}, "
                    f"after removing unused rules: {_format_bytes(cleaned)}, "
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
    """Generate a relevant fix hint based on the amount of unused CSS."""
    if pct > 60:
        return (
            f"'{filepath}' has very high unused CSS ({pct:.0f}%). Consider: "
            f"(1) Run `npx uncss` as part of your build pipeline to strip dead rules, "
            f"(2) Split into route-specific stylesheets loaded on demand, "
            f"(3) Migrate to a utility-first framework like Tailwind with tree-shaking."
        )
    if pct > 30:
        return (
            f"Integrate UnCSS or PurgeCSS into your build process to remove unused "
            f"selectors from '{filepath}'. If using a CSS framework, ensure only "
            f"the components you actually use are imported."
        )
    return (
        f"'{filepath}' has a moderate amount of unused CSS. Running "
        f"`npx uncss` during builds can trim the remaining dead rules."
    )
