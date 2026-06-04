"""Trivy runner — filesystem vulnerability scanner."""

from __future__ import annotations

import json
import logging
import shutil
import time
from typing import Any

from vibescan.models import Finding, ToolResult, ToolStatus
from vibescan.normalisers.trivy import TrivyNormaliser
from vibescan.runners.base import AsyncToolRunner

logger = logging.getLogger(__name__)


class TrivyRunner(AsyncToolRunner):
    name = "trivy"

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "trivy binary not found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        start = time.monotonic()
        tc = self.tool_config

        cmd = [
            self.bin_path,
            "fs",
            self.target,
            "--format",
            "json",
            "--scanners",
            "vuln",
        ]

        # Severity filter from config
        severity_filter: str | None = tc.get("severity")
        if severity_filter:
            cmd.extend(["--severity", severity_filter])

        # Ignore unfixed vulnerabilities
        ignore_unfixed: bool = tc.get("ignore_unfixed", False)
        if ignore_unfixed:
            cmd.append("--ignore-unfixed")

        if self.config.verbose:
            logger.info("trivy command: %s", " ".join(cmd))

        try:
            result = self._exec(cmd)
        except FileNotFoundError:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.SKIPPED,
                error="trivy binary not found",
                duration_seconds=time.monotonic() - start,
            )
        except Exception as exc:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.FAILED,
                error=f"trivy execution error: {exc}",
                duration_seconds=time.monotonic() - start,
            )

        duration = time.monotonic() - start

        if self.config.verbose:
            logger.info("trivy stderr: %s", result.stderr.strip()[:500])

        # Parse JSON output
        raw_data: dict[str, Any] | None = None
        if result.stdout.strip():
            try:
                raw_data = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                return ToolResult(
                    tool=self.name,
                    status=ToolStatus.FAILED,
                    error=f"Failed to parse trivy JSON output: {exc}",
                    duration_seconds=duration,
                )

        # trivy returns 0 on success (even with findings)
        if result.returncode != 0 and not raw_data:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.FAILED,
                error=f"trivy exited with code {result.returncode}: {result.stderr.strip()[:500]}",
                duration_seconds=duration,
            )

        # Normalise findings
        findings: list[Finding] = []
        if raw_data:
            normaliser = TrivyNormaliser()
            findings = normaliser.normalise(raw_data)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            duration_seconds=duration,
        )
