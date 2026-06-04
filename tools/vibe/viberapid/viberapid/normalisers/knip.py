"""Normaliser for knip output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser


class KnipNormaliser(BaseNormaliser):
    """Convert knip JSON reporter output to Finding objects.

    knip --reporter json shape:
    {
      "files": ["src/unused.ts"],
      "issues": [
        {
          "file": "src/index.ts",
          "dependencies": ["lodash"],
          "devDependencies": [],
          "optionalPeerDependencies": [],
          "unlisted": {},
          "binaries": {},
          "unresolved": {},
          "exports": {"myFunc": [{"line": 10, "col": 1, ...}]},
          "types": {},
          "duplicates": []
        }
      ]
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        findings: list[Finding] = []

        # Unused files
        for filepath in raw_data.get("files", []):
            findings.append(Finding(
                tool="knip",
                severity=Severity.LOW,
                category=Category.CODE,
                file=filepath,
                rule_id="unused-file",
                rule_name="Unused file",
                message=f"File '{filepath}' is not imported by any other module in the project.",
                fix_hint="Delete this file if it is truly unused, or add it to knip's ignore list.",
                effort=Effort.LOW,
                raw={"type": "unused-file", "file": filepath},
            ))

        # Per-file issues
        for issue in raw_data.get("issues", []):
            filepath = issue.get("file", "unknown")

            # Unused dependencies referenced in this file
            for dep in issue.get("dependencies", []):
                findings.append(Finding(
                    tool="knip",
                    severity=Severity.MEDIUM,
                    category=Category.DEPENDENCY,
                    file=filepath,
                    rule_id="unused-dependency",
                    rule_name="Unused dependency",
                    message=f"Dependency '{dep}' is listed in package.json but not used in code.",
                    fix_hint=f"Run `npm uninstall {dep}` or verify it is used at runtime.",
                    effort=Effort.LOW,
                    raw={"type": "unused-dependency", "package": dep},
                ))

            # Unused devDependencies
            for dep in issue.get("devDependencies", []):
                findings.append(Finding(
                    tool="knip",
                    severity=Severity.LOW,
                    category=Category.DEPENDENCY,
                    file=filepath,
                    rule_id="unused-dev-dependency",
                    rule_name="Unused dev dependency",
                    message=f"Dev dependency '{dep}' is not used in the project.",
                    fix_hint=f"Run `npm uninstall {dep}` to remove it.",
                    effort=Effort.LOW,
                    raw={"type": "unused-dev-dependency", "package": dep},
                ))

            # Unused exports
            exports = issue.get("exports", {})
            for export_name, locations in exports.items():
                line = None
                col = None
                if isinstance(locations, list) and locations:
                    loc = locations[0]
                    if isinstance(loc, dict):
                        line = loc.get("line")
                        col = loc.get("col")

                findings.append(Finding(
                    tool="knip",
                    severity=Severity.LOW,
                    category=Category.CODE,
                    file=filepath,
                    rule_id="unused-export",
                    rule_name="Unused export",
                    message=f"Export '{export_name}' in '{filepath}' is not imported anywhere.",
                    line=line,
                    col=col,
                    fix_hint=(
                        f"Remove the export keyword from '{export_name}' or delete "
                        f"the function/variable if it is no longer needed."
                    ),
                    effort=Effort.LOW,
                    raw={"type": "unused-export", "name": export_name, "locations": locations},
                ))

            # Unused types
            types = issue.get("types", {})
            for type_name, locations in types.items():
                line = None
                if isinstance(locations, list) and locations:
                    loc = locations[0]
                    if isinstance(loc, dict):
                        line = loc.get("line")

                findings.append(Finding(
                    tool="knip",
                    severity=Severity.LOW,
                    category=Category.CODE,
                    file=filepath,
                    rule_id="unused-type",
                    rule_name="Unused type export",
                    message=f"Type export '{type_name}' in '{filepath}' is not imported anywhere.",
                    line=line,
                    fix_hint=f"Remove the exported type '{type_name}' if it is no longer needed.",
                    effort=Effort.LOW,
                    raw={"type": "unused-type", "name": type_name},
                ))

            # Duplicate exports
            for dup in issue.get("duplicates", []):
                findings.append(Finding(
                    tool="knip",
                    severity=Severity.LOW,
                    category=Category.CODE,
                    file=filepath,
                    rule_id="duplicate-export",
                    rule_name="Duplicate export",
                    message=f"Duplicate export detected in '{filepath}': {dup}",
                    fix_hint="Consolidate duplicate exports into a single declaration.",
                    effort=Effort.LOW,
                    raw={"type": "duplicate-export", "detail": dup},
                ))

        return findings
