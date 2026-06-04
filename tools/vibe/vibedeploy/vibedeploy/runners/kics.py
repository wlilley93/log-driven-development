"""kics runner — Keeping Infrastructure as Code Secure scanner."""

from __future__ import annotations

import json
from pathlib import Path

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.kics import KicsNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class KicsRunner(AsyncToolRunner):
    name = "kics"

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "kics not installed"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        # kics writes results to a file rather than stdout
        output_dir = Path("/tmp/kics-results")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "results.json"

        # Clean up previous results
        if output_file.exists():
            output_file.unlink()

        cmd = [
            self.bin_path, "scan",
            "-p", self.target,
            "--output-path", str(output_dir),
            "--report-formats", "json",
        ]

        result = self._exec(cmd, timeout=self.config.timeout * 2)

        # Read the output file
        data = None
        if output_file.exists():
            try:
                data = json.loads(output_file.read_text())
            except (json.JSONDecodeError, OSError):
                pass

        if data is None:
            # Try parsing stdout as fallback
            if result.stdout.strip():
                try:
                    data = json.loads(result.stdout)
                except (json.JSONDecodeError, ValueError):
                    pass

        if data is None:
            stderr = result.stderr.strip() if result.stderr else "no output"
            return self._make_error_result(f"kics failed: {stderr[:200]}")

        normaliser = KicsNormaliser()
        findings = normaliser.normalise(data)
        status = ToolStatus.SUCCESS if not findings else ToolStatus.PARTIAL
        return ToolResult(tool=self.name, status=status, findings=findings)
