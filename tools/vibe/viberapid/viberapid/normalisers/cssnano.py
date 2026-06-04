"""Normaliser for cssnano dry-run output."""

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


class CssnanoNormaliser(BaseNormaliser):
    """Convert cssnano minification analysis to Finding objects.

    Input shape (built by the runner):
    {
      "files": [
        {
          "file": "styles/main.css",
          "original_size": 85000,
          "minified_size": 52000,
          "savings": 33000,
          "savings_pct": 38.8
        }
      ],
      "total_original": 150000,
      "total_minified": 95000,
      "total_savings": 55000
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
            minified = entry.get("minified_size", 0)
            savings = entry.get("savings", 0)
            pct = entry.get("savings_pct", 0)

            # Skip files where cssnano encountered errors or no savings
            if entry.get("error") and savings == 0:
                continue

            if pct > 50:
                severity = Severity.HIGH
                rule_id = "high-minification-savings"
                rule_name = "High CSS minification savings (>50%)"
            elif pct > 25:
                severity = Severity.MEDIUM
                rule_id = "medium-minification-savings"
                rule_name = "Medium CSS minification savings (>25%)"
            elif pct > 10:
                severity = Severity.LOW
                rule_id = "low-minification-savings"
                rule_name = "Low CSS minification savings (>10%)"
            else:
                # Already well-minified or minimal savings
                continue

            findings.append(Finding(
                tool="cssnano",
                severity=severity,
                category=Category.CSS,
                file=filepath,
                rule_id=rule_id,
                rule_name=rule_name,
                message=(
                    f"'{filepath}' can be minified from {_format_bytes(original)} "
                    f"to {_format_bytes(minified)} ({pct:.1f}% reduction). "
                    f"This CSS is not being minified in the current build."
                ),
                metric="css_minification_savings_pct",
                current_value=float(pct),
                target_value=5.0,
                fix_hint=_get_fix_hint(filepath, pct, savings),
                saving_estimate=f"{_format_bytes(savings)} with minification",
                effort=Effort.LOW,
                raw=entry,
            ))

        return findings


def _get_fix_hint(filepath: str, pct: float, savings: int) -> str:
    """Generate minification-specific fix hints."""
    if pct > 50:
        return (
            f"'{filepath}' has very high minification potential ({pct:.0f}%), indicating "
            f"it is served unminified. Add cssnano to your PostCSS pipeline: "
            f"`npm install -D cssnano` and add it to postcss.config.js. "
            f"If using a bundler, ensure CSS minification is enabled for production builds."
        )
    if pct > 25:
        return (
            f"Enable CSS minification in your build pipeline to save "
            f"{_format_bytes(savings)}. Install cssnano (`npm install -D cssnano`) "
            f"and configure it in PostCSS, or enable the built-in minifier in "
            f"your bundler (Webpack: css-minimizer-webpack-plugin, Vite: built-in)."
        )
    return (
        f"'{filepath}' has minor minification headroom. Ensure cssnano or an "
        f"equivalent minifier runs on CSS output during production builds."
    )
