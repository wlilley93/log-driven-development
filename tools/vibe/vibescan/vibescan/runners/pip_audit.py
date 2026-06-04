"""pip-audit runner — Python dependency vulnerability scanner."""

from __future__ import annotations

import json
import logging
import shutil
import time
from typing import Any

from vibescan.models import Finding, ToolResult, ToolStatus
from vibescan.normalisers.pip_audit import PipAuditNormaliser
from vibescan.runners.base import AsyncToolRunner

logger = logging.getLogger(__name__)


class PipAuditRunner(AsyncToolRunner):
    name = "pip-audit"

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "pip-audit binary not found"
            return False
        if not self._file_exists("requirements.txt", "pyproject.toml"):
            self.skip_reason = "no requirements.txt or pyproject.toml found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        start = time.monotonic()

        cmd = [self.bin_path, "-f", "json"]

        # If requirements.txt exists, use it explicitly
        if self._file_exists("requirements.txt"):
            cmd.extend(["-r", "requirements.txt"])

        if self.config.verbose:
            logger.info("pip-audit command: %s", " ".join(cmd))

        try:
            result = self._exec(cmd)
        except FileNotFoundError:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.SKIPPED,
                error="pip-audit binary not found",
                duration_seconds=time.monotonic() - start,
            )
        except Exception as exc:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.FAILED,
                error=f"pip-audit execution error: {exc}",
                duration_seconds=time.monotonic() - start,
            )

        duration = time.monotonic() - start

        if self.config.verbose:
            logger.info("pip-audit stderr: %s", result.stderr.strip()[:500])

        # Parse JSON output
        raw_data: Any = None
        if result.stdout.strip():
            try:
                raw_data = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                return ToolResult(
                    tool=self.name,
                    status=ToolStatus.FAILED,
                    error=f"Failed to parse pip-audit JSON output: {exc}",
                    duration_seconds=duration,
                )

        # pip-audit exit codes: 0 = clean, 1 = vulnerabilities found
        if result.returncode not in (0, 1) and not raw_data:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.FAILED,
                error=f"pip-audit exited with code {result.returncode}: {result.stderr.strip()[:500]}",
                duration_seconds=duration,
            )

        # Normalise findings
        findings: list[Finding] = []
        if raw_data:
            normaliser = PipAuditNormaliser()
            findings = normaliser.normalise(raw_data)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            duration_seconds=duration,
        )
