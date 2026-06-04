"""prowler runner — AWS security assessment."""

from __future__ import annotations

import json

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.prowler import ProwlerNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class ProwlerRunner(AsyncToolRunner):
    name = "prowler"
    requires_cloud = True

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "prowler not installed"
            return False
        return super().should_run()

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        cmd = [self.bin_path, "--output-format", "json", "--output-directory", "/tmp/prowler"]
        result = self._exec(cmd, timeout=self.config.timeout * 4)

        findings = []
        # Prowler outputs NDJSON (one JSON object per line)
        if result.stdout.strip():
            normaliser = ProwlerNormaliser()
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    findings.extend(normaliser.normalise(data))
                except (json.JSONDecodeError, Exception):
                    continue

        if result.returncode not in (0, 1, 2) and not findings:
            return self._make_error_result(f"prowler failed: {result.stderr[:200]}")

        status = ToolStatus.SUCCESS if result.returncode == 0 else ToolStatus.PARTIAL
        return ToolResult(tool=self.name, status=status, findings=findings)
