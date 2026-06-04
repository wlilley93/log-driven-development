"""Licence compliance runner — checks npm and Python dependencies against allow/blocklists."""

from __future__ import annotations

import json
import logging
import shutil
import time
from pathlib import Path
from typing import Any

from vibescan.installer import get_tool_bin, get_tool_spec, check_tool
from vibescan.models import Category, Finding, Severity, ToolResult, ToolStatus
from vibescan.normalisers.licence import LicenceNormaliser
from vibescan.runners.base import AsyncToolRunner

logger = logging.getLogger(__name__)


class LicenceRunner(AsyncToolRunner):
    name = "licence"

    def should_run(self) -> bool:
        has_npm = self._file_exists("package.json")
        has_python = self._file_exists("requirements.txt", "pyproject.toml")

        if not has_npm and not has_python:
            self.skip_reason = "no package.json, requirements.txt, or pyproject.toml found"
            return False

        # Check that at least one licence tool is available
        has_npm_tool = has_npm and shutil.which("npx") is not None
        pip_licenses_available = shutil.which("pip-licenses") is not None
        if not pip_licenses_available:
            spec = get_tool_spec("pip-licenses")
            if spec:
                pip_licenses_available = check_tool(spec)["installed"]
        has_pip_tool = has_python and pip_licenses_available

        if not has_npm_tool and not has_pip_tool:
            self.skip_reason = "no licence scanning tools available (need npx/license-checker or pip-licenses)"
            return False

        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        start = time.monotonic()
        normaliser = LicenceNormaliser()
        all_findings: list[Finding] = []
        errors: list[str] = []
        ran_any = False

        # Run license-checker (npm) if package.json exists
        if self._file_exists("package.json") and shutil.which("npx"):
            npm_findings, npm_error = self._run_npm_licence_checker(normaliser)
            if npm_error:
                errors.append(npm_error)
            all_findings.extend(npm_findings)
            ran_any = True

        # Run pip-licenses if Python dependency files exist
        pip_licenses_bin = shutil.which("pip-licenses") or get_tool_bin("pip-licenses")
        if self._file_exists("requirements.txt", "pyproject.toml") and Path(pip_licenses_bin).exists():
            pip_findings, pip_error = self._run_pip_licenses(normaliser)
            if pip_error:
                errors.append(pip_error)
            all_findings.extend(pip_findings)
            ran_any = True

        duration = time.monotonic() - start

        if not ran_any:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.SKIPPED,
                error="no licence tools could execute",
                duration_seconds=duration,
            )

        # Apply allow/blocklist filtering
        filtered_findings = self._apply_licence_policy(all_findings)

        status = ToolStatus.SUCCESS
        if errors:
            status = ToolStatus.PARTIAL

        return ToolResult(
            tool=self.name,
            status=status,
            findings=filtered_findings,
            error="; ".join(errors) if errors else None,
            duration_seconds=duration,
        )

    def _run_npm_licence_checker(
        self, normaliser: LicenceNormaliser
    ) -> tuple[list[Finding], str | None]:
        """Run license-checker via npx and return findings."""
        cmd = ["npx", "license-checker", "--json", "--production"]

        if self.config.verbose:
            logger.info("licence: npm command: %s", " ".join(cmd))

        try:
            result = self._exec(cmd)
        except FileNotFoundError:
            return [], "npx not found"
        except Exception as exc:
            return [], f"license-checker error: {exc}"

        if self.config.verbose:
            logger.info("licence: npm stderr: %s", result.stderr.strip()[:500])

        raw_data: dict[str, Any] | None = None
        if result.stdout.strip():
            try:
                raw_data = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                return [], f"Failed to parse license-checker output: {exc}"

        if not raw_data:
            if result.returncode != 0:
                return [], f"license-checker exited with code {result.returncode}"
            return [], None

        findings = normaliser.normalise({"npm": raw_data})
        return findings, None

    def _run_pip_licenses(
        self, normaliser: LicenceNormaliser
    ) -> tuple[list[Finding], str | None]:
        """Run pip-licenses and return findings."""
        pip_bin = shutil.which("pip-licenses") or get_tool_bin("pip-licenses")
        cmd = [pip_bin, "--format=json", "--with-urls"]

        if self.config.verbose:
            logger.info("licence: pip command: %s", " ".join(cmd))

        try:
            result = self._exec(cmd)
        except FileNotFoundError:
            return [], "pip-licenses not found"
        except Exception as exc:
            return [], f"pip-licenses error: {exc}"

        if self.config.verbose:
            logger.info("licence: pip stderr: %s", result.stderr.strip()[:500])

        raw_data: Any = None
        if result.stdout.strip():
            try:
                raw_data = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                return [], f"Failed to parse pip-licenses output: {exc}"

        if not raw_data:
            if result.returncode != 0:
                return [], f"pip-licenses exited with code {result.returncode}"
            return [], None

        findings = normaliser.normalise({"pip": raw_data})
        return findings, None

    def _apply_licence_policy(self, findings: list[Finding]) -> list[Finding]:
        """Apply allow/blocklist policy to licence findings, adjusting severity."""
        blocklist = set(self.config.licence_blocklist)
        allowlist = set(self.config.licence_allowlist)

        filtered: list[Finding] = []
        for finding in findings:
            licence = finding.licence
            # Treat missing licence as "UNKNOWN" for policy checks
            licence_clean = licence.strip() if licence else "UNKNOWN"

            if licence_clean in blocklist:
                # Blocklisted licence — escalate to HIGH
                finding.severity = Severity.HIGH
                finding.message = f"Blocklisted licence: {licence_clean}. {finding.message}"
                filtered.append(finding)
            elif licence_clean in allowlist:
                # Allowlisted — skip (no finding)
                if self.config.verbose:
                    logger.info(
                        "licence: skipping allowlisted %s for %s",
                        licence_clean,
                        finding.file,
                    )
            elif licence_clean.upper() in ("UNKNOWN", "UNLICENSED", ""):
                # Unknown licence — warn
                finding.severity = Severity.MEDIUM
                finding.message = f"Unknown licence for {finding.file}. {finding.message}"
                filtered.append(finding)
            else:
                # Not in either list — INFO level
                finding.severity = Severity.INFO
                filtered.append(finding)

        return filtered
