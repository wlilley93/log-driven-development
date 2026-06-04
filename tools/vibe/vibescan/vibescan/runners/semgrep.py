"""Semgrep runner — multi-language SAST with configurable rulesets."""

from __future__ import annotations

import json
import logging
import shutil
import time
from typing import Any

from vibescan.config import DEFAULT_SEMGREP_RULESETS
from vibescan.models import Finding, ToolResult, ToolStatus
from vibescan.normalisers.semgrep import SemgrepNormaliser
from vibescan.runners.base import AsyncToolRunner

logger = logging.getLogger(__name__)


class SemgrepRunner(AsyncToolRunner):
    name = "semgrep"

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "semgrep binary not found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        start = time.monotonic()

        # Resolve rulesets from config
        tc = self.tool_config
        rulesets: list[str] = tc.get("rulesets", DEFAULT_SEMGREP_RULESETS)
        exclude_paths: list[str] = tc.get("exclude_paths", [])

        cmd = [self.bin_path, "scan", "--json"]

        # Add rulesets
        for ruleset in rulesets:
            cmd.extend(["--config", ruleset])

        # Add exclude paths (per-tool + global)
        for path in [*self.global_excludes, *exclude_paths]:
            cmd.extend(["--exclude", path])

        # If scanning only changed files, limit scope
        if changed_files:
            for f in changed_files:
                cmd.extend(["--include", f])

        # Target directory
        cmd.append(self.target)

        if self.config.verbose:
            logger.info("semgrep command: %s", " ".join(cmd))

        try:
            result = self._exec(cmd, timeout=self.config.timeout * 2)
        except FileNotFoundError:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.SKIPPED,
                error="semgrep binary not found",
                duration_seconds=time.monotonic() - start,
            )
        except Exception as exc:
            error_msg = str(exc)
            if "TimeoutExpired" in type(exc).__name__:
                return ToolResult(
                    tool=self.name,
                    status=ToolStatus.TIMEOUT,
                    error=f"semgrep timed out after {self.config.timeout * 2}s",
                    duration_seconds=time.monotonic() - start,
                )
            return ToolResult(
                tool=self.name,
                status=ToolStatus.FAILED,
                error=f"semgrep execution error: {error_msg}",
                duration_seconds=time.monotonic() - start,
            )

        duration = time.monotonic() - start

        if self.config.verbose:
            logger.info("semgrep stderr: %s", result.stderr.strip()[:500])

        # Parse JSON output
        raw_data: dict[str, Any] | None = None
        if result.stdout.strip():
            try:
                raw_data = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                return ToolResult(
                    tool=self.name,
                    status=ToolStatus.FAILED,
                    error=f"Failed to parse semgrep JSON output: {exc}",
                    duration_seconds=duration,
                )

        # semgrep exit codes: 0 = success, 1 = findings, other = error
        if result.returncode not in (0, 1) and not raw_data:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.FAILED,
                error=f"semgrep exited with code {result.returncode}: {result.stderr.strip()[:500]}",
                duration_seconds=duration,
            )

        # Normalise findings
        findings: list[Finding] = []
        if raw_data:
            normaliser = SemgrepNormaliser()
            findings = normaliser.normalise(raw_data)

        status = ToolStatus.SUCCESS
        # If semgrep reported errors alongside results, mark as partial
        if raw_data and raw_data.get("errors"):
            status = ToolStatus.PARTIAL

        return ToolResult(
            tool=self.name,
            status=status,
            findings=findings,
            duration_seconds=duration,
        )
