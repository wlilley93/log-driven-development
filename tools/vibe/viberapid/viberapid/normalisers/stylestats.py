"""Normaliser for stylestats output."""

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


class StylestatsNormaliser(BaseNormaliser):
    """Convert stylestats JSON output to Finding objects.

    stylestats --format json outputs per file:
    {
      "published": "...",
      "paths": ["styles.css"],
      "stylesheets": 1,
      "size": 85000,
      "dataUriSize": 0,
      "ratioOfDataUriSize": 0,
      "gzippedSize": 18000,
      "rules": 480,
      "selectors": 620,
      "declarations": 950,
      "simplicity": 0.77,
      "averageOfIdentifiers": 2.1,
      "mostIdentifiers": 8,
      "mostIdentifiersSelector": ".nav .dropdown .menu > li > a:hover",
      "averageOfCohesion": 1.8,
      "lowestCohesion": 12,
      "lowestCohesionSelector": ".header",
      "totalUniqueFontSizes": 14,
      "uniqueFontSizes": ["12px", "14px", ...],
      "totalUniqueFontFamilies": 5,
      "uniqueFontFamilies": [...],
      "totalUniqueColors": 35,
      "uniqueColors": [...],
      "totalUniqueBackgroundImages": 3,
      "idSelectors": 8,
      "universalSelectors": 2,
      "unqualifiedAttributeSelectors": 1,
      "javascriptSpecificSelectors": 0,
      "importantKeywords": 12,
      "floatProperties": 15,
      "propertiesCount": [["display", 45], ["color", 38], ...]
    }

    The runner passes: [{"file": "path", "stats": {...}}]
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, list):
            return []

        findings: list[Finding] = []

        for entry in raw_data:
            if not isinstance(entry, dict):
                continue

            filepath = entry.get("file", "unknown")
            stats = entry.get("stats", {})
            if not isinstance(stats, dict):
                continue

            # Large file size
            size = stats.get("size", 0)
            gzipped = stats.get("gzippedSize", 0)
            if size > 100_000:
                findings.append(Finding(
                    tool="stylestats",
                    severity=Severity.MEDIUM,
                    category=Category.CSS,
                    file=filepath,
                    rule_id="large-css-file",
                    rule_name="Large CSS file",
                    message=(
                        f"'{filepath}' is {_format_bytes(size)} "
                        f"({_format_bytes(gzipped)} gzipped). "
                        f"Large CSS files increase page load time."
                    ),
                    metric="css_file_size",
                    current_value=float(size),
                    target_value=50000.0,
                    fix_hint=(
                        "Split into smaller files loaded per-route, remove unused rules, "
                        "or adopt CSS-in-JS / utility CSS to reduce shipped bytes."
                    ),
                    saving_estimate=f"{_format_bytes(size - 50000)} potential reduction",
                    effort=Effort.MEDIUM,
                    raw=stats,
                ))

            # Low simplicity (rules / selectors ratio)
            simplicity = stats.get("simplicity", 1.0)
            if simplicity < 0.6:
                findings.append(Finding(
                    tool="stylestats",
                    severity=Severity.MEDIUM,
                    category=Category.CSS,
                    file=filepath,
                    rule_id="low-simplicity",
                    rule_name="Low CSS simplicity",
                    message=(
                        f"'{filepath}' has a simplicity score of {simplicity:.2f} "
                        f"(rules/selectors ratio). Low simplicity indicates overly "
                        f"complex selectors with many grouped rules."
                    ),
                    metric="css_simplicity",
                    current_value=float(simplicity),
                    target_value=0.8,
                    fix_hint=(
                        "Reduce selector grouping complexity. Each rule should ideally "
                        "target a single selector for maintainability."
                    ),
                    effort=Effort.MEDIUM,
                    raw=stats,
                ))

            # Many !important keywords
            important = stats.get("importantKeywords", 0)
            if important > 5:
                findings.append(Finding(
                    tool="stylestats",
                    severity=Severity.MEDIUM,
                    category=Category.CSS,
                    file=filepath,
                    rule_id="important-overuse",
                    rule_name="Excessive !important usage",
                    message=(
                        f"'{filepath}' uses `!important` {important} times. "
                        f"This often signals specificity wars."
                    ),
                    metric="important_count",
                    current_value=float(important),
                    target_value=0.0,
                    fix_hint=(
                        "Refactor CSS to eliminate `!important` by restructuring "
                        "the cascade or reducing selector specificity."
                    ),
                    effort=Effort.MEDIUM,
                    raw=stats,
                ))

            # Excessive unique font sizes
            font_sizes = stats.get("totalUniqueFontSizes", 0)
            if font_sizes > 10:
                findings.append(Finding(
                    tool="stylestats",
                    severity=Severity.LOW,
                    category=Category.CSS,
                    file=filepath,
                    rule_id="many-font-sizes",
                    rule_name="Many unique font sizes",
                    message=(
                        f"'{filepath}' uses {font_sizes} unique font sizes. "
                        f"A consistent type scale typically uses 6-8 sizes."
                    ),
                    metric="unique_font_sizes",
                    current_value=float(font_sizes),
                    target_value=8.0,
                    fix_hint=(
                        "Consolidate font sizes into a design token scale "
                        f"(e.g., xs, sm, base, lg, xl, 2xl). Found: "
                        f"{', '.join(stats.get('uniqueFontSizes', [])[:8])}"
                    ),
                    effort=Effort.LOW,
                    raw=stats,
                ))

            # Many unique colors
            colors = stats.get("totalUniqueColors", 0)
            if colors > 25:
                findings.append(Finding(
                    tool="stylestats",
                    severity=Severity.LOW,
                    category=Category.CSS,
                    file=filepath,
                    rule_id="many-colors",
                    rule_name="Many unique colors",
                    message=(
                        f"'{filepath}' uses {colors} unique colors. "
                        f"A large palette suggests inconsistent design tokens."
                    ),
                    metric="unique_colors",
                    current_value=float(colors),
                    target_value=20.0,
                    fix_hint=(
                        "Define a color palette as CSS custom properties and replace "
                        "one-off hex/rgb values with token references."
                    ),
                    effort=Effort.MEDIUM,
                    raw=stats,
                ))

            # Excessive float usage
            floats = stats.get("floatProperties", 0)
            if floats > 10:
                findings.append(Finding(
                    tool="stylestats",
                    severity=Severity.LOW,
                    category=Category.CSS,
                    file=filepath,
                    rule_id="float-usage",
                    rule_name="Excessive float usage",
                    message=(
                        f"'{filepath}' uses `float` {floats} times. "
                        f"Modern layouts should use Flexbox or Grid instead."
                    ),
                    metric="float_count",
                    current_value=float(floats),
                    target_value=0.0,
                    fix_hint=(
                        "Replace float-based layouts with Flexbox (`display: flex`) "
                        "or CSS Grid (`display: grid`) for better maintainability."
                    ),
                    effort=Effort.MEDIUM,
                    raw=stats,
                ))

            # High identifier complexity
            most_identifiers = stats.get("mostIdentifiers", 0)
            if most_identifiers > 5:
                most_selector = stats.get("mostIdentifiersSelector", "")
                findings.append(Finding(
                    tool="stylestats",
                    severity=Severity.LOW,
                    category=Category.CSS,
                    file=filepath,
                    rule_id="complex-selector",
                    rule_name="Complex CSS selector",
                    message=(
                        f"Most complex selector in '{filepath}' has "
                        f"{most_identifiers} identifiers: `{most_selector}`."
                    ),
                    metric="max_identifiers",
                    current_value=float(most_identifiers),
                    target_value=3.0,
                    fix_hint="Flatten this selector to fewer identifiers using BEM or utility classes.",
                    effort=Effort.LOW,
                    raw=stats,
                ))

        return findings
