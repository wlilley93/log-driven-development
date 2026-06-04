"""Normaliser for source-map-explorer output."""

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


class SourceMapExplorerNormaliser(BaseNormaliser):
    """Convert source-map-explorer JSON output to Finding objects.

    source-map-explorer --json output shape:
    {
      "results": [
        {
          "bundleName": "dist/main.js",
          "totalBytes": 524288,
          "mappedBytes": 500000,
          "unmappedBytes": 24288,
          "eolBytes": 0,
          "sourceMapCommentBytes": 0,
          "files": {
            "node_modules/lodash/lodash.js": 72048,
            "node_modules/react/index.js": 6500,
            "src/index.tsx": 2048,
            "[unmapped]": 24288
          }
        }
      ]
    }

    Or older versions may emit a flat structure:
    {
      "bundleName": "...",
      "files": {...},
      "totalBytes": ...
    }
    """

    # Thresholds for individual modules
    LARGE_MODULE_THRESHOLD = 100 * 1024   # 100 KB
    MEDIUM_MODULE_THRESHOLD = 50 * 1024   # 50 KB
    SMALL_MODULE_THRESHOLD = 20 * 1024    # 20 KB

    # Threshold for total bundle size
    BUNDLE_CRITICAL = 500 * 1024          # 500 KB
    BUNDLE_HIGH = 250 * 1024              # 250 KB

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        findings: list[Finding] = []

        # Handle both single result and results array
        results = raw_data.get("results", [])
        if not results and "files" in raw_data:
            results = [raw_data]

        for result in results:
            if not isinstance(result, dict):
                continue

            bundle_name = result.get("bundleName", "unknown")
            total_bytes = result.get("totalBytes", 0)
            unmapped_bytes = result.get("unmappedBytes", 0)
            files = result.get("files", {})

            if not isinstance(files, dict):
                continue

            # Flag total bundle size
            if total_bytes > self.BUNDLE_CRITICAL:
                findings.append(Finding(
                    tool="source-map-explorer",
                    severity=Severity.CRITICAL,
                    category=Category.BUNDLE,
                    file=bundle_name,
                    rule_id="bundle-oversized-critical",
                    rule_name="Bundle critically oversized",
                    message=(
                        f"Bundle '{bundle_name}' is {_format_bytes(total_bytes)} total. "
                        f"This significantly impacts load time."
                    ),
                    metric="bundle_total_size",
                    current_value=float(total_bytes),
                    target_value=float(self.BUNDLE_HIGH),
                    fix_hint=(
                        f"Split '{bundle_name}' into smaller chunks using dynamic import(). "
                        f"Audit the largest modules listed below for replacement or lazy-loading."
                    ),
                    saving_estimate=(
                        f"~{_format_bytes(total_bytes - self.BUNDLE_HIGH)} potential savings "
                        f"by splitting to under 250 KB"
                    ),
                    effort=Effort.HIGH,
                    raw={"bundle": bundle_name, "totalBytes": total_bytes},
                ))
            elif total_bytes > self.BUNDLE_HIGH:
                findings.append(Finding(
                    tool="source-map-explorer",
                    severity=Severity.HIGH,
                    category=Category.BUNDLE,
                    file=bundle_name,
                    rule_id="bundle-oversized-high",
                    rule_name="Bundle oversized",
                    message=(
                        f"Bundle '{bundle_name}' is {_format_bytes(total_bytes)} total."
                    ),
                    metric="bundle_total_size",
                    current_value=float(total_bytes),
                    target_value=float(self.BUNDLE_HIGH),
                    fix_hint=(
                        f"Consider code-splitting '{bundle_name}' to reduce initial load. "
                        f"Use dynamic import() for non-critical paths."
                    ),
                    saving_estimate=(
                        f"~{_format_bytes(total_bytes - 100 * 1024)} potential savings "
                        f"by optimising to under 100 KB"
                    ),
                    effort=Effort.MEDIUM,
                    raw={"bundle": bundle_name, "totalBytes": total_bytes},
                ))

            # Flag large unmapped bytes (indicates missing source maps)
            if unmapped_bytes > 10 * 1024:
                pct = (unmapped_bytes / total_bytes * 100) if total_bytes > 0 else 0
                findings.append(Finding(
                    tool="source-map-explorer",
                    severity=Severity.LOW,
                    category=Category.BUNDLE,
                    file=bundle_name,
                    rule_id="unmapped-bytes",
                    rule_name="Unmapped bytes in source map",
                    message=(
                        f"'{bundle_name}' has {_format_bytes(unmapped_bytes)} "
                        f"({pct:.1f}%) of unmapped code. Source maps may be incomplete."
                    ),
                    fix_hint=(
                        "Ensure all loaders and plugins generate complete source maps. "
                        "Set devtool to 'source-map' for full mapping."
                    ),
                    effort=Effort.LOW,
                    raw={"bundle": bundle_name, "unmappedBytes": unmapped_bytes},
                ))

            # Analyse individual files/modules within the bundle
            for module_path, module_size in files.items():
                if not isinstance(module_size, (int, float)) or module_size <= 0:
                    continue

                # Skip meta entries
                if module_path in ("[unmapped]", "[EOLs]", "[source map comment]"):
                    continue

                if module_size < self.SMALL_MODULE_THRESHOLD:
                    continue

                is_node_module = "node_modules/" in module_path
                severity = _classify_module_severity(module_size, is_node_module)
                pct = (module_size / total_bytes * 100) if total_bytes > 0 else 0
                short_name = _shorten_module_path(module_path)

                findings.append(Finding(
                    tool="source-map-explorer",
                    severity=severity,
                    category=Category.BUNDLE,
                    file=module_path,
                    rule_id="large-module" if is_node_module else "large-source-module",
                    rule_name=(
                        "Large node_modules dependency" if is_node_module
                        else "Large source module"
                    ),
                    message=(
                        f"'{short_name}' occupies {_format_bytes(module_size)} "
                        f"({pct:.1f}%) of '{bundle_name}'."
                    ),
                    metric="module_size",
                    current_value=float(module_size),
                    fix_hint=_get_module_fix_hint(module_path, module_size, is_node_module),
                    saving_estimate=(
                        f"~{_format_bytes(module_size)} if '{short_name}' is replaced or removed"
                    ),
                    effort=Effort.MEDIUM if is_node_module else Effort.HIGH,
                    raw={
                        "module": module_path,
                        "size": module_size,
                        "bundle": bundle_name,
                        "percentage": round(pct, 1),
                    },
                ))

        return findings


