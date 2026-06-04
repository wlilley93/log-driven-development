"""Normaliser for esbuild benchmark output."""

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


class EsbuildBenchNormaliser(BaseNormaliser):
    """Convert esbuild benchmark comparison data to Finding objects.

    Input shape (built by the runner):
    {
      "entry_point": "src/index.ts",
      "esbuild_output_size": 125000,
      "current_dist_size": 310000,
      "gap": 185000,
      "gap_pct": 59.7,
      "esbuild_time_ms": 42,
      "output_files": [
        {"path": "out.js", "size": 125000}
      ],
      "current_files": [
        {"path": "dist/main.js", "size": 310000}
      ]
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        findings: list[Finding] = []

        entry_point = raw_data.get("entry_point", "unknown")
        esbuild_size = raw_data.get("esbuild_output_size", 0)
        current_size = raw_data.get("current_dist_size", 0)
        gap = raw_data.get("gap", 0)
        gap_pct = raw_data.get("gap_pct", 0)
        esbuild_time_ms = raw_data.get("esbuild_time_ms")

        # Overall gap finding
        if gap > 0 and current_size > 0:
            severity = _classify_gap(gap_pct)

            findings.append(Finding(
                tool="esbuild-bench",
                severity=severity,
                category=Category.BUNDLE,
                file=entry_point,
                rule_id="bundle-gap",
                rule_name="Bundle size gap vs optimal",
                message=(
                    f"Current dist is {_format_bytes(current_size)} but esbuild "
                    f"produces {_format_bytes(esbuild_size)} — a gap of "
                    f"{_format_bytes(gap)} ({gap_pct:.1f}%)."
                ),
                metric="bundle_size_gap",
                current_value=float(current_size),
                target_value=float(esbuild_size),
                fix_hint=_get_gap_fix_hint(gap_pct),
                saving_estimate=f"~{_format_bytes(gap)} potential savings by closing the gap",
                effort=_effort_for_gap(gap_pct),
                raw=raw_data,
            ))
        elif current_size > 0 and gap <= 0:
            # Current build is already at or better than esbuild baseline
            findings.append(Finding(
                tool="esbuild-bench",
                severity=Severity.INFO,
                category=Category.BUNDLE,
                file=entry_point,
                rule_id="bundle-optimal",
                rule_name="Bundle size near optimal",
                message=(
                    f"Current dist ({_format_bytes(current_size)}) is at or below "
                    f"esbuild's baseline ({_format_bytes(esbuild_size)}). "
                    f"Build output is well optimised."
                ),
                metric="bundle_size_gap",
                current_value=float(current_size),
                target_value=float(esbuild_size),
                effort=Effort.LOW,
                raw=raw_data,
            ))

        # Per-file comparison if output_files and current_files are present
        output_files = raw_data.get("output_files", [])
        current_files = raw_data.get("current_files", [])

        for current_file in current_files:
            if not isinstance(current_file, dict):
                continue
            path = current_file.get("path", "")
            file_size = current_file.get("size", 0)

            if file_size > 250 * 1024:
                findings.append(Finding(
                    tool="esbuild-bench",
                    severity=Severity.MEDIUM,
                    category=Category.BUNDLE,
                    file=path,
                    rule_id="large-output-file",
                    rule_name="Large output file in dist",
                    message=(
                        f"Output file '{path}' is {_format_bytes(file_size)}. "
                        f"Consider splitting it into smaller chunks."
                    ),
                    metric="output_file_size",
                    current_value=float(file_size),
                    target_value=250 * 1024.0,
                    fix_hint=(
                        f"Split '{path}' using code splitting or dynamic imports "
                        f"to reduce initial load size."
                    ),
                    effort=Effort.MEDIUM,
                    raw=current_file,
                ))

        # Build time finding
        if esbuild_time_ms is not None and esbuild_time_ms > 0:
            findings.append(Finding(
                tool="esbuild-bench",
                severity=Severity.INFO,
                category=Category.BUNDLE,
                file=entry_point,
                rule_id="esbuild-build-time",
                rule_name="esbuild benchmark build time",
                message=(
                    f"esbuild built '{entry_point}' in {esbuild_time_ms}ms "
                    f"producing {_format_bytes(esbuild_size)}."
                ),
                metric="build_time_ms",
                current_value=float(esbuild_time_ms),
                effort=Effort.LOW,
                raw={"time_ms": esbuild_time_ms, "output_size": esbuild_size},
            ))

        return findings


def _classify_gap(gap_pct: float) -> Severity:
    """Classify severity based on the percentage gap."""
    if gap_pct > 100:
        return Severity.CRITICAL
    if gap_pct > 50:
        return Severity.HIGH
    if gap_pct > 20:
        return Severity.MEDIUM
    return Severity.LOW


def _effort_for_gap(gap_pct: float) -> Effort:
    """Map gap percentage to expected effort."""
    if gap_pct > 50:
        return Effort.HIGH
    if gap_pct > 20:
        return Effort.MEDIUM
    return Effort.LOW


def _get_gap_fix_hint(gap_pct: float) -> str:
    """Generate a fix hint based on the gap percentage."""
    if gap_pct > 100:
        return (
            "The current build is more than double the optimal size. "
            "Investigate whether minification and tree-shaking are fully enabled. "
            "Check for accidentally bundled development code, source maps in dist, "
            "or duplicate polyfills."
        )

    if gap_pct > 50:
        return (
            "Significant room for optimisation. Check that dead code elimination "
            "and tree-shaking are working. Audit for duplicate dependencies "
            "and consider switching to more efficient alternatives for heavy packages."
        )

    if gap_pct > 20:
        return (
            "Moderate optimisation gap. Check for unused polyfills, "
            "ensure sideEffects is set correctly in package.json, "
            "and verify that CSS/font assets are not bundled unnecessarily."
        )

    return (
        "Build output is close to optimal. Minor gains may come from "
        "fine-tuning minification settings or removing small unused utilities."
    )
