"""scoutsuite runner — multi-cloud security assessment."""

from __future__ import annotations

import json
from pathlib import Path

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.scoutsuite import ScoutSuiteNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class ScoutSuiteRunner(AsyncToolRunner):
    name = "scoutsuite"
    requires_cloud = True

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "ScoutSuite not installed"
            return False
        return super().should_run()

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        # Determine cloud provider from config
        provider = self.config.cloud or "aws"
        output_dir = Path("/tmp/scoutsuite-report")

        cmd = [
            self.bin_path,
            provider,
            "--no-browser",
            "--report-dir", str(output_dir),
        ]
        result = self._exec(cmd, timeout=self.config.timeout * 4)

        if result.returncode != 0 and not output_dir.exists():
            return self._make_error_result(f"ScoutSuite failed: {result.stderr[:200]}")

        # ScoutSuite writes a scoutsuite-results/scoutsuite_results_*.js file
        # containing JSON after stripping the JS variable assignment
        findings = []
        results_dir = output_dir / "scoutsuite-results"
        if results_dir.exists():
            for js_file in results_dir.glob("scoutsuite_results_*.js"):
                try:
                    content = js_file.read_text(errors="replace")
                    # Strip JS variable assignment: "scoutsuite_results = {...}"
                    if "=" in content:
                        content = content.split("=", 1)[1].strip().rstrip(";")
                    data = json.loads(content)
                    normaliser = ScoutSuiteNormaliser()
                    findings = normaliser.normalise(data)
                except (json.JSONDecodeError, OSError):
                    continue
                break

        status = ToolStatus.SUCCESS if result.returncode == 0 else ToolStatus.PARTIAL
        return ToolResult(tool=self.name, status=status, findings=findings)
