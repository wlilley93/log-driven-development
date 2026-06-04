"""Normaliser for gzip size analysis output."""

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


class GzipSizeNormaliser(BaseNormaliser):
    """Convert gzip compression analysis to Finding objects.

    Input shape (built by the runner):
    [
      {
        "file": "dist/main.js",
        "original_size": 450000,
        "gzip_size": 125000,
        "compression_ratio": 72.2,
        "headroom_pct": 0
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
            original = entry.get("original_size", 0)
            gzip_size = entry.get("gzip_size", 0)
            ratio = entry.get("compression_ratio", 0)

            if original <= 0 or gzip_size <= 0:
                continue

            # Report files that don't compress well (ratio < 50%)
            if ratio < 30:
                severity = Severity.MEDIUM
                rule_id = "poor-compression"
                rule_name = "Poor gzip compression ratio"
                message = (
                    f"'{filepath}' compresses poorly: {_format_bytes(original)} -> "
                    f"{_format_bytes(gzip_size)} ({ratio:.1f}% reduction). "
                    f"This may indicate already-compressed content or binary data."
                )
                fix_hint = (
                    f"'{filepath}' does not compress well with gzip. If this is a "
                    f"JavaScript/CSS file, check for embedded binary data or large "
                    f"inline data URIs. Consider serving pre-compressed with Brotli."
                )
            elif gzip_size > 204_800:  # > 200 KB gzipped
                severity = Severity.MEDIUM
                rule_id = "large-gzipped"
                rule_name = "Large file even after gzip"
                message = (
                    f"'{filepath}' is still {_format_bytes(gzip_size)} after gzip "
                    f"(from {_format_bytes(original)}, {ratio:.1f}% reduction). "
                    f"Consider code splitting or tree-shaking."
                )
                fix_hint = (
                    f"Even with gzip, '{filepath}' is over 200 KB. Split the bundle "
                    f"into smaller chunks, tree-shake unused code, or lazy-load modules."
                )
            elif gzip_size > 102_400:  # > 100 KB gzipped
                severity = Severity.LOW
                rule_id = "moderate-gzipped"
                rule_name = "Moderate gzipped file size"
                message = (
                    f"'{filepath}': {_format_bytes(original)} -> "
                    f"{_format_bytes(gzip_size)} gzipped ({ratio:.1f}% reduction)."
                )
                fix_hint = (
                    f"Consider Brotli compression for '{filepath}' — "
                    f"typically 15-20% smaller than gzip at similar CPU cost."
                )
            else:
                severity = Severity.INFO
                rule_id = "gzip-info"
                rule_name = "Gzip compression info"
                message = (
                    f"'{filepath}': {_format_bytes(original)} -> "
                    f"{_format_bytes(gzip_size)} gzipped ({ratio:.1f}% reduction)."
                )
                fix_hint = "File compresses well. Consider Brotli for marginal additional savings."

            findings.append(Finding(
                tool="gzip-size",
                severity=severity,
                category=Category.COMPRESSION,
                file=filepath,
                rule_id=rule_id,
                rule_name=rule_name,
                message=message,
                metric="gzip_compression_ratio",
                current_value=float(ratio),
                target_value=60.0,
                fix_hint=fix_hint,
                saving_estimate=f"{_format_bytes(original - gzip_size)} with gzip",
                effort=Effort.LOW,
                raw=entry,
            ))

        return findings
