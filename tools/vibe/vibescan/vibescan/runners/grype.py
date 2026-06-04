"""Grype runner — filesystem vulnerability scanner."""

from __future__ import annotations

import json
import logging
import shutil
import time
from typing import Any

from vibescan.models import Finding, ToolResult, ToolStatus
from vibescan.normalisers.grype import GrypeNormaliser
from vibescan.runners.base import AsyncToolRunner

logger = logging.getLogger(__name__)


class GrypeRunner(AsyncToolRunner):
    name = "grype"

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "grype binary not found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        start = time.monotonic()

        cmd = [
            self.bin_path,
            f"dir:{self.target}",
            "-o",
            "json",
        ]

        if self.config.verbose:
            logger.info("grype command: %s", " ".join(cmd))

        try:
            result = self._exec(cmd)
        except FileNotFoundError:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.SKIPPED,
                error="grype binary not found",
                duration_seconds=time.monotonic() - start,
            )
        except Exception as exc:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.FAILED,
                error=f"grype execution error: {exc}",
                duration_seconds=time.monotonic() - start,
            )

        duration = time.monotonic() - start

        if self.config.verbose:
            logger.info("grype stderr: %s", result.stderr.strip()[:500])

        # Parse JSON output
        raw_data: dict[str, Any] | None = None
        if result.stdout.strip():
            try:
                raw_data = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                return ToolResult(
                    tool=self.name,
                    status=ToolStatus.FAILED,
                    error=f"Failed to parse grype JSON output: {exc}",
                    duration_seconds=duration,
                )

        # grype exit codes: 0 = no vulns, 1 = vulns found
        if result.returncode not in (0, 1) and not raw_data:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.FAILED,
                error=f"grype exited with code {result.returncode}: {result.stderr.strip()[:500]}",
                duration_seconds=duration,
            )

        # Normalise findings
        findings: list[Finding] = []
        if raw_data:
            normaliser = GrypeNormaliser()
            findings = normaliser.normalise(raw_data)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            duration_seconds=duration,
        )
