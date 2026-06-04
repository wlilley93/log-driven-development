"""Normaliser for size-limit output."""

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


class SizeLimitNormaliser(BaseNormaliser):
    """Convert size-limit JSON output to Finding objects.

    size-limit --json shape:
    [
      {
        "name": "dist/index.js",
        "passed": true,
        "size": 25600,
        "sizeLimit": 30000,
        "running": 150,
        "loading": 50
      },
      {
        "name": "dist/styles.css",
        "passed": false,
        "size": 45000,
        "sizeLimit": 30000
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

            name = entry.get("name", "unknown")
            passed = entry.get("passed", True)
            size = entry.get("size", 0)
            size_limit = entry.get("sizeLimit")
            running_time = entry.get("running")
            loading_time = entry.get("loading")

            if not passed and size_limit is not None:
                over_pct = ((size - size_limit) / size_limit * 100) if size_limit > 0 else 0
                findings.append(Finding(
                    tool="size-limit",
                    severity=Severity.HIGH,
                    category=Category.BUNDLE,
                    file=name,
                    rule_id="budget-exceeded",
                    rule_name="Size budget exceeded",
                    message=(
                        f"'{name}' is {_format_bytes(size)} which exceeds the "
                        f"{_format_bytes(size_limit)} budget by {over_pct:.0f}%."
                    ),
                    metric="bundle_size",
                    current_value=float(size),
                    target_value=float(size_limit),
                    fix_hint=(
                        f"Reduce '{name}' by {_format_bytes(size - size_limit)} to meet budget. "
                        f"Try tree-shaking, code splitting, or replacing heavy dependencies."
                    ),
                    saving_estimate=f"{_format_bytes(size - size_limit)} over budget",
                    effort=Effort.MEDIUM,
                    raw=entry,
                ))
            elif passed and size > 0:
                headroom = size_limit - size if size_limit else None
                msg_parts = [f"'{name}' is {_format_bytes(size)}"]
                if size_limit:
                    msg_parts.append(
                        f"within the {_format_bytes(size_limit)} budget "
                        f"({_format_bytes(headroom)} headroom)"
                    )
                if running_time is not None:
                    msg_parts.append(f"estimated running time: {running_time}ms")
                if loading_time is not None:
                    msg_parts.append(f"loading time: {loading_time}ms")

                findings.append(Finding(
                    tool="size-limit",
                    severity=Severity.INFO,
                    category=Category.BUNDLE,
                    file=name,
                    rule_id="budget-ok",
                    rule_name="Size budget within limit",
                    message=". ".join(msg_parts) + ".",
                    metric="bundle_size",
                    current_value=float(size),
                    target_value=float(size_limit) if size_limit else None,
                    effort=Effort.LOW,
                    raw=entry,
                ))

        return findings
