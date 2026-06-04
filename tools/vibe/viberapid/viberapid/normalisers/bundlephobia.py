"""Normaliser for bundlephobia output."""

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
    return f"{size_bytes} B"


class BundlephobiaNormaliser(BaseNormaliser):
    """Convert bundlephobia-cli output to Finding objects.

    Input is a list of dicts, each representing one package analysis:
    [
      {
        "name": "lodash",
        "version": "4.17.21",
        "size": 72048,
        "gzip": 25200,
        "error": null
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
            version = entry.get("version", "")
            size = entry.get("size", 0)
            gzip_size = entry.get("gzip", 0)
            error = entry.get("error")

            if error:
                continue

            display_size = gzip_size if gzip_size > 0 else size
            if display_size <= 0:
                continue

            # Severity based on gzip (or raw) size
            if display_size > 102_400:  # >100 KB
                severity = Severity.HIGH
                rule_id = "large-dependency"
                rule_name = "Large dependency (>100 KB)"
            elif display_size > 51_200:  # >50 KB
                severity = Severity.MEDIUM
                rule_id = "medium-dependency"
                rule_name = "Medium-large dependency (>50 KB)"
            else:
                severity = Severity.LOW
                rule_id = "small-dependency"
                rule_name = "Dependency size info"

            version_str = f"@{version}" if version else ""
            findings.append(Finding(
                tool="bundlephobia",
                severity=severity,
                category=Category.BUNDLE,
                file="package.json",
                rule_id=rule_id,
                rule_name=rule_name,
                message=(
                    f"'{name}{version_str}' adds {_format_bytes(size)} "
                    f"(minified) / {_format_bytes(gzip_size)} (gzipped) to the bundle."
                ),
                metric="bundle_size_gzip",
                current_value=float(gzip_size),
                target_value=51200.0,
                fix_hint=_get_fix_hint(name, gzip_size),
                saving_estimate=_estimate_saving(name, gzip_size),
                effort=Effort.MEDIUM if gzip_size > 51_200 else Effort.LOW,
                raw=entry,
            ))

        return findings


def _get_fix_hint(name: str, gzip_size: int) -> str:
    """Generate a relevant fix hint based on the package."""
    well_known_alternatives = {
        "moment": "Replace 'moment' with 'dayjs' (~2 KB gzip) or 'date-fns' (tree-shakeable).",
        "lodash": "Replace 'lodash' with 'lodash-es' for tree-shaking, or import specific functions: `import debounce from 'lodash/debounce'`.",
        "underscore": "Replace 'underscore' with native ES methods or 'lodash-es' for tree-shaking.",
        "rxjs": "Ensure RxJS deep imports are used (e.g., `import { map } from 'rxjs/operators'`) for tree-shaking.",
        "axios": "Consider replacing 'axios' with the native `fetch()` API (available in Node 18+).",
        "jquery": "Replace jQuery with native DOM APIs (`document.querySelector`, `fetch`, etc.).",
    }

    if name in well_known_alternatives:
        return well_known_alternatives[name]

    if gzip_size > 102_400:
        return (
            f"Consider whether '{name}' can be replaced with a lighter alternative, "
            f"loaded lazily via dynamic import(), or moved to a CDN."
        )

    return (
        f"Check if '{name}' supports tree-shaking. "
        f"Use named imports instead of default imports where possible."
    )


def _estimate_saving(name: str, gzip_size: int) -> str:
    """Estimate potential savings."""
    well_known_savings = {
        "moment": "~65 KB gzip saved by switching to dayjs",
        "lodash": "~20-60 KB gzip saved via tree-shaking or lodash-es",
        "jquery": "~30 KB gzip saved by using native APIs",
    }

    if name in well_known_savings:
        return well_known_savings[name]

    if gzip_size > 102_400:
        return f"~{_format_bytes(int(gzip_size * 0.5))} potential savings with a lighter alternative"

    return f"{_format_bytes(gzip_size)} bundle weight"
