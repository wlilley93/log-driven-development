"""Normaliser for SVGO output."""

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


class SvgoNormaliser(BaseNormaliser):
    """Convert SVGO dry-run analysis to Finding objects.

    Input shape (built by the runner):
    [
      {
        "file": "public/icons/logo.svg",
        "original_size": 12500,
        "optimized_size": 7800,
        "savings": 4700,
        "savings_pct": 37.6
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
            optimized = entry.get("optimized_size", 0)
            savings = entry.get("savings", 0)
            pct = entry.get("savings_pct", 0)

            if pct <= 5:
                # Already well-optimised, skip
                continue

            if pct > 30:
                severity = Severity.MEDIUM
                rule_id = "svg-high-optimization"
                rule_name = "SVG has high optimisation potential (>30%)"
            elif pct > 15:
                severity = Severity.LOW
                rule_id = "svg-moderate-optimization"
                rule_name = "SVG has moderate optimisation potential"
            else:
                severity = Severity.INFO
                rule_id = "svg-low-optimization"
                rule_name = "SVG has minor optimisation potential"

            findings.append(Finding(
                tool="svgo",
                severity=severity,
                category=Category.ASSET,
                file=filepath,
                rule_id=rule_id,
                rule_name=rule_name,
                message=(
                    f"SVG '{filepath}' can be reduced from {_format_bytes(original)} "
                    f"to {_format_bytes(optimized)} ({pct:.1f}% reduction)."
                ),
                metric="svg_optimization_pct",
                current_value=float(pct),
                target_value=0.0,
                fix_hint=(
                    f"Run `npx svgo {filepath}` to optimise in-place. "
                    f"SVGO removes unnecessary metadata, comments, hidden elements, "
                    f"and simplifies path data. Use `--multipass` for best results."
                ),
                saving_estimate=f"{_format_bytes(savings)} SVG reduction",
                effort=Effort.LOW,
                raw=entry,
            ))

        return findings
