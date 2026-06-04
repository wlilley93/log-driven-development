"""CodeQL runner — deep SAST analysis (deep mode only)."""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from vibescan.models import Finding, ToolResult, ToolStatus
from vibescan.normalisers.codeql import CodeqlNormaliser
from vibescan.runners.base import AsyncToolRunner

logger = logging.getLogger(__name__)

# Languages CodeQL can auto-detect
CODEQL_LANGUAGES = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "javascript",
    ".jsx": "javascript",
    ".tsx": "javascript",
    ".java": "java",
    ".cs": "csharp",
    ".go": "go",
    ".rb": "ruby",
    ".cpp": "cpp",
    ".c": "cpp",
    ".swift": "swift",
}


class CodeqlRunner(AsyncToolRunner):
    name = "codeql"
    deep_only = True

    def should_run(self) -> bool:
        if not shutil.which("codeql"):
            self.skip_reason = "codeql binary not found (install from https://github.com/github/codeql-cli-binaries)"
            return False
        return True

    def _detect_language(self) -> str | None:
        """Detect the primary language of the target directory."""
        target = Path(self.target)
        counts: dict[str, int] = {}
        for ext, lang in CODEQL_LANGUAGES.items():
            count = sum(1 for _ in target.rglob(f"*{ext}"))
            if count > 0:
                counts[lang] = counts.get(lang, 0) + count

        if not counts:
            return None

        return max(counts, key=counts.get)  # type: ignore[arg-type]

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        start = time.monotonic()

        # Detect language
        tc = self.tool_config
        language = tc.get("language") or self._detect_language()
        if not language:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.SKIPPED,
                error="Could not detect a supported language for CodeQL",
                duration_seconds=time.monotonic() - start,
            )

        if self.config.verbose:
            logger.info("codeql: detected language %s", language)

        # Create temporary database directory
        with tempfile.TemporaryDirectory(prefix="vibescan-codeql-") as db_dir:
            db_path = Path(db_dir) / "codeql-db"

            # Step 1: Create the CodeQL database
            create_cmd = [
                "codeql",
                "database",
                "create",
                str(db_path),
                "--language",
                language,
                "--source-root",
                self.target,
                "--overwrite",
            ]

            if self.config.verbose:
                logger.info("codeql create command: %s", " ".join(create_cmd))

            try:
                create_result = self._exec(
                    create_cmd, timeout=self.config.timeout * 3
                )
            except FileNotFoundError:
                return ToolResult(
                    tool=self.name,
                    status=ToolStatus.SKIPPED,
                    error="codeql binary not found",
                    duration_seconds=time.monotonic() - start,
                )
            except Exception as exc:
                error_msg = str(exc)
                if "TimeoutExpired" in type(exc).__name__:
                    return ToolResult(
                        tool=self.name,
                        status=ToolStatus.TIMEOUT,
                        error="codeql database creation timed out",
                        duration_seconds=time.monotonic() - start,
                    )
                return ToolResult(
                    tool=self.name,
                    status=ToolStatus.FAILED,
                    error=f"codeql database create failed: {error_msg}",
                    duration_seconds=time.monotonic() - start,
                )

            if create_result.returncode != 0:
                return ToolResult(
                    tool=self.name,
                    status=ToolStatus.FAILED,
                    error=f"codeql database create failed (exit {create_result.returncode}): {create_result.stderr.strip()[:500]}",
                    duration_seconds=time.monotonic() - start,
                )

            if self.config.verbose:
                logger.info(
                    "codeql database created, stderr: %s",
                    create_result.stderr.strip()[:500],
                )

            # Step 2: Analyze the database
            sarif_path = Path(db_dir) / "results.sarif"
            query_suite = tc.get(
                "query_suite", f"codeql/{language}-queries:codeql-suites/{language}-security-and-quality.qls"
            )

            analyze_cmd = [
                "codeql",
                "database",
                "analyze",
                str(db_path),
                query_suite,
                "--format",
                "sarif-latest",
                "--output",
                str(sarif_path),
            ]

            if self.config.verbose:
                logger.info("codeql analyze command: %s", " ".join(analyze_cmd))

            try:
                analyze_result = self._exec(
                    analyze_cmd, timeout=self.config.timeout * 5
                )
            except Exception as exc:
                error_msg = str(exc)
                if "TimeoutExpired" in type(exc).__name__:
                    return ToolResult(
                        tool=self.name,
                        status=ToolStatus.TIMEOUT,
                        error="codeql analysis timed out",
                        duration_seconds=time.monotonic() - start,
                    )
                return ToolResult(
                    tool=self.name,
                    status=ToolStatus.FAILED,
                    error=f"codeql analyze failed: {error_msg}",
                    duration_seconds=time.monotonic() - start,
                )

            duration = time.monotonic() - start

            if analyze_result.returncode != 0:
                return ToolResult(
                    tool=self.name,
                    status=ToolStatus.FAILED,
                    error=f"codeql analyze failed (exit {analyze_result.returncode}): {analyze_result.stderr.strip()[:500]}",
                    duration_seconds=duration,
                )

            # Parse SARIF output
            raw_data: dict[str, Any] | None = None
            if sarif_path.exists():
                try:
                    with open(sarif_path) as f:
                        raw_data = json.load(f)
                except (json.JSONDecodeError, OSError) as exc:
                    return ToolResult(
                        tool=self.name,
                        status=ToolStatus.FAILED,
                        error=f"Failed to parse codeql SARIF output: {exc}",
                        duration_seconds=duration,
                    )

            # Normalise findings
            findings: list[Finding] = []
            if raw_data:
                normaliser = CodeqlNormaliser()
                findings = normaliser.normalise(raw_data)

            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS,
                findings=findings,
                duration_seconds=duration,
            )