def _classify_module_severity(size: int | float, is_node_module: bool) -> Severity:
    """Classify module severity based on size."""
    if size > 100 * 1024:
        return Severity.HIGH
    if size > 50 * 1024:
        return Severity.MEDIUM
    return Severity.LOW


def _shorten_module_path(path: str) -> str:
    """Shorten a module path for display."""
    if "node_modules/" in path:
        parts = path.split("node_modules/")
        return parts[-1]
    if path.startswith("./"):
        return path[2:]
    return path


def _get_module_fix_hint(module_path: str, size: int | float, is_node_module: bool) -> str:
    """Generate a fix hint for a large module."""
    short = _shorten_module_path(module_path)

    # Known heavy packages
    well_known = {
        "moment": "Replace 'moment' with 'dayjs' (~2 KB) or 'date-fns' (tree-shakeable).",
        "lodash": "Use 'lodash-es' for tree-shaking or import specific functions: "
                  "`import debounce from 'lodash/debounce'`.",
        "rxjs": "Use deep imports: `import { map } from 'rxjs/operators'`.",
        "core-js": "Target modern browsers to reduce core-js polyfill size, or use "
                   "@babel/preset-env with useBuiltIns: 'usage'.",
    }

    for pkg, hint in well_known.items():
        if pkg in module_path.lower():
            return hint

    if is_node_module:
        return (
            f"Dependency '{short}' adds {_format_bytes(size)} to the bundle. "
            f"Consider a lighter alternative, lazy-loading via dynamic import(), "
            f"or checking if tree-shaking is working correctly."
        )

    return (
        f"Source module '{short}' is {_format_bytes(size)}. "
        f"Consider splitting it into smaller modules or lazy-loading "
        f"non-critical parts with dynamic import()."
    )
