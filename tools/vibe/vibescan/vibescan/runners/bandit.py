"""Bandit runner — Python-specific SAST."""

from __future__ import annotations

import json
import logging
import shutil
import time
from pathlib import Path
from typing import Any

from vibescan.models import Finding, ToolResult, ToolStatus
from vibescan.normalisers.bandit import BanditNormaliser
from vibescan.runners.base import AsyncToolRunner

logger = logging.getLogger(__name__)


class BanditRunner(AsyncToolRunner):
    name = "bandit"

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "bandit binary not found"
            return False

        # Only run if Python files exist
        target = Path(self.target)
        has_python = any(target.rglob("*.py"))
        if not has_python:
            self.skip_reason = "no Python files found"
            return False

        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        start = time.monotonic()
        tc = self.tool_config

        cmd = [self.bin_path, "-f", "json"]

        # Skip specific tests from config
        skip_tests: list[str] = tc.get("skip", [])
        if skip_tests:
            cmd.extend(["-s", ",".join(skip_tests)])

        # Exclude directories from config (per-tool + global)
        exclude_dirs: list[str] = [*self.global_excludes, *tc.get("exclude_dirs", [])]
        if exclude_dirs:
            cmd.extend(["--exclude", ",".join(exclude_dirs)])

        if changed_files:
            # Scan only specified files
            py_files = [f for f in changed_files if f.endswith(".py")]
            if not py_files:
                return ToolResult(
                    tool=self.name,
                    status=ToolStatus.SKIPPED,
                    error="no Python files in changed_files",
                    duration_seconds=time.monotonic() - start,
                )
            cmd.extend(py_files)
        else:
            # Recursive scan of target
            cmd.extend(["-r", self.target])

        if self.config.verbose:
            logger.info("bandit command: %s", " ".join(cmd))

        try:
            result = self._exec(cmd)
        except FileNotFoundError:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.SKIPPED,
                error="bandit binary not found",
                duration_seconds=time.monotonic() - start,
            )
        except Exception as exc:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.FAILED,
                error=f"bandit execution error: {exc}",
                duration_seconds=time.monotonic() - start,
            )

        duration = time.monotonic() - start

        if self.config.verbose:
            logger.info("bandit stderr: %s", result.stderr.strip()[:500])

        # Parse JSON output — bandit may prepend a progress bar line to stdout
        raw_data: dict[str, Any] | None = None
        stdout = result.stdout.strip()
        if stdout:
            # Find the start of JSON (skip progress bar lines)
            json_start = stdout.find("{")
            if json_start >= 0:
                stdout = stdout[json_start:]
            try:
                raw_data = json.loads(stdout)
            except json.JSONDecodeError as exc:
                return ToolResult(
                    tool=self.name,
                    status=ToolStatus.FAILED,
                    error=f"Failed to parse bandit JSON output: {exc}",
                    duration_seconds=duration,
                )

        # bandit exit codes: 0 = no issues, 1 = issues found, other = error
        if result.returncode not in (0, 1) and not raw_data:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.FAILED,
                error=f"bandit exited with code {result.returncode}: {result.stderr.strip()[:500]}",
                duration_seconds=duration,
            )

        # Normalise findings
        findings: list[Finding] = []
        if raw_data:
            normaliser = BanditNormaliser()
            findings = normaliser.normalise(raw_data)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            duration_seconds=duration,
        )
