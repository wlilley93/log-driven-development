"""Normaliser for glyphhanger output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser


class GlyphhangerNormaliser(BaseNormaliser):
    """Convert glyphhanger analysis to Finding objects.

    Input shape (built by the runner):
    {
      "fonts": [
        {
          "file": "fonts/Inter.woff2",
          "total_glyphs": 850,
          "used_glyphs": 120,
          "unused_glyphs": 730,
          "unused_pct": 85.9,
          "file_size": 95000,
          "unicode_ranges": "U+0000-00FF, U+0131, ..."
        }
      ],
      "charset": "abcdefg..."
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        findings: list[Finding] = []

        for font_info in raw_data.get("fonts", []):
            if not isinstance(font_info, dict):
                continue

            filepath = font_info.get("file", "unknown")
            total_glyphs = font_info.get("total_glyphs", 0)
            used_glyphs = font_info.get("used_glyphs", 0)
            unused_pct = font_info.get("unused_pct", 0)
            file_size = font_info.get("file_size", 0)
            unicode_ranges = font_info.get("unicode_ranges", "")

            if total_glyphs == 0:
                continue

            if unused_pct > 50:
                severity = Severity.MEDIUM
                rule_id = "high-unused-glyphs"
                rule_name = "High unused glyph percentage"
            elif unused_pct > 25:
                severity = Severity.LOW
                rule_id = "moderate-unused-glyphs"
                rule_name = "Moderate unused glyph percentage"
            else:
                severity = Severity.INFO
                rule_id = "font-glyph-info"
                rule_name = "Font glyph usage info"

            estimated_savings = int(file_size * (unused_pct / 100)) if file_size > 0 else 0

            findings.append(Finding(
                tool="glyphhanger",
                severity=severity,
                category=Category.FONT,
                file=filepath,
                rule_id=rule_id,
                rule_name=rule_name,
                message=(
                    f"Font '{filepath}' contains {total_glyphs} glyphs but only "
                    f"{used_glyphs} are used ({unused_pct:.1f}% unused). "
                    f"File size: {file_size / 1024:.1f} KB."
                ),
                metric="unused_glyphs_pct",
                current_value=float(unused_pct),
                target_value=25.0,
                fix_hint=_get_fix_hint(filepath, unused_pct, unicode_ranges),
                saving_estimate=f"~{estimated_savings / 1024:.1f} KB with subsetting",
                effort=Effort.MEDIUM,
                raw=font_info,
            ))

        return findings


def _get_fix_hint(filepath: str, unused_pct: float, unicode_ranges: str) -> str:
    """Generate fix hint for font subsetting."""
    if unused_pct > 50:
        hint = (
            f"Subset '{filepath}' to include only the glyphs actually used. "
            f"Use glyphhanger to generate a subset: "
            f"`npx glyphhanger --whitelist='...' --subset={filepath}`. "
        )
        if unicode_ranges:
            hint += f"Detected unicode range: {unicode_ranges[:80]}..."
        return hint

    return (
        f"Consider subsetting '{filepath}' to remove unused glyphs. "
        f"Use `@font-face` `unicode-range` to load font subsets on demand."
    )
