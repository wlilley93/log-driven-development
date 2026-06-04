"""Snyk runner — dependency vulnerability scanner (requires SNYK_TOKEN)."""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from typing import Any

from vibescan.models import Finding, ToolResult, ToolStatus
from vibescan.normalisers.snyk import SnykNormaliser
from vibescan.runners.base import AsyncToolRunner

logger = logging.getLogger(__name__)


class SnykRunner(AsyncToolRunner):
    name = "snyk"

    def should_run(self) -> bool:
        if not os.environ.get("SNYK_TOKEN"):
            self.skip_reason = "SNYK_TOKEN environment variable not set"
            return False
        if not self._tool_exists():
            self.skip_reason = "snyk binary not found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        start = time.monotonic()

        cmd = [self.bin_path, "test", "--json"]

        if self.config.verbose:
            logger.info("snyk command: %s", " ".join(cmd))

        try:
            result = self._exec(cmd)
        except FileNotFoundError:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.SKIPPED,
                error="snyk binary not found",
                duration_seconds=time.monotonic() - start,
            )
        except Exception as exc:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.FAILED,
                error=f"snyk execution error: {exc}",
                duration_seconds=time.monotonic() - start,
            )

        duration = time.monotonic() - start

        if self.config.verbose:
            logger.info("snyk stderr: %s", result.stderr.strip()[:500])

        # Parse JSON output
        raw_data: dict[str, Any] | None = None
        if result.stdout.strip():
            try:
                raw_data = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                return ToolResult(
                    tool=self.name,
                    status=ToolStatus.FAILED,
                    error=f"Failed to parse snyk JSON output: {exc}",
                    duration_seconds=duration,
                )

        # snyk exit codes: 0 = no vulns, 1 = vulns found, 2 = action required, 3 = error
        if result.returncode == 3 or (result.returncode not in (0, 1, 2) and not raw_data):
            error_msg = result.stderr.strip()[:500]
            # Check for auth errors
            if raw_data and raw_data.get("error"):
                error_msg = raw_data["error"]
            return ToolResult(
                tool=self.name,
                status=ToolStatus.FAILED,
                error=f"snyk error (exit {result.returncode}): {error_msg}",
                duration_seconds=duration,
            )

        # Normalise findings
        findings: list[Finding] = []
        if raw_data:
            normaliser = SnykNormaliser()
            findings = normaliser.normalise(raw_data)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            duration_seconds=duration,
        )
