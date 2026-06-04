"""KICS runner — Infrastructure as Code scanner."""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from vibescan.models import Finding, ToolResult, ToolStatus
from vibescan.normalisers.kics import KicsNormaliser
from vibescan.runners.base import AsyncToolRunner

logger = logging.getLogger(__name__)

# File patterns that indicate IaC content
IAC_FILES = [
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
]
IAC_EXTENSIONS = [
    ".tf",         # Terraform
    ".tfvars",     # Terraform variables
    ".yaml",       # Potential k8s manifests
    ".yml",        # Potential k8s manifests
]
IAC_GLOBS = [
    "*.tf",
    "Dockerfile*",
    "docker-compose*",
]


class KicsRunner(AsyncToolRunner):
    name = "kics"

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "kics binary not found"
            return False

        # Check if IaC files exist in target
        has_iac = False

        # Check explicit filenames
        for fname in IAC_FILES:
            if self._file_exists(fname):
                has_iac = True
                break

        # Check for terraform files
        if not has_iac:
            target = Path(self.target)
            for ext in (".tf", ".tfvars"):
                if any(target.rglob(f"*{ext}")):
                    has_iac = True
                    break

        # Check for kubernetes-style YAML (look for 'apiVersion' in yaml files)
        if not has_iac:
            target = Path(self.target)
            for yml in target.rglob("*.y*ml"):
                try:
                    content = yml.read_text(errors="ignore")[:500]
                    if "apiVersion" in content or "kind:" in content:
                        has_iac = True
                        break
                except OSError:
                    continue

        if not has_iac:
            self.skip_reason = "no IaC files found (Dockerfile, docker-compose, *.tf, k8s YAML)"
            return False

        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        start = time.monotonic()

        with tempfile.TemporaryDirectory(prefix="vibescan-kics-") as tmp_dir:
            output_path = Path(tmp_dir) / "results.json"

            cmd = [
                self.bin_path,
                "scan",
                "-p",
                self.target,
                "--output-path",
                tmp_dir,
                "--output-name",
                "results",
                "--report-formats",
                "json",
            ]

            if self.config.verbose:
                logger.info("kics command: %s", " ".join(cmd))

            try:
                result = self._exec(cmd)
            except FileNotFoundError:
                return ToolResult(
                    tool=self.name,
                    status=ToolStatus.SKIPPED,
                    error="kics binary not found",
                    duration_seconds=time.monotonic() - start,
                )
            except Exception as exc:
                return ToolResult(
                    tool=self.name,
                    status=ToolStatus.FAILED,
                    error=f"kics execution error: {exc}",
                    duration_seconds=time.monotonic() - start,
                )

            duration = time.monotonic() - start

            if self.config.verbose:
                logger.info("kics stderr: %s", result.stderr.strip()[:500])

            # kics exit codes: 0 = no findings, 50 = findings found, 40+ = partial, other = error
            # kics writes output to file, not stdout
            raw_data: dict[str, Any] | None = None

            if output_path.exists():
                try:
                    with open(output_path) as f:
                        raw_data = json.load(f)
                except (json.JSONDecodeError, OSError) as exc:
                    return ToolResult(
                        tool=self.name,
                        status=ToolStatus.FAILED,
                        error=f"Failed to parse kics output: {exc}",
                        duration_seconds=duration,
                    )
            elif result.stdout.strip():
                # Fallback: try parsing stdout
                try:
                    raw_data = json.loads(result.stdout)
                except json.JSONDecodeError:
                    pass

            if not raw_data and result.returncode not in (0, 50):
                return ToolResult(
                    tool=self.name,
                    status=ToolStatus.FAILED,
                    error=f"kics exited with code {result.returncode}: {result.stderr.strip()[:500]}",
                    duration_seconds=duration,
                )

            # Normalise findings
            findings: list[Finding] = []
            if raw_data:
                normaliser = KicsNormaliser()
                findings = normaliser.normalise(raw_data)

            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS,
                findings=findings,
                duration_seconds=duration,
            )
