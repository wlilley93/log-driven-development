"""Normaliser for npm-check output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser


class NpmCheckNormaliser(BaseNormaliser):
    """Convert npm-check JSON output to Finding objects.

    npm-check --json output shape:
    [
      {
        "moduleName": "lodash",
        "homepage": "https://lodash.com/",
        "regError": null,
        "pkgError": null,
        "latest": "4.18.0",
        "installed": "4.17.21",
        "packageWanted": "4.17.21",
        "packageJson": "^4.17.21",
        "devDependency": false,
        "usedInScripts": false,
        "mismatch": false,
        "semverValid": "4.17.21",
        "easyUpgrade": true,
        "bump": "minor",
        "unused": false
      },
      {
        "moduleName": "jest-cli",
        "installed": "29.0.0",
        "latest": "29.7.0",
        "devDependency": true,
        "unused": true,
        "bump": "minor"
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

            module_name = entry.get("moduleName", "unknown")
            installed = entry.get("installed", "unknown")
            latest = entry.get("latest", "")
            bump = entry.get("bump", "unknown")
            unused = entry.get("unused", False)
            mismatch = entry.get("mismatch", False)
            dev_dep = entry.get("devDependency", False)
            reg_error = entry.get("regError")
            pkg_error = entry.get("pkgError")
            easy_upgrade = entry.get("easyUpgrade", True)
            package_json = entry.get("packageJson", "")

            # Skip errored entries
            if reg_error or pkg_error:
                continue

            # Unused dependency
            if unused:
                severity = Severity.LOW if dev_dep else Severity.MEDIUM
                findings.append(Finding(
                    tool="npm-check",
                    severity=severity,
                    category=Category.DEPENDENCY,
                    file="package.json",
                    rule_id="unused-package",
                    rule_name="Unused package",
                    message=(
                        f"Package '{module_name}' ({installed}) is installed but "
                        f"does not appear to be used in the project."
                    ),
                    fix_hint=f"Run `npm uninstall {module_name}` to remove it.",
                    saving_estimate=(
                        f"Remove '{module_name}' to reduce install size "
                        f"and node_modules footprint"
                    ),
                    effort=Effort.LOW,
                    raw=entry,
                ))

            # Version mismatch (installed != what package.json specifies)
            if mismatch:
                findings.append(Finding(
                    tool="npm-check",
                    severity=Severity.MEDIUM,
                    category=Category.DEPENDENCY,
                    file="package.json",
                    rule_id="version-mismatch",
                    rule_name="Installed version mismatch",
                    message=(
                        f"'{module_name}' is installed at {installed} but "
                        f"package.json specifies {package_json}."
                    ),
                    fix_hint=(
                        f"Run `npm install` to re-align installed version with "
                        f"package.json, or update the version specifier."
                    ),
                    effort=Effort.LOW,
                    raw=entry,
                ))

            # Outdated dependency
            if latest and latest != installed and not unused:
                severity = _severity_for_bump(bump)
                effort = _effort_for_bump(bump, easy_upgrade)

                findings.append(Finding(
                    tool="npm-check",
                    severity=severity,
                    category=Category.DEPENDENCY,
                    file="package.json",
                    rule_id=f"outdated-{bump}",
                    rule_name=f"Outdated package ({bump} update available)",
                    message=(
                        f"'{module_name}' is at {installed}, latest is {latest} "
                        f"({bump} update)."
                    ),
                    fix_hint=_get_upgrade_hint(module_name, bump, latest, easy_upgrade),
                    effort=effort,
                    raw=entry,
                ))

        return findings


def _severity_for_bump(bump: str) -> Severity:
    """Map semver bump type to severity."""
    if bump == "major":
        return Severity.MEDIUM
    if bump == "minor":
        return Severity.LOW
    # patch or unknown
    return Severity.LOW


def _effort_for_bump(bump: str, easy_upgrade: bool) -> Effort:
    """Map bump type and upgrade ease to effort."""
    if bump == "major":
        return Effort.HIGH
    if not easy_upgrade:
        return Effort.MEDIUM
    return Effort.LOW


def _get_upgrade_hint(
    module_name: str,
    bump: str,
    latest: str,
    easy_upgrade: bool,
) -> str:
    """Generate an upgrade hint."""
    cmd = f"npm install {module_name}@{latest}"

    if bump == "major":
        return (
            f"Run `{cmd}` to upgrade. This is a major version update and may "
            f"include breaking changes — check the changelog and release notes first."
        )

    if not easy_upgrade:
        return (
            f"Run `{cmd}` to upgrade. This update may require manual "
            f"intervention due to peer dependency or lockfile constraints."
        )

    if bump == "minor":
        return (
            f"Run `{cmd}` to upgrade. Minor updates typically add new features "
            f"without breaking changes."
        )

    return (
        f"Run `{cmd}` to upgrade. Patch updates usually contain bug fixes only."
    )
