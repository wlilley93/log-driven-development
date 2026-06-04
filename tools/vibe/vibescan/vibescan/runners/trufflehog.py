"""TruffleHog runner — secret detection with verification support."""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
import time
from typing import Any

from vibescan.models import Finding, ToolResult, ToolStatus
from vibescan.normalisers.trufflehog import TrufflehogNormaliser
from vibescan.runners.base import AsyncToolRunner

logger = logging.getLogger(__name__)


class TrufflehogRunner(AsyncToolRunner):
    name = "trufflehog"
    is_secret_scanner = True

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "trufflehog binary not found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        start = time.monotonic()
        normaliser = TrufflehogNormaliser()
        all_findings: list[Finding] = []

        # Run 1: verified secrets only
        verified_data = self._run_trufflehog(verified_only=True)
        if isinstance(verified_data, ToolResult):
            # Error occurred
            return verified_data

        if verified_data:
            all_findings.extend(normaliser.normalise(verified_data))

        # Run 2: all secrets (unverified included)
        all_data = self._run_trufflehog(verified_only=False)
        if isinstance(all_data, ToolResult):
            # Error in second pass — return partial results from first
            return ToolResult(
                tool=self.name,
                status=ToolStatus.PARTIAL,
                findings=all_findings,
                error=all_data.error,
                duration_seconds=time.monotonic() - start,
            )

        if all_data:
            unverified_findings = normaliser.normalise(all_data)
            # Deduplicate: only add findings not already found in verified pass
            verified_keys = {
                (f.file, f.line, f.rule_id) for f in all_findings
            }
            for finding in unverified_findings:
                key = (finding.file, finding.line, finding.rule_id)
                if key not in verified_keys:
                    all_findings.append(finding)

        duration = time.monotonic() - start

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=all_findings,
            duration_seconds=duration,
        )

    def _run_trufflehog(
        self, verified_only: bool = False
    ) -> list[dict[str, Any]] | ToolResult:
        """Execute trufflehog and return parsed NDJSON results or a ToolResult on error."""
        cmd = [
            self.bin_path,
            "filesystem",
            self.target,
            "--json",
        ]

        if verified_only:
            cmd.append("--only-verified")

        # Exclude paths from config (write to temp file for --exclude-paths)
        tc = self.tool_config
        exclude_paths: list[str] = tc.get("exclude_paths", [])
        exclude_file = None
        if exclude_paths:
            exclude_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
            for p in exclude_paths:
                exclude_file.write(p + "\n")
            exclude_file.close()
            cmd.extend(["--exclude-paths", exclude_file.name])

        if self.config.verbose:
            logger.info(
                "trufflehog command (%s): %s",
                "verified" if verified_only else "all",
                " ".join(cmd),
            )

        try:
            result = self._exec(cmd)
        except FileNotFoundError:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.SKIPPED,
                error="trufflehog binary not found",
            )
        except Exception as exc:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.FAILED,
                error=f"trufflehog execution error: {exc}",
            )
        finally:
            if exclude_file:
                import os
                os.unlink(exclude_file.name)

        if self.config.verbose:
            logger.info("trufflehog stderr: %s", result.stderr.strip()[:500])

        # trufflehog outputs newline-delimited JSON (one JSON object per line)
        records: list[dict[str, Any]] = []
        if result.stdout.strip():
            for line in result.stdout.strip().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    if self.config.verbose:
                        logger.warning(
                            "trufflehog: skipping non-JSON line: %s", line[:100]
                        )

        return records
