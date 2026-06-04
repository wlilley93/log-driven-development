"""Normaliser for brotli size analysis output."""

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


class BrotliSizeNormaliser(BaseNormaliser):
    """Convert brotli compression analysis to Finding objects.

    Input shape (built by the runner):
    [
      {
        "file": "dist/main.js",
        "original_size": 450000,
        "gzip_size": 125000,
        "brotli_size": 105000,
        "brotli_vs_gzip_improvement": 16.0,
        "brotli_ratio": 76.7
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
            brotli_size = entry.get("brotli_size", 0)
            improvement = entry.get("brotli_vs_gzip_improvement", 0)
            brotli_ratio = entry.get("brotli_ratio", 0)

            if original <= 0 or brotli_size <= 0:
                continue

            gzip_vs_brotli_savings = gzip_size - brotli_size if gzip_size > 0 else 0

            if improvement > 20:
                severity = Severity.MEDIUM
                rule_id = "high-brotli-headroom"
                rule_name = "Significant Brotli improvement over gzip"
            elif improvement > 10:
                severity = Severity.LOW
                rule_id = "moderate-brotli-headroom"
                rule_name = "Moderate Brotli improvement over gzip"
            elif improvement > 0:
                severity = Severity.INFO
                rule_id = "minor-brotli-headroom"
                rule_name = "Minor Brotli improvement over gzip"
            else:
                continue  # No improvement to report

            findings.append(Finding(
                tool="brotli-size",
                severity=severity,
                category=Category.COMPRESSION,
                file=filepath,
                rule_id=rule_id,
                rule_name=rule_name,
                message=(
                    f"'{filepath}': Brotli compresses to {_format_bytes(brotli_size)} "
                    f"vs gzip's {_format_bytes(gzip_size)} "
                    f"({improvement:.1f}% smaller, {_format_bytes(gzip_vs_brotli_savings)} saved). "
                    f"Original size: {_format_bytes(original)}."
                ),
                metric="brotli_vs_gzip_improvement",
                current_value=float(improvement),
                target_value=0.0,
                fix_hint=(
                    f"Enable Brotli compression on your web server or CDN for '{filepath}'. "
                    f"Most modern servers (nginx, Caddy, Cloudflare, Vercel) support Brotli. "
                    f"For static assets, pre-compress with `brotli -Z {filepath}` at build time."
                ),
                saving_estimate=f"{_format_bytes(gzip_vs_brotli_savings)} over gzip",
                effort=Effort.LOW,
                raw=entry,
            ))

        return findings
