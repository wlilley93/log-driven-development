"""Runner for cost-of-modules — measures disk cost of node_modules."""

from __future__ import annotations

from pathlib import Path

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.cost_of_modules import CostOfModulesNormaliser
from viberapid.runners.base import AsyncToolRunner


class CostOfModulesRunner(AsyncToolRunner):
    """Run cost-of-modules to measure node_modules disk usage per package."""

    name = "cost-of-modules"
    requires_node = True

    def should_run(self) -> bool:
        if not self._file_exists("package.json"):
            self.skip_reason = "no package.json found"
            return False
        if not (Path(self.target) / "node_modules").is_dir():
            self.skip_reason = "no node_modules directory found (run npm install first)"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        npx = self._npx_path()
        cmd = [npx, "cost-of-modules", "--json"]

        data, stderr = self._exec_json(cmd, timeout=180)

        if data is None:
            return self._make_error_result(
                f"cost-of-modules failed to produce JSON output. stderr: {stderr[:500]}"
            )

        normaliser = CostOfModulesNormaliser()
        findings = normaliser.normalise(data)

        total_size = 0
        module_count = 0
        if isinstance(data, list):
            total_size = sum(m.get("size", 0) for m in data if isinstance(m, dict))
            module_count = len(data)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "total_modules": module_count,
                "total_disk_bytes": total_size,
            },
        )
