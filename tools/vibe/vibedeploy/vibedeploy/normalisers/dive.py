"""Normaliser for dive JSON output."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser

# Efficiency thresholds
_EFFICIENCY_CRITICAL = 0.6  # Below 60% is high severity
_EFFICIENCY_WARN = 0.85     # Below 85% is medium severity

# Wasted space thresholds (bytes)
_WASTED_HIGH = 100 * 1024 * 1024   # 100 MB
_WASTED_MEDIUM = 20 * 1024 * 1024  # 20 MB


class DiveNormaliser(BaseNormaliser):
    tool_name = "dive"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings: list[Finding] = []

        if not isinstance(raw_data, dict):
            return findings

        # Dive CI JSON has an "image" key with efficiency data
        image = raw_data.get("image", {})
        results = raw_data.get("results", raw_data)

        efficiency = image.get("efficiencyScore", results.get("efficiencyScore"))
        wasted_bytes = image.get("wastedBytes", results.get("wastedBytes", 0))
        size_bytes = image.get("sizeBytes", results.get("sizeBytes", 0))

        # Check efficiency score
        if efficiency is not None:
            if efficiency < _EFFICIENCY_CRITICAL:
                findings.append(Finding(
                    tool=self.tool_name,
                    severity=Severity.HIGH,
                    category=Category.DOCKER,
                    file="Dockerfile",
                    rule_id="dive-low-efficiency",
                    rule_name="Low Image Efficiency",
                    message=(
                        f"Docker image efficiency is {efficiency:.1%}, "
                        f"below the {_EFFICIENCY_CRITICAL:.0%} threshold. "
                        f"Wasted space: {_format_bytes(wasted_bytes)}."
                    ),
                    blocks_deploy=False,
                    effort=Effort.MEDIUM,
                    fix_hint="Combine RUN instructions, use multi-stage builds, and remove unnecessary files in the same layer",
                    raw=raw_data,
                ))
            elif efficiency < _EFFICIENCY_WARN:
                findings.append(Finding(
                    tool=self.tool_name,
                    severity=Severity.MEDIUM,
                    category=Category.DOCKER,
                    file="Dockerfile",
                    rule_id="dive-moderate-efficiency",
                    rule_name="Moderate Image Efficiency",
                    message=(
                        f"Docker image efficiency is {efficiency:.1%}, "
                        f"below the {_EFFICIENCY_WARN:.0%} threshold. "
                        f"Wasted space: {_format_bytes(wasted_bytes)}."
                    ),
                    blocks_deploy=False,
                    effort=Effort.LOW,
                    fix_hint="Review layers for unnecessary files and consider combining RUN statements",
                    raw=raw_data,
                ))

        # Check wasted space independently
        if wasted_bytes > _WASTED_HIGH:
            findings.append(Finding(
                tool=self.tool_name,
                severity=Severity.HIGH,
                category=Category.DOCKER,
                file="Dockerfile",
                rule_id="dive-high-waste",
                rule_name="High Wasted Space",
                message=(
                    f"Docker image has {_format_bytes(wasted_bytes)} of wasted space "
                    f"out of {_format_bytes(size_bytes)} total."
                ),
                blocks_deploy=False,
                effort=Effort.MEDIUM,
                fix_hint="Use multi-stage builds and clean up package manager caches in the same RUN layer",
                raw=raw_data,
            ))
        elif wasted_bytes > _WASTED_MEDIUM:
            findings.append(Finding(
                tool=self.tool_name,
                severity=Severity.LOW,
                category=Category.DOCKER,
                file="Dockerfile",
                rule_id="dive-moderate-waste",
                rule_name="Moderate Wasted Space",
                message=(
                    f"Docker image has {_format_bytes(wasted_bytes)} of wasted space "
                    f"out of {_format_bytes(size_bytes)} total."
                ),
                blocks_deploy=False,
                effort=Effort.LOW,
                fix_hint="Clean up temporary files and caches in the same layer they are created",
                raw=raw_data,
            ))

        # Check per-layer results if available
        pass_results = results.get("pass", []) if isinstance(results, dict) else []
        fail_results = results.get("fail", []) if isinstance(results, dict) else []

        for fail_item in fail_results:
            if isinstance(fail_item, dict):
                rule = fail_item.get("rule", "unknown")
                message = fail_item.get("message", f"Dive check failed: {rule}")
                findings.append(Finding(
                    tool=self.tool_name,
                    severity=Severity.MEDIUM,
                    category=Category.DOCKER,
                    file="Dockerfile",
                    rule_id=f"dive-{rule}",
                    rule_name=rule,
                    message=message,
                    blocks_deploy=False,
                    effort=Effort.LOW,
                    raw=fail_item,
                ))

        return findings


def _format_bytes(num_bytes: int | float) -> str:
    """Format bytes into a human-readable string."""
    if num_bytes >= 1024 * 1024 * 1024:
        return f"{num_bytes / (1024 ** 3):.1f} GB"
    if num_bytes >= 1024 * 1024:
        return f"{num_bytes / (1024 ** 2):.1f} MB"
    if num_bytes >= 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes} bytes"
