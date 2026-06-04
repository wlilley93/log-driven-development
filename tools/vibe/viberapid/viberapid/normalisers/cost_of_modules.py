"""Normaliser for cost-of-modules output."""

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


class CostOfModulesNormaliser(BaseNormaliser):
    """Convert cost-of-modules JSON output to Finding objects.

    cost-of-modules --json shape:
    [
      {"name": "lodash", "children": 0, "size": 4567890},
      {"name": "express", "children": 55, "size": 2345678},
      ...
    ]
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, list):
            return []

        findings: list[Finding] = []

        # Sort by size descending, take top 10
        sorted_modules = sorted(
            [m for m in raw_data if isinstance(m, dict) and m.get("size", 0) > 0],
            key=lambda m: m.get("size", 0),
            reverse=True,
        )[:10]

        total_size = sum(m.get("size", 0) for m in raw_data if isinstance(m, dict))

        for rank, module in enumerate(sorted_modules, start=1):
            name = module.get("name", "unknown")
            size = module.get("size", 0)
            children = module.get("children", 0)
            pct = (size / total_size * 100) if total_size > 0 else 0

            if size > 10_485_760:  # > 10 MB
                severity = Severity.HIGH
            elif size > 5_242_880:  # > 5 MB
                severity = Severity.MEDIUM
            elif size > 1_048_576:  # > 1 MB
                severity = Severity.LOW
            else:
                severity = Severity.INFO

            findings.append(Finding(
                tool="cost-of-modules",
                severity=severity,
                category=Category.BUNDLE,
                file="node_modules",
                rule_id=f"large-module-{rank}",
                rule_name=f"Large node_module (#{rank})",
                message=(
                    f"'{name}' occupies {_format_bytes(size)} on disk "
                    f"({pct:.1f}% of node_modules) with {children} sub-dependencies."
                ),
                metric="module_disk_size",
                current_value=float(size),
                fix_hint=(
                    f"Evaluate whether '{name}' can be replaced with a lighter alternative "
                    f"or if its {children} transitive dependencies can be deduplicated."
                ),
                saving_estimate=f"{_format_bytes(size)} disk space",
                effort=Effort.MEDIUM,
                raw=module,
            ))

        return findings
