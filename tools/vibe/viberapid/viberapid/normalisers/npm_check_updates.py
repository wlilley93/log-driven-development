"""Normaliser for npm-check-updates output."""

from __future__ import annotations

import re
from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser


def _classify_update(current: str, latest: str) -> str:
    """Classify the semver update type: major, minor, or patch."""
    current_parts = _parse_semver(current)
    latest_parts = _parse_semver(latest)

    if current_parts is None or latest_parts is None:
        return "unknown"

    if latest_parts[0] > current_parts[0]:
        return "major"
    if latest_parts[1] > current_parts[1]:
        return "minor"
    if latest_parts[2] > current_parts[2]:
        return "patch"
    return "unknown"


def _parse_semver(version_str: str) -> tuple[int, int, int] | None:
    """Parse a semver string, stripping range prefixes like ^ or ~."""
    cleaned = re.sub(r"^[~^>=<\s]+", "", version_str.strip())
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", cleaned)
    if match:
        return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    return None


class NpmCheckUpdatesNormaliser(BaseNormaliser):
    """Convert npm-check-updates JSON output to Finding objects.

    npx npm-check-updates --jsonUpgraded shape:
    {
      "lodash": "4.18.0",
      "react": "19.0.0",
      "typescript": "5.5.0"
    }

    These are the *target* versions. The current versions come from package.json.
    The runner passes both as:
    {
      "upgrades": {"lodash": "4.18.0", ...},
      "current": {"lodash": "^4.17.21", ...}
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        findings: list[Finding] = []

        upgrades = raw_data.get("upgrades", {})
        current = raw_data.get("current", {})

        for pkg_name, target_version in upgrades.items():
            current_version = current.get(pkg_name, "unknown")
            update_type = _classify_update(current_version, target_version)

            if update_type == "major":
                severity = Severity.MEDIUM
                effort = Effort.HIGH
            elif update_type == "minor":
                severity = Severity.LOW
                effort = Effort.LOW
            else:
                severity = Severity.LOW
                effort = Effort.LOW

            findings.append(Finding(
                tool="npm-check-updates",
                severity=severity,
                category=Category.DEPENDENCY,
                file="package.json",
                rule_id=f"outdated-{update_type}",
                rule_name=f"Outdated dependency ({update_type} update)",
                message=(
                    f"'{pkg_name}' can be updated from {current_version} to "
                    f"{target_version} ({update_type} update)."
                ),
                fix_hint=_get_fix_hint(pkg_name, update_type, target_version),
                effort=effort,
                raw={
                    "package": pkg_name,
                    "current": current_version,
                    "target": target_version,
                    "update_type": update_type,
                },
            ))

        return findings


def _get_fix_hint(pkg_name: str, update_type: str, target_version: str) -> str:
    """Generate fix hint based on update type."""
    if update_type == "major":
        return (
            f"Run `npm install {pkg_name}@{target_version}` to upgrade. "
            f"Major version updates may include breaking changes; check the changelog first."
        )
    if update_type == "minor":
        return (
            f"Run `npm install {pkg_name}@{target_version}` to upgrade. "
            f"Minor updates typically add features without breaking changes."
        )
    return (
        f"Run `npm install {pkg_name}@{target_version}` to upgrade. "
        f"Patch updates usually contain bug fixes only."
    )
