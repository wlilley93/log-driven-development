"""npm audit runner — JavaScript/Node.js dependency vulnerability scanner."""

from __future__ import annotations

import json
import logging
import shutil
import time
from typing import Any

from vibescan.models import Finding, ToolResult, ToolStatus
from vibescan.normalisers.npm_audit import NpmAuditNormaliser
from vibescan.runners.base import AsyncToolRunner

logger = logging.getLogger(__name__)


class NpmAuditRunner(AsyncToolRunner):
    name = "npm-audit"

    def should_run(self) -> bool:
        if not shutil.which("npm"):
            self.skip_reason = "npm not found"
            return False
        if not self._file_exists("package-lock.json"):
            self.skip_reason = "no package-lock.json found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        start = time.monotonic()

        cmd = ["npm", "audit", "--json"]

        if self.config.verbose:
            logger.info("npm audit command: %s", " ".join(cmd))

        try:
            result = self._exec(cmd)
        except FileNotFoundError:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.SKIPPED,
                error="npm binary not found",
                duration_seconds=time.monotonic() - start,
            )
        except Exception as exc:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.FAILED,
                error=f"npm audit execution error: {exc}",
                duration_seconds=time.monotonic() - start,
            )

        duration = time.monotonic() - start

        if self.config.verbose:
            logger.info("npm audit stderr: %s", result.stderr.strip()[:500])

        # Parse JSON output
        raw_data: dict[str, Any] | None = None
        if result.stdout.strip():
            try:
                raw_data = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                return ToolResult(
                    tool=self.name,
                    status=ToolStatus.FAILED,
                    error=f"Failed to parse npm audit JSON output: {exc}",
                    duration_seconds=duration,
                )

        # npm audit exit codes: 0 = no vulns, 1 = vulns found, other = error
        # npm audit may return exit code 1 with valid JSON when vulnerabilities exist
        if result.returncode not in (0, 1) and not raw_data:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.FAILED,
                error=f"npm audit exited with code {result.returncode}: {result.stderr.strip()[:500]}",
                duration_seconds=duration,
            )

        # Normalise findings
        findings: list[Finding] = []
        if raw_data:
            normaliser = NpmAuditNormaliser()
            findings = normaliser.normalise(raw_data)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            duration_seconds=duration,
        )
