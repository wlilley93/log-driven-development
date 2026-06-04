"""license_checker runner — check npm dependencies for copyleft/unknown licenses."""

from __future__ import annotations

import json
import shutil

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner

# Copyleft licenses that may restrict proprietary usage
COPYLEFT_LICENSES = {
    "GPL-2.0", "GPL-2.0-only", "GPL-2.0-or-later", "GPL-2.0+",
    "GPL-3.0", "GPL-3.0-only", "GPL-3.0-or-later", "GPL-3.0+",
    "AGPL-1.0", "AGPL-3.0", "AGPL-3.0-only", "AGPL-3.0-or-later",
    "LGPL-2.0", "LGPL-2.1", "LGPL-3.0",
    "EUPL-1.1", "EUPL-1.2",
    "OSL-3.0",
    "SSPL-1.0",
    "CPAL-1.0",
    "CPL-1.0",
    "CC-BY-SA-4.0",
}

# License strings that are problematic
UNKNOWN_LICENSE_MARKERS = {"UNKNOWN", "UNLICENSED", "UNLICENCED", "SEE LICENSE IN", "Custom"}


class LicenseCheckerRunner(AsyncToolRunner):
    name = "license_checker"

    def should_run(self) -> bool:
        if not shutil.which("npx") and not shutil.which("license-checker"):
            self.skip_reason = "npm/npx not installed"
            return False
        if not self._file_exists("package.json"):
            self.skip_reason = "no package.json found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        # Try license-checker directly, fallback to npx
        bin_path = shutil.which("license-checker")
        if bin_path:
            cmd = [bin_path, "--json", "--production"]
        else:
            cmd = ["npx", "--yes", "license-checker", "--json", "--production"]

        try:
            result = self._exec(cmd, timeout=self.config.timeout * 2)
        except Exception as e:
            return self._make_error_result(f"license-checker execution failed: {e}")

        if not result.stdout.strip():
            if result.returncode != 0:
                return self._make_error_result(
                    f"license-checker exited with code {result.returncode}: {result.stderr[:300]}"
                )
            return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=[])

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return self._make_error_result("Failed to parse license-checker JSON output")

        findings = self._analyse_licenses(data)
        return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=findings)

    def _analyse_licenses(self, data: dict) -> list[Finding]:
        findings: list[Finding] = []

        for pkg_key, pkg_info in data.items():
            licenses = pkg_info.get("licenses", "UNKNOWN")
            # licenses can be a string or a list
            if isinstance(licenses, list):
                license_str = ", ".join(str(l) for l in licenses)
            else:
                license_str = str(licenses)

            repository = pkg_info.get("repository", "")
            publisher = pkg_info.get("publisher", "")
            pkg_path = pkg_info.get("path", "")

            # Check for copyleft
            is_copyleft = False
            for copyleft in COPYLEFT_LICENSES:
                if copyleft.lower() in license_str.lower():
                    is_copyleft = True
                    break

            if is_copyleft:
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.HIGH,
                    category=Category.SUPPLY_CHAIN,
                    file="package.json",
                    rule_id=f"copyleft-license-{pkg_key}",
                    rule_name="Copyleft License Dependency",
                    message=(
                        f"{pkg_key} uses copyleft license '{license_str}'. "
                        f"This may require your application to be open-sourced."
                    ),
                    blocks_deploy=False,
                    effort=Effort.HIGH,
                    fix_hint=f"Replace {pkg_key} with an MIT/Apache-2.0 licensed alternative",
                    raw={"package": pkg_key, "licenses": license_str, "repository": repository},
                ))
                continue

            # Check for unknown licenses
            is_unknown = False
            for marker in UNKNOWN_LICENSE_MARKERS:
                if marker.lower() in license_str.lower():
                    is_unknown = True
                    break

            if is_unknown:
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.MEDIUM,
                    category=Category.SUPPLY_CHAIN,
                    file="package.json",
                    rule_id=f"unknown-license-{pkg_key}",
                    rule_name="Unknown License Dependency",
                    message=(
                        f"{pkg_key} has unknown or unspecified license: '{license_str}'. "
                        f"Review the package license before deploying to production."
                    ),
                    blocks_deploy=False,
                    effort=Effort.LOW,
                    fix_hint=f"Check {repository or pkg_key} for license information",
                    raw={"package": pkg_key, "licenses": license_str, "repository": repository},
                ))

        return findings
