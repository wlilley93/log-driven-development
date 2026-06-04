"""pip_licenses runner — check Python dependencies for copyleft/unknown licenses."""

from __future__ import annotations

import json
import shutil

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner

# Copyleft licenses that may restrict proprietary usage
COPYLEFT_LICENSES = {
    "gpl", "agpl", "lgpl", "eupl", "osl", "sspl", "cpal", "cpl",
    "gnu general public", "gnu affero", "gnu lesser general public",
    "cc-by-sa",
}

UNKNOWN_LICENSE_MARKERS = {"unknown", "unlicense", "unlicensed", "custom", "other"}


class PipLicensesRunner(AsyncToolRunner):
    name = "pip_licenses"

    @property
    def bin_path(self) -> str:
        from vibedeploy.installer import get_tool_bin
        path = get_tool_bin(self.name)
        if path == self.name:
            return "pip-licenses"
        return path

    def should_run(self) -> bool:
        if not shutil.which("pip-licenses") and not self._tool_exists():
            self.skip_reason = "pip-licenses not installed"
            return False
        if not self._file_exists("requirements.txt", "pyproject.toml", "setup.py", "Pipfile"):
            self.skip_reason = "no Python dependency files found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        bin_path = shutil.which("pip-licenses") or self.bin_path
        cmd = [bin_path, "--format=json", "--with-urls"]

        try:
            result = self._exec(cmd, timeout=self.config.timeout)
        except Exception as e:
            return self._make_error_result(f"pip-licenses execution failed: {e}")

        if not result.stdout.strip():
            if result.returncode != 0:
                return self._make_error_result(
                    f"pip-licenses exited with code {result.returncode}: {result.stderr[:300]}"
                )
            return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=[])

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return self._make_error_result("Failed to parse pip-licenses JSON output")

        findings = self._analyse_licenses(data)
        return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=findings)

    def _analyse_licenses(self, data: list) -> list[Finding]:
        findings: list[Finding] = []

        for pkg in data:
            pkg_name = pkg.get("Name", "unknown")
            pkg_version = pkg.get("Version", "unknown")
            license_str = pkg.get("License", "UNKNOWN")
            url = pkg.get("URL", "")

            license_lower = license_str.lower()

            # Check for copyleft
            is_copyleft = any(cl in license_lower for cl in COPYLEFT_LICENSES)

            if is_copyleft:
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.HIGH,
                    category=Category.SUPPLY_CHAIN,
                    file="requirements.txt",
                    rule_id=f"copyleft-license-{pkg_name}",
                    rule_name="Copyleft License Dependency",
                    message=(
                        f"{pkg_name}=={pkg_version} uses copyleft license '{license_str}'. "
                        f"This may require your application to be open-sourced."
                    ),
                    blocks_deploy=False,
                    effort=Effort.HIGH,
                    fix_hint=f"Replace {pkg_name} with a permissively licensed alternative",
                    docs_url=url if url else None,
                    raw={"package": pkg_name, "version": pkg_version, "license": license_str},
                ))
                continue

            # Check for unknown licenses
            is_unknown = any(marker in license_lower for marker in UNKNOWN_LICENSE_MARKERS)

            if is_unknown:
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.MEDIUM,
                    category=Category.SUPPLY_CHAIN,
                    file="requirements.txt",
                    rule_id=f"unknown-license-{pkg_name}",
                    rule_name="Unknown License Dependency",
                    message=(
                        f"{pkg_name}=={pkg_version} has unknown/unspecified license: '{license_str}'. "
                        f"Review the package license before deploying."
                    ),
                    blocks_deploy=False,
                    effort=Effort.LOW,
                    fix_hint=f"Check {url or pkg_name} for license information",
                    raw={"package": pkg_name, "version": pkg_version, "license": license_str},
                ))

        return findings
