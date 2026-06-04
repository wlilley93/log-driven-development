"""Normaliser for duplicate-packages analysis."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser


class DuplicatePackagesNormaliser(BaseNormaliser):
    """Convert duplicate package analysis to Finding objects.

    Input shape (built by the runner):
    {
      "duplicates": {
        "lodash": ["4.17.21", "4.17.15"],
        "semver": ["7.5.4", "6.3.1", "5.7.1"]
      },
      "total_duplicates": 2
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        findings: list[Finding] = []
        duplicates = raw_data.get("duplicates", {})

        for pkg_name, versions in duplicates.items():
            if not isinstance(versions, list) or len(versions) < 2:
                continue

            version_count = len(versions)
            version_list = ", ".join(sorted(versions))

            # More versions = more severity
            if version_count >= 4:
                severity = Severity.HIGH
            elif version_count >= 3:
                severity = Severity.MEDIUM
            else:
                severity = Severity.MEDIUM

            findings.append(Finding(
                tool="duplicate-packages",
                severity=severity,
                category=Category.BUNDLE,
                file="package-lock.json",
                rule_id="duplicate-package",
                rule_name="Duplicate package versions",
                message=(
                    f"'{pkg_name}' is installed at {version_count} different versions: "
                    f"{version_list}. This increases node_modules size and bundle weight."
                ),
                fix_hint=(
                    f"Run `npm dedupe` to flatten the dependency tree. "
                    f"If that does not resolve it, check which top-level packages "
                    f"require different versions of '{pkg_name}' using `npm ls {pkg_name}` "
                    f"and consider updating them."
                ),
                saving_estimate=(
                    f"{version_count - 1} extra copies of '{pkg_name}' "
                    f"could potentially be deduplicated"
                ),
                effort=Effort.LOW if version_count == 2 else Effort.MEDIUM,
                raw={"package": pkg_name, "versions": versions},
            ))

        return findings
