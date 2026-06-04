"""Normaliser for bundlewatch output."""

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


def _parse_size_string(size_str: str) -> float | None:
    """Parse a size string like '250KB' or '1.2MB' to bytes."""
    if not isinstance(size_str, str):
        return None

    size_str = size_str.strip().upper()

    try:
        if size_str.endswith("MB"):
            return float(size_str[:-2].strip()) * 1_048_576
        if size_str.endswith("KB"):
            return float(size_str[:-2].strip()) * 1024
        if size_str.endswith("B"):
            return float(size_str[:-1].strip())
        return float(size_str)
    except (ValueError, TypeError):
        return None


class BundlewatchNormaliser(BaseNormaliser):
    """Convert bundlewatch JSON output to Finding objects.

    bundlewatch --ci output shape (varies by version):
    {
      "status": "fail",
      "files": [
        {
          "filePath": "dist/main.js",
          "maxSize": "250KB",
          "size": 310000,
          "status": "fail",
          "message": "310KB > maxSize 250KB (gzip)"
        },
        {
          "filePath": "dist/vendor.js",
          "maxSize": "500KB",
          "size": 200000,
          "status": "pass",
          "message": "200KB < maxSize 500KB (gzip)"
        }
      ]
    }

    Some versions may also report as an array directly.
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, (dict, list)):
            return []

        findings: list[Finding] = []

        # Handle both dict and list forms
        if isinstance(raw_data, list):
            files = raw_data
        else:
            files = raw_data.get("files", raw_data.get("results", []))

        for entry in files:
            if not isinstance(entry, dict):
                continue

            file_path = entry.get("filePath", entry.get("path", "unknown"))
            max_size_str = entry.get("maxSize", "")
            size = entry.get("size", 0)
            status = entry.get("status", "unknown")
            message = entry.get("message", "")

            # Normalise size to bytes
            if isinstance(size, str):
                size = _parse_size_string(size) or 0
            max_size = _parse_size_string(max_size_str) if max_size_str else None

            if status == "fail":
                # Budget exceeded
                over_amount = (size - max_size) if max_size else size
                over_pct = ((size - max_size) / max_size * 100) if max_size and max_size > 0 else 0

                # Severity based on how far over budget
                if over_pct > 50:
                    severity = Severity.CRITICAL
                elif over_pct > 20:
                    severity = Severity.HIGH
                else:
                    severity = Severity.MEDIUM

                findings.append(Finding(
                    tool="bundlewatch",
                    severity=severity,
                    category=Category.BUNDLE,
                    file=file_path,
                    rule_id="budget-exceeded",
                    rule_name="Bundle size budget exceeded",
                    message=(
                        f"'{file_path}' is {_format_bytes(size)} which exceeds "
                        f"the {max_size_str} budget"
                        f" by {over_pct:.0f}%." if max_size else "."
                    ),
                    metric="bundle_size",
                    current_value=float(size),
                    target_value=float(max_size) if max_size else None,
                    fix_hint=(
                        f"Reduce '{file_path}' by {_format_bytes(over_amount)} to meet "
                        f"the {max_size_str} budget. Try code splitting, tree-shaking, "
                        f"or replacing heavy dependencies."
                    ),
                    saving_estimate=f"~{_format_bytes(over_amount)} over budget",
                    effort=_effort_from_over_pct(over_pct),
                    raw=entry,
                ))

            elif status == "pass":
                # Within budget — informational
                headroom = (max_size - size) if max_size else None
                headroom_str = f" ({_format_bytes(headroom)} headroom)" if headroom else ""

                findings.append(Finding(
                    tool="bundlewatch",
                    severity=Severity.INFO,
                    category=Category.BUNDLE,
                    file=file_path,
                    rule_id="budget-ok",
                    rule_name="Bundle size within budget",
                    message=(
                        f"'{file_path}' is {_format_bytes(size)} — within "
                        f"the {max_size_str} budget{headroom_str}."
                    ),
                    metric="bundle_size",
                    current_value=float(size),
                    target_value=float(max_size) if max_size else None,
                    effort=Effort.LOW,
                    raw=entry,
                ))

            else:
                # Unknown status — still report
                findings.append(Finding(
                    tool="bundlewatch",
                    severity=Severity.LOW,
                    category=Category.BUNDLE,
                    file=file_path,
                    rule_id="budget-unknown",
                    rule_name="Bundle size status unknown",
                    message=message or f"'{file_path}' is {_format_bytes(size)}.",
                    metric="bundle_size",
                    current_value=float(size),
                    effort=Effort.LOW,
                    raw=entry,
                ))

        return findings


def _effort_from_over_pct(over_pct: float) -> Effort:
    """Map over-budget percentage to effort level."""
    if over_pct > 50:
        return Effort.HIGH
    if over_pct > 20:
        return Effort.MEDIUM
    return Effort.LOW
