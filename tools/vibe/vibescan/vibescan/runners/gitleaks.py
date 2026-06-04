"""Gitleaks runner — secret detection via regex patterns."""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
import time
from typing import Any

from vibescan.models import Finding, ToolResult, ToolStatus
from vibescan.normalisers.gitleaks import GitleaksNormaliser
from vibescan.runners.base import AsyncToolRunner

logger = logging.getLogger(__name__)


class GitleaksRunner(AsyncToolRunner):
    name = "gitleaks"
    is_secret_scanner = True

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "gitleaks binary not found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        start = time.monotonic()
        tc = self.tool_config
        cmd = [
            self.bin_path,
            "detect",
            "--source",
            self.target,
            "--report-format",
            "json",
            "--report-path",
            "/dev/stdout",
            "--no-banner",
        ]

        # Exclude paths from config (per-tool + global; write .gitleaksignore temp file)
        exclude_paths: list[str] = [*self.global_excludes, *tc.get("exclude_paths", [])]
        ignore_file = None
        if exclude_paths:
            ignore_file = tempfile.NamedTemporaryFile(mode="w", suffix=".gitleaksignore", delete=False)
            for p in exclude_paths:
                ignore_file.write(p + "\n")
            ignore_file.close()
            cmd.extend(["--gitleaks-ignore-path", ignore_file.name])

        # If scanning only changed files, limit git log scope
        if changed_files:
            # gitleaks --log-opts accepts git log options to restrict commits
            log_opts = " ".join(f"-- {f}" for f in changed_files)
            cmd.extend(["--log-opts", log_opts])

        if self.config.verbose:
            cmd.append("--verbose")
            logger.info("gitleaks command: %s", " ".join(cmd))

        try:
            result = self._exec(cmd)
        except FileNotFoundError:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.SKIPPED,
                error="gitleaks binary not found",
                duration_seconds=time.monotonic() - start,
            )
        except Exception as exc:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.FAILED,
                error=f"gitleaks execution error: {exc}",
                duration_seconds=time.monotonic() - start,
            )
        finally:
            if ignore_file:
                os.unlink(ignore_file.name)

        duration = time.monotonic() - start

        if self.config.verbose:
            logger.info("gitleaks stderr: %s", result.stderr.strip())

        # gitleaks exit codes: 0 = no leaks, 1 = leaks found, other = error
        if result.returncode not in (0, 1):
            return ToolResult(
                tool=self.name,
                status=ToolStatus.FAILED,
                error=f"gitleaks exited with code {result.returncode}: {result.stderr.strip()[:500]}",
                duration_seconds=duration,
            )

        # Parse JSON output
        raw_data: Any = None
        if result.stdout.strip():
            import json

            try:
                raw_data = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                return ToolResult(
                    tool=self.name,
                    status=ToolStatus.FAILED,
                    error=f"Failed to parse gitleaks JSON output: {exc}",
                    duration_seconds=duration,
                )

        # Normalise findings
        findings: list[Finding] = []
        if raw_data:
            normaliser = GitleaksNormaliser()
            findings = normaliser.normalise(raw_data)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            duration_seconds=duration,
        )
