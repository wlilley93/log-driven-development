"""Runner for stylestats — CSS complexity and quality metrics."""

from __future__ import annotations

import json
from typing import Any

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.stylestats import StylestatsNormaliser
from viberapid.runners.base import AsyncToolRunner


class StylestatsRunner(AsyncToolRunner):
    """Run stylestats to analyse CSS complexity metrics."""

    name = "stylestats"
    requires_node = True

    def should_run(self) -> bool:
        css_files = self._glob_files("*.css")
        css_files = [
            f for f in css_files
            if "node_modules" not in str(f)
            and ".next" not in str(f)
            and "vendor" not in str(f)
        ]
        if not css_files:
            self.skip_reason = "no CSS files found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        css_files = self._glob_files("*.css")
        css_files = [
            f for f in css_files
            if "node_modules" not in str(f)
            and ".next" not in str(f)
            and "vendor" not in str(f)
        ]

        if not css_files:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS,
                findings=[],
                metrics={"css_files_checked": 0},
            )

        npx = self._npx_path()
        results: list[dict[str, Any]] = []

        for css_file in css_files[:30]:  # limit to 30 files
            cmd = [npx, "stylestats", str(css_file), "--format", "json"]
            data, stderr = self._exec_json(cmd, timeout=30)

            if data is None:
                continue

            relative_path = str(css_file.relative_to(self.target))
            results.append({
                "file": relative_path,
                "stats": data,
            })

        normaliser = StylestatsNormaliser()
        findings = normaliser.normalise(results)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={"css_files_checked": len(results)},
        )
