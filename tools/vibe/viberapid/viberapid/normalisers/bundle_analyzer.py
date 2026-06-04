"""Normaliser for webpack-bundle-analyzer output."""

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


class BundleAnalyzerNormaliser(BaseNormaliser):
    """Convert webpack stats.json data to Finding objects.

    Input shape (webpack stats.json):
    {
      "assets": [
        {
          "name": "main.abc123.js",
          "size": 524288,
          "chunks": [0],
          "chunkNames": ["main"],
          "emitted": true
        }
      ],
      "chunks": [
        {
          "id": 0,
          "names": ["main"],
          "size": 524288,
          "modules": [
            {
              "name": "./src/index.js",
              "size": 2048,
              "id": 0
            }
          ]
        }
      ]
    }
    """

    # Thresholds in bytes
    CRITICAL_THRESHOLD = 500 * 1024   # 500 KB
    HIGH_THRESHOLD = 250 * 1024       # 250 KB
    MEDIUM_THRESHOLD = 100 * 1024     # 100 KB

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        findings: list[Finding] = []

        # Analyse assets (output files)
        assets = raw_data.get("assets", [])
        for asset in assets:
            if not isinstance(asset, dict):
                continue

            name = asset.get("name", "unknown")
            size = asset.get("size", 0)

            if not isinstance(size, (int, float)) or size <= 0:
                continue

            # Skip non-JS/CSS assets (images, fonts, etc.)
            if not _is_bundle_asset(name):
                continue

            severity, rule_id, rule_name = _classify_asset_size(size)
            if severity is None:
                # Under all thresholds — emit INFO
                findings.append(Finding(
                    tool="bundle-analyzer",
                    severity=Severity.INFO,
                    category=Category.BUNDLE,
                    file=name,
                    rule_id="asset-size-ok",
                    rule_name="Asset size within limits",
                    message=f"Asset '{name}' is {_format_bytes(size)}.",
                    metric="asset_size",
                    current_value=float(size),
                    target_value=float(self.MEDIUM_THRESHOLD),
                    effort=Effort.LOW,
                    raw=asset,
                ))
                continue

            threshold = _threshold_for_severity(severity)
            findings.append(Finding(
                tool="bundle-analyzer",
                severity=severity,
                category=Category.BUNDLE,
                file=name,
                rule_id=rule_id,
                rule_name=rule_name,
                message=(
                    f"Asset '{name}' is {_format_bytes(size)} which exceeds "
                    f"the {_format_bytes(threshold)} threshold."
                ),
                metric="asset_size",
                current_value=float(size),
                target_value=float(threshold),
                fix_hint=_get_asset_fix_hint(name, size, severity),
                saving_estimate=_estimate_asset_saving(name, size, severity),
                effort=_effort_for_severity(severity),
                raw=asset,
            ))

        # Analyse large modules within chunks
        chunks = raw_data.get("chunks", [])
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue

            chunk_names = chunk.get("names", [])
            chunk_label = chunk_names[0] if chunk_names else f"chunk-{chunk.get('id', '?')}"
            modules = chunk.get("modules", [])

            for module in modules:
                if not isinstance(module, dict):
                    continue

                mod_name = module.get("name", "unknown")
                mod_size = module.get("size", 0)

                if not isinstance(mod_size, (int, float)) or mod_size <= 0:
                    continue

                # Only flag large individual modules (>50 KB is notable)
                if mod_size > 50 * 1024:
                    severity = Severity.MEDIUM if mod_size > 100 * 1024 else Severity.LOW
                    findings.append(Finding(
                        tool="bundle-analyzer",
                        severity=severity,
                        category=Category.BUNDLE,
                        file=mod_name,
                        rule_id="large-module",
                        rule_name="Large module in bundle",
                        message=(
                            f"Module '{mod_name}' in chunk '{chunk_label}' "
                            f"is {_format_bytes(mod_size)}."
                        ),
                        metric="module_size",
                        current_value=float(mod_size),
                        fix_hint=(
                            f"Consider code-splitting '{mod_name}' via dynamic import() "
                            f"or replacing it with a lighter alternative."
                        ),
                        effort=Effort.MEDIUM,
                        raw={"module": mod_name, "size": mod_size, "chunk": chunk_label},
                    ))

        return findings


def _is_bundle_asset(name: str) -> bool:
    """Check if a file is a JS or CSS bundle asset."""
    lower = name.lower()
    return lower.endswith((".js", ".mjs", ".cjs", ".css"))


def _classify_asset_size(
    size: int | float,
) -> tuple[Severity | None, str, str]:
    """Classify asset severity based on size thresholds."""
    if size > 500 * 1024:
        return Severity.CRITICAL, "oversized-asset-critical", "Oversized asset (>500 KB)"
    if size > 250 * 1024:
        return Severity.HIGH, "oversized-asset-high", "Large asset (>250 KB)"
    if size > 100 * 1024:
        return Severity.MEDIUM, "oversized-asset-medium", "Medium-large asset (>100 KB)"
    return None, "", ""


def _threshold_for_severity(severity: Severity) -> float:
    """Return the byte threshold for a given severity."""
    return {
        Severity.CRITICAL: 500 * 1024,
        Severity.HIGH: 250 * 1024,
        Severity.MEDIUM: 100 * 1024,
    }.get(severity, 100 * 1024)


def _effort_for_severity(severity: Severity) -> Effort:
    """Map severity to expected fix effort."""
    if severity >= Severity.HIGH:
        return Effort.HIGH
    if severity == Severity.MEDIUM:
        return Effort.MEDIUM
    return Effort.LOW


def _get_asset_fix_hint(name: str, size: int | float, severity: Severity) -> str:
    """Generate a fix hint for an oversized asset."""
    lower = name.lower()

    if lower.endswith(".css"):
        return (
            f"CSS asset '{name}' is {_format_bytes(size)}. "
            f"Use PurgeCSS or Tailwind's purge option to remove unused styles. "
            f"Consider splitting critical CSS from non-critical."
        )

    if severity == Severity.CRITICAL:
        return (
            f"Asset '{name}' is critically large at {_format_bytes(size)}. "
            f"Apply aggressive code splitting with dynamic import(), enable tree-shaking, "
            f"replace heavy dependencies, and ensure minification is enabled."
        )

    if severity == Severity.HIGH:
        return (
            f"Asset '{name}' is {_format_bytes(size)}. "
            f"Use dynamic import() for non-critical code paths, enable tree-shaking, "
            f"and audit large dependencies with source-map-explorer."
        )

    return (
        f"Asset '{name}' is {_format_bytes(size)}. "
        f"Consider code splitting or lazy-loading non-essential modules."
    )


def _estimate_asset_saving(name: str, size: int | float, severity: Severity) -> str:
    """Estimate potential savings from reducing asset size."""
    if severity == Severity.CRITICAL:
        target = 250 * 1024
        saving = size - target
        return (
            f"~{_format_bytes(saving)} potential savings by splitting "
            f"'{name}' to under 250 KB"
        )

    if severity == Severity.HIGH:
        target = 100 * 1024
        saving = size - target
        return (
            f"~{_format_bytes(saving)} potential savings by optimising "
            f"'{name}' to under 100 KB"
        )

    target = 50 * 1024
    saving = size - target
    return f"~{_format_bytes(saving)} potential savings by optimising '{name}'"
