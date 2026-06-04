"""Runner for size-limit — checks bundle size budgets."""

from __future__ import annotations

import json
from pathlib import Path

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.size_limit import SizeLimitNormaliser
from viberapid.runners.base import AsyncToolRunner


class SizeLimitRunner(AsyncToolRunner):
    """Run size-limit to check bundle size against configured budgets."""

    name = "size-limit"
    requires_node = True

    def should_run(self) -> bool:
        if not self._file_exists("package.json"):
            self.skip_reason = "no package.json found"
            return False

        # size-limit needs config: either .size-limit.json or size-limit key in package.json
        if self._file_exists(".size-limit.json", ".size-limit.js", ".size-limit.cjs"):
            return True

        # Check package.json for size-limit config
        pkg_path = Path(self.target) / "package.json"
        try:
            pkg_data = json.loads(pkg_path.read_text())
            if "size-limit" in pkg_data:
                return True
        except (json.JSONDecodeError, OSError):
            pass

        self.skip_reason = "no size-limit configuration found (.size-limit.json or package.json)"
        return False

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        npx = self._npx_path()
        cmd = [npx, "size-limit", "--json"]

        data, stderr = self._exec_json(cmd)

        if data is None:
            return self._make_error_result(
                f"size-limit failed to produce JSON output. stderr: {stderr[:500]}"
            )

        normaliser = SizeLimitNormaliser()
        findings = normaliser.normalise(data)

        violations = sum(
            1 for entry in data
            if isinstance(entry, dict) and not entry.get("passed", True)
        )

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "entries_checked": len(data) if isinstance(data, list) else 0,
                "budget_violations": violations,
            },
        )
