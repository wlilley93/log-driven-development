"""cloudsplaining runner — AWS IAM policy analysis."""

from __future__ import annotations

import json
from pathlib import Path

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.cloudsplaining import CloudsplainingNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class CloudsplainingRunner(AsyncToolRunner):
    name = "cloudsplaining"
    requires_cloud = True

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "cloudsplaining not installed"
            return False
        return super().should_run()

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        output_dir = Path("/tmp/cloudsplaining-output")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: Download the account authorization details
        auth_file = output_dir / "authorization-details.json"
        if not auth_file.exists():
            dl_cmd = [
                "aws", "iam", "get-account-authorization-details",
                "--output", "json",
            ]
            dl_result = self._exec(dl_cmd, timeout=60)
            if dl_result.returncode != 0:
                return self._make_error_result(
                    f"Failed to download IAM authorization details: {dl_result.stderr[:200]}"
                )
            try:
                auth_file.write_text(dl_result.stdout)
            except OSError as e:
                return self._make_error_result(f"Failed to write auth details: {e}")

        # Step 2: Run cloudsplaining scan
        cmd = [
            self.bin_path,
            "scan",
            "--input-file", str(auth_file),
            "--output", str(output_dir),
            "--skip-open-report",
        ]
        result = self._exec(cmd, timeout=self.config.timeout * 2)

        # Parse the results JSON
        findings = []
        results_file = output_dir / "iam-results.json"
        if not results_file.exists():
            # Try alternative output filenames
            for candidate in output_dir.glob("*.json"):
                if candidate.name != "authorization-details.json":
                    results_file = candidate
                    break

        if results_file.exists():
            try:
                data = json.loads(results_file.read_text())
                normaliser = CloudsplainingNormaliser()
                findings = normaliser.normalise(data)
            except (json.JSONDecodeError, OSError):
                pass

        if result.returncode != 0 and not findings:
            return self._make_error_result(f"cloudsplaining failed: {result.stderr[:200]}")

        status = ToolStatus.SUCCESS if result.returncode == 0 else ToolStatus.PARTIAL
        return ToolResult(tool=self.name, status=status, findings=findings)
