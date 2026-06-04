"""Normaliser for fonttools analysis output."""

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


class FonttoolsNormaliser(BaseNormaliser):
    """Convert fonttools analysis results to Finding objects.

    Input shape (built by the runner):
    [
      {
        "file": "fonts/Inter-Regular.ttf",
        "file_size": 320000,
        "format": "TrueType",
        "num_glyphs": 2500,
        "tables": ["glyf", "cmap", "head", ...],
        "has_hinting": true,
        "family_name": "Inter",
        "is_variable": false,
        "num_masters": 1,
        "subsetting_potential": 0.65
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

            filepath = entry.get("file", "unknown")
            file_size = entry.get("file_size", 0)
            num_glyphs = entry.get("num_glyphs", 0)
            has_hinting = entry.get("has_hinting", False)
            font_format = entry.get("format", "unknown")
            family_name = entry.get("family_name", "unknown")
            is_variable = entry.get("is_variable", False)
            subsetting_potential = entry.get("subsetting_potential", 0)

            # Large font file
            if file_size > 500_000:  # > 500 KB
                findings.append(Finding(
                    tool="fonttools",
                    severity=Severity.HIGH,
                    category=Category.FONT,
                    file=filepath,
                    rule_id="large-font-file",
                    rule_name="Large font file (>500 KB)",
                    message=(
                        f"'{filepath}' ({family_name}, {font_format}) is "
                        f"{_format_bytes(file_size)} with {num_glyphs} glyphs."
                    ),
                    metric="font_file_size",
                    current_value=float(file_size),
                    target_value=100000.0,
                    fix_hint=(
                        f"Subset '{filepath}' to include only needed glyphs. "
                        f"Convert to WOFF2 for better compression. "
                        f"Use `pyftsubset` from fonttools: "
                        f"`pyftsubset {filepath} --unicodes='U+0000-00FF' --flavor=woff2`"
                    ),
                    saving_estimate=f"~{_format_bytes(int(file_size * 0.6))} with subsetting + WOFF2",
                    effort=Effort.MEDIUM,
                    raw=entry,
                ))
            elif file_size > 200_000:  # > 200 KB
                findings.append(Finding(
                    tool="fonttools",
                    severity=Severity.MEDIUM,
                    category=Category.FONT,
                    file=filepath,
                    rule_id="medium-font-file",
                    rule_name="Medium font file (>200 KB)",
                    message=(
                        f"'{filepath}' ({family_name}, {font_format}) is "
                        f"{_format_bytes(file_size)} with {num_glyphs} glyphs."
                    ),
                    metric="font_file_size",
                    current_value=float(file_size),
                    target_value=100000.0,
                    fix_hint=(
                        f"Consider subsetting '{filepath}' to reduce its size. "
                        f"Use `pyftsubset` to strip unused glyphs."
                    ),
                    saving_estimate=f"~{_format_bytes(int(file_size * 0.4))} with subsetting",
                    effort=Effort.MEDIUM,
                    raw=entry,
                ))

            # Not WOFF2 format
            if font_format in ("TrueType", "OpenType", "CFF") and filepath.endswith(
                (".ttf", ".otf")
            ):
                findings.append(Finding(
                    tool="fonttools",
                    severity=Severity.MEDIUM,
                    category=Category.FONT,
                    file=filepath,
                    rule_id="not-woff2",
                    rule_name="Font not in WOFF2 format",
                    message=(
                        f"'{filepath}' is in {font_format} format ({_format_bytes(file_size)}). "
                        f"WOFF2 provides 30-50% better compression for web delivery."
                    ),
                    fix_hint=(
                        f"Convert to WOFF2: `pyftsubset {filepath} --flavor=woff2 "
                        f"--output-file={filepath.rsplit('.', 1)[0]}.woff2`"
                    ),
                    saving_estimate=f"~{_format_bytes(int(file_size * 0.35))} with WOFF2 conversion",
                    effort=Effort.LOW,
                    raw=entry,
                ))

            # Hinting data (useful for screens but adds weight)
            if has_hinting and file_size > 100_000:
                findings.append(Finding(
                    tool="fonttools",
                    severity=Severity.LOW,
                    category=Category.FONT,
                    file=filepath,
                    rule_id="has-hinting",
                    rule_name="Font contains hinting data",
                    message=(
                        f"'{filepath}' contains hinting instructions. "
                        f"Modern browsers and high-DPI screens rarely benefit from hinting. "
                        f"Removing hints can reduce file size by 10-30%."
                    ),
                    fix_hint=(
                        f"Remove hinting with: `pyftsubset {filepath} --no-hinting "
                        f"--desubroutinize --flavor=woff2`"
                    ),
                    saving_estimate=f"~{_format_bytes(int(file_size * 0.15))} by removing hints",
                    effort=Effort.LOW,
                    raw=entry,
                ))

            # High subsetting potential
            if subsetting_potential > 0.5 and num_glyphs > 500:
                findings.append(Finding(
                    tool="fonttools",
                    severity=Severity.LOW,
                    category=Category.FONT,
                    file=filepath,
                    rule_id="subsetting-opportunity",
                    rule_name="Font subsetting opportunity",
                    message=(
                        f"'{filepath}' has {num_glyphs} glyphs with "
                        f"{subsetting_potential * 100:.0f}% subsetting potential. "
                        f"Most Latin-based websites need fewer than 300 glyphs."
                    ),
                    fix_hint=(
                        f"Subset to Latin range: `pyftsubset {filepath} "
                        f"--unicodes='U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,"
                        f"U+2000-206F,U+2074,U+20AC,U+2122,U+2191,U+2193,U+2212,"
                        f"U+2215,U+FEFF,U+FFFD' --flavor=woff2`"
                    ),
                    saving_estimate=f"~{_format_bytes(int(file_size * subsetting_potential))} possible",
                    effort=Effort.MEDIUM,
                    raw=entry,
                ))

        return findings
