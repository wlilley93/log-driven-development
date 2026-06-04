"""Normaliser for parker output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser


class ParkerNormaliser(BaseNormaliser):
    """Convert parker JSON metrics to Finding objects.

    parker outputs (per file or aggregated):
    {
      "total-stylesheets": 1,
      "total-stylesheet-size": 45000,
      "total-rules": 320,
      "total-selectors": 450,
      "total-identifiers": 1200,
      "total-declarations": 800,
      "selectors-per-rule": 1.4,
      "identifiers-per-selector": 2.7,
      "specificity-per-selector": 12.5,
      "top-selector-specificity": 130,
      "top-selector-specificity-selector": ".foo .bar #baz > div",
      "total-id-selectors": 15,
      "total-unique-colors": 42,
      "unique-colors": ["#fff", "#000", ...],
      "total-important-keywords": 8,
      "total-media-queries": 12
    }

    The runner passes: {"file": "path", "metrics": {...}}[]
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, list):
            return []

        findings: list[Finding] = []

        for entry in raw_data:
            if not isinstance(entry, dict):
                continue

            filepath = entry.get("file", "unknown")
            metrics = entry.get("metrics", {})
            if not isinstance(metrics, dict):
                continue

            # High specificity
            top_specificity = metrics.get("top-selector-specificity", 0)
            if top_specificity > 100:
                top_selector = metrics.get("top-selector-specificity-selector", "unknown")
                findings.append(Finding(
                    tool="parker",
                    severity=Severity.HIGH,
                    category=Category.CSS,
                    file=filepath,
                    rule_id="high-specificity",
                    rule_name="Very high CSS specificity",
                    message=(
                        f"Highest specificity in '{filepath}' is {top_specificity} "
                        f"(selector: `{top_selector}`). High specificity makes CSS "
                        f"hard to override and maintain."
                    ),
                    metric="top_specificity",
                    current_value=float(top_specificity),
                    target_value=50.0,
                    fix_hint=(
                        "Reduce specificity by avoiding ID selectors and deeply nested rules. "
                        "Use BEM naming or utility classes to keep specificity flat."
                    ),
                    effort=Effort.MEDIUM,
                    raw=metrics,
                ))
            elif top_specificity > 50:
                findings.append(Finding(
                    tool="parker",
                    severity=Severity.MEDIUM,
                    category=Category.CSS,
                    file=filepath,
                    rule_id="medium-specificity",
                    rule_name="Elevated CSS specificity",
                    message=(
                        f"Highest specificity in '{filepath}' is {top_specificity}. "
                        f"Consider flattening your selector hierarchy."
                    ),
                    metric="top_specificity",
                    current_value=float(top_specificity),
                    target_value=50.0,
                    fix_hint="Prefer class selectors over ID selectors and reduce nesting depth.",
                    effort=Effort.LOW,
                    raw=metrics,
                ))

            # ID selectors
            id_selectors = metrics.get("total-id-selectors", 0)
            if id_selectors > 0:
                findings.append(Finding(
                    tool="parker",
                    severity=Severity.MEDIUM if id_selectors > 5 else Severity.LOW,
                    category=Category.CSS,
                    file=filepath,
                    rule_id="id-selectors",
                    rule_name="ID selectors in CSS",
                    message=(
                        f"'{filepath}' uses {id_selectors} ID selector(s). "
                        f"ID selectors have high specificity and make overrides difficult."
                    ),
                    metric="id_selectors",
                    current_value=float(id_selectors),
                    target_value=0.0,
                    fix_hint="Replace `#id` selectors with `.class` selectors for lower specificity.",
                    effort=Effort.LOW,
                    raw=metrics,
                ))

            # !important usage
            important_count = metrics.get("total-important-keywords", 0)
            if important_count > 0:
                findings.append(Finding(
                    tool="parker",
                    severity=Severity.MEDIUM if important_count > 3 else Severity.LOW,
                    category=Category.CSS,
                    file=filepath,
                    rule_id="important-keywords",
                    rule_name="!important keywords",
                    message=(
                        f"'{filepath}' uses `!important` {important_count} time(s). "
                        f"Excessive use of !important indicates specificity issues."
                    ),
                    metric="important_count",
                    current_value=float(important_count),
                    target_value=0.0,
                    fix_hint=(
                        "Remove `!important` by fixing the underlying specificity issues. "
                        "Re-order your CSS or use more specific (but low-specificity) selectors."
                    ),
                    effort=Effort.MEDIUM,
                    raw=metrics,
                ))

            # Excessive selectors
            total_selectors = metrics.get("total-selectors", 0)
            if total_selectors > 1000:
                findings.append(Finding(
                    tool="parker",
                    severity=Severity.MEDIUM,
                    category=Category.CSS,
                    file=filepath,
                    rule_id="excessive-selectors",
                    rule_name="Excessive CSS selectors",
                    message=(
                        f"'{filepath}' contains {total_selectors} selectors. "
                        f"Large CSS files with many selectors slow down parsing and CSSOM construction."
                    ),
                    metric="total_selectors",
                    current_value=float(total_selectors),
                    target_value=500.0,
                    fix_hint=(
                        "Split the stylesheet into smaller files, remove unused rules, "
                        "or adopt a utility-first CSS framework to reduce selector count."
                    ),
                    effort=Effort.HIGH,
                    raw=metrics,
                ))

            # Excessive unique colors
            unique_colors = metrics.get("total-unique-colors", 0)
            if unique_colors > 30:
                findings.append(Finding(
                    tool="parker",
                    severity=Severity.LOW,
                    category=Category.CSS,
                    file=filepath,
                    rule_id="excessive-colors",
                    rule_name="Excessive unique colors",
                    message=(
                        f"'{filepath}' uses {unique_colors} unique colors. "
                        f"A large color palette can indicate inconsistent design tokens."
                    ),
                    metric="unique_colors",
                    current_value=float(unique_colors),
                    target_value=20.0,
                    fix_hint=(
                        "Consolidate similar colors into CSS custom properties (design tokens). "
                        "Audit near-duplicate colors and standardise the palette."
                    ),
                    effort=Effort.MEDIUM,
                    raw=metrics,
                ))

        return findings
