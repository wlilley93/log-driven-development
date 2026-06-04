"""Runner for bundlephobia — checks npm package bundle sizes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.bundlephobia import BundlephobiaNormaliser
from viberapid.runners.base import AsyncToolRunner


class BundlephobiaRunner(AsyncToolRunner):
    """Check bundle sizes of npm dependencies via bundlephobia-cli."""

    name = "bundlephobia"
    requires_node = True

    def should_run(self) -> bool:
        if not self._file_exists("package.json"):
            self.skip_reason = "no package.json found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        # Read package.json to get top dependencies
        pkg_path = Path(self.target) / "package.json"
        try:
            pkg_data = json.loads(pkg_path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            return self._make_error_result(f"Failed to read package.json: {exc}")

        deps = pkg_data.get("dependencies", {})
        if not deps:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS,
                findings=[],
                metrics={"packages_checked": 0},
            )

        # Limit to first 20 deps to avoid very long run times
        max_deps = self.tool_config.get("max_deps", 20)
        dep_names = list(deps.keys())[:max_deps]

        npx = self._npx_path()
        results: list[dict[str, Any]] = []

        for dep in dep_names:
            cmd = [npx, "bundlephobia-cli", dep]
            try:
                data, stderr = self._exec_json(cmd, timeout=30)
                if data and isinstance(data, dict):
                    results.append(data)
                elif data and isinstance(data, list):
                    results.extend(data)
            except Exception:
                # Individual package failure is non-fatal
                continue

        if not results:
            # Try alternative: some versions output line-by-line
            return ToolResult(
                tool=self.name,
                status=ToolStatus.PARTIAL,
                findings=[],
                error="bundlephobia-cli did not return JSON for any package",
                metrics={"packages_checked": len(dep_names)},
            )

        normaliser = BundlephobiaNormaliser()
        findings = normaliser.normalise(results)

        total_size = sum(r.get("gzip", 0) for r in results)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "packages_checked": len(results),
                "total_gzip_bytes": total_size,
            },
        )
