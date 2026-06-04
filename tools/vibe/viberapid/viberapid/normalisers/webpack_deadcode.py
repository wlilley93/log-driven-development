"""Normaliser for webpack dead code detection output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser


class WebpackDeadcodeNormaliser(BaseNormaliser):
    """Convert webpack dead code analysis results to Finding objects.

    Input shape (built by the runner from webpack-deadcode-plugin or custom analysis):
    {
      "unused_files": [
        "src/utils/deprecated.ts",
        "src/components/OldWidget.tsx"
      ],
      "unused_exports": {
        "src/index.ts": ["unusedHelper", "legacyFunc"],
        "src/utils.ts": ["formatOld"]
      },
      "total_unused_files": 2,
      "total_unused_exports": 3
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        findings: list[Finding] = []

        # Unused files
        unused_files = raw_data.get("unused_files", [])
        for filepath in unused_files:
            if not isinstance(filepath, str):
                continue

            severity = _severity_for_file(filepath)
            findings.append(Finding(
                tool="webpack-deadcode",
                severity=severity,
                category=Category.CODE,
                file=filepath,
                rule_id="unused-file",
                rule_name="Unused file (webpack dead code)",
                message=(
                    f"File '{filepath}' is not imported by any module in the webpack "
                    f"dependency graph and contributes dead code to the build."
                ),
                fix_hint=(
                    f"Delete '{filepath}' if it is truly unused, or add it to "
                    f"the webpack-deadcode-plugin exclude list if it is loaded dynamically."
                ),
                saving_estimate=_estimate_file_saving(filepath),
                effort=Effort.LOW,
                raw={"type": "unused-file", "file": filepath},
            ))

        # Unused exports
        unused_exports = raw_data.get("unused_exports", {})
        for filepath, exports in unused_exports.items():
            if not isinstance(exports, list):
                continue

            for export_name in exports:
                if not isinstance(export_name, str):
                    continue

                findings.append(Finding(
                    tool="webpack-deadcode",
                    severity=Severity.LOW,
                    category=Category.CODE,
                    file=filepath,
                    rule_id="unused-export",
                    rule_name="Unused export (webpack dead code)",
                    message=(
                        f"Export '{export_name}' in '{filepath}' is not imported "
                        f"anywhere in the webpack dependency graph."
                    ),
                    fix_hint=(
                        f"Remove the export keyword from '{export_name}' in '{filepath}', "
                        f"or delete the function/variable entirely if it is no longer needed. "
                        f"This enables tree-shaking to exclude it from the bundle."
                    ),
                    effort=Effort.LOW,
                    raw={
                        "type": "unused-export",
                        "file": filepath,
                        "export": export_name,
                    },
                ))

        # Summary finding if many unused files
        total_files = raw_data.get("total_unused_files", len(unused_files))
        total_exports = raw_data.get("total_unused_exports", 0)

        if total_files > 10 or total_exports > 20:
            findings.append(Finding(
                tool="webpack-deadcode",
                severity=Severity.MEDIUM,
                category=Category.CODE,
                file="(project)",
                rule_id="high-dead-code-count",
                rule_name="High amount of dead code",
                message=(
                    f"Found {total_files} unused files and {total_exports} unused exports. "
                    f"This indicates significant code rot that inflates the bundle."
                ),
                fix_hint=(
                    "Run a cleanup pass to remove unused files and exports. "
                    "Consider adding a lint rule (e.g., eslint-plugin-unused-imports) "
                    "to prevent accumulation of dead code."
                ),
                saving_estimate=(
                    f"Removing {total_files} unused files could significantly "
                    f"reduce bundle and build time"
                ),
                effort=Effort.MEDIUM,
                raw={
                    "total_unused_files": total_files,
                    "total_unused_exports": total_exports,
                },
            ))

        return findings


def _severity_for_file(filepath: str) -> Severity:
    """Determine severity based on the file type/location."""
    lower = filepath.lower()

    # Component files are more impactful
    if any(ext in lower for ext in (".tsx", ".jsx")):
        return Severity.MEDIUM

    # Test files being "unused" is expected
    if any(part in lower for part in (".test.", ".spec.", "__tests__", "__mocks__")):
        return Severity.INFO

    return Severity.LOW


def _estimate_file_saving(filepath: str) -> str:
    """Estimate savings from removing an unused file."""
    lower = filepath.lower()
    if any(ext in lower for ext in (".tsx", ".jsx")):
        return f"Removing unused component '{filepath}' reduces bundle and compile time"
    return f"Removing unused file '{filepath}' reduces project complexity and build time"
