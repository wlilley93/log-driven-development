"""detect-secrets runner — baseline-aware secret detection."""

from __future__ import annotations

import json
import logging
import shutil
import time
from pathlib import Path
from typing import Any

from vibescan.models import Finding, ToolResult, ToolStatus
from vibescan.normalisers.detect_secrets import DetectSecretsNormaliser
from vibescan.runners.base import AsyncToolRunner

logger = logging.getLogger(__name__)

BASELINE_FILENAME = ".secrets.baseline"


class DetectSecretsRunner(AsyncToolRunner):
    name = "detect-secrets"
    is_secret_scanner = True

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "detect-secrets binary not found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        start = time.monotonic()
        tc = self.tool_config
        cmd = [self.bin_path, "scan"]

        # Use baseline if it exists in the target directory
        baseline_path = Path(self.target) / BASELINE_FILENAME
        if baseline_path.exists():
            cmd.extend(["--baseline", str(baseline_path)])
            if self.config.verbose:
                logger.info("using baseline %s", baseline_path)
        else:
            # Scan all files when no baseline exists
            cmd.append("--all-files")

        # Exclude paths from config (converted to regex for --exclude-files)
        exclude_paths: list[str] = tc.get("exclude_paths", [])
        if exclude_paths:
            pattern = "|".join(p.replace("/", r"\/") for p in exclude_paths)
            cmd.extend(["--exclude-files", pattern])

        # If we have changed files, scan only those
        if changed_files:
            # detect-secrets scan accepts file paths as positional args
            cmd.extend(changed_files)

        if self.config.verbose:
            logger.info("ds command: %s", " ".join(cmd))

        try:
            result = self._exec(cmd)
        except FileNotFoundError:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.SKIPPED,
                error="detect-secrets binary not found",
                duration_seconds=time.monotonic() - start,
            )
        except Exception as exc:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.FAILED,
                error=f"detect-secrets execution error: {exc}",
                duration_seconds=time.monotonic() - start,
            )

        duration = time.monotonic() - start

        if self.config.verbose:
            logger.info("ds stderr: %s", result.stderr.strip()[:500])

        # detect-secrets outputs JSON to stdout with a "results" key
        raw_data: dict[str, Any] | None = None
        if result.stdout.strip():
            try:
                raw_data = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                return ToolResult(
                    tool=self.name,
                    status=ToolStatus.FAILED,
                    error=f"Failed to parse detect-secrets output: {exc}",
                    duration_seconds=duration,
                )

        # Non-zero exit with no output is an error
        if result.returncode != 0 and not raw_data:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.FAILED,
                error=f"detect-secrets exited with code {result.returncode}: {result.stderr.strip()[:500]}",
                duration_seconds=duration,
            )

        # Normalise findings
        findings: list[Finding] = []
        if raw_data:
            normaliser = DetectSecretsNormaliser()
            findings = normaliser.normalise(raw_data)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            duration_seconds=duration,
        )
