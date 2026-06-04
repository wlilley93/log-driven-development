"""Normaliser for depcheck output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser


class DepcheckNormaliser(BaseNormaliser):
    """Convert depcheck JSON output to Finding objects.

    depcheck JSON shape:
    {
      "dependencies": ["lodash", "moment"],
      "devDependencies": ["jest-cli"],
      "missing": {"react-dom": ["/src/index.tsx"]},
      "using": {...},
      "invalidFiles": {...},
      "invalidDirs": {...}
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        findings: list[Finding] = []

        # Unused production dependencies
        for dep in raw_data.get("dependencies", []):
            findings.append(Finding(
                tool="depcheck",
                severity=Severity.MEDIUM,
                category=Category.DEPENDENCY,
                file="package.json",
                rule_id="unused-dependency",
                rule_name="Unused dependency",
                message=f"Package '{dep}' is listed as a dependency but is not imported anywhere.",
                fix_hint=f"Run `npm uninstall {dep}` to remove it, or verify it is used via a dynamic import or CLI.",
                saving_estimate=f"Remove '{dep}' to reduce install size and node_modules footprint.",
                effort=Effort.LOW,
                raw={"package": dep, "type": "dependency"},
            ))

        # Unused devDependencies
        for dep in raw_data.get("devDependencies", []):
            findings.append(Finding(
                tool="depcheck",
                severity=Severity.LOW,
                category=Category.DEPENDENCY,
                file="package.json",
                rule_id="unused-dev-dependency",
                rule_name="Unused dev dependency",
                message=f"Package '{dep}' is listed as a devDependency but is not imported anywhere.",
                fix_hint=f"Run `npm uninstall {dep}` to remove it from devDependencies.",
                effort=Effort.LOW,
                raw={"package": dep, "type": "devDependency"},
            ))

        # Missing dependencies (imported but not in package.json)
        missing = raw_data.get("missing", {})
        for dep, files in missing.items():
            file_list = ", ".join(files[:3])
            extra = f" (+{len(files) - 3} more)" if len(files) > 3 else ""
            findings.append(Finding(
                tool="depcheck",
                severity=Severity.HIGH,
                category=Category.DEPENDENCY,
                file="package.json",
                rule_id="missing-dependency",
                rule_name="Missing dependency",
                message=(
                    f"Package '{dep}' is imported in {file_list}{extra} "
                    f"but is not listed in package.json."
                ),
                fix_hint=f"Run `npm install {dep}` to add it as a dependency.",
                effort=Effort.LOW,
                raw={"package": dep, "type": "missing", "files": files},
            ))

        return findings
