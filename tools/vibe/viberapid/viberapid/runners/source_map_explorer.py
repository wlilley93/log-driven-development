"""Runner for source-map-explorer — analyses bundle composition via source maps."""

from __future__ import annotations

from pathlib import Path

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.source_map_explorer import SourceMapExplorerNormaliser
from viberapid.runners.base import AsyncToolRunner


class SourceMapExplorerRunner(AsyncToolRunner):
    """Run source-map-explorer to analyse bundle composition via source maps.

    Finds .js files with corresponding .js.map files and analyses them to
    determine which modules contribute the most to bundle size.
    """

    name = "source-map-explorer"
    requires_node = True

    def should_run(self) -> bool:
        if not self._file_exists("package.json"):
            self.skip_reason = "no package.json found"
            return False

        # Need .map files or a dist/ directory to scan
        map_files = self._glob_files("dist/**/*.js.map", "build/**/*.js.map", "out/**/*.js.map")
        has_dist = self._file_exists("dist", "build", "out", ".next")

        if not map_files and not has_dist:
            self.skip_reason = "no source map files (.js.map) or dist/ directory found"
            return False

        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        target = Path(self.target)

        # Find JS files that have corresponding .map files
        js_files = self._find_analysable_files(target)

        if not js_files:
            # Try running on all JS files in dist/ — source-map-explorer
            # can work with inline source maps too
            js_files = self._find_dist_js_files(target)

        if not js_files:
            return self._make_error_result(
                "No JavaScript files with source maps found. "
                "Build the project with source maps enabled first "
                "(e.g., devtool: 'source-map' in webpack config)."
            )

        npx = self._npx_path()
        all_results: list[dict] = []

        # Analyse each JS file individually to avoid CLI arg length limits
        max_files = self.tool_config.get("max_files", 10)
        for js_file in js_files[:max_files]:
            cmd = [npx, "source-map-explorer", str(js_file), "--json"]

            try:
                data, stderr = self._exec_json(cmd, timeout=60)
                if data and isinstance(data, dict):
                    results = data.get("results", [])
                    if results:
                        all_results.extend(results)
                    elif "files" in data:
                        # Older format: flat structure
                        all_results.append(data)
            except Exception:
                # Individual file failure is non-fatal
                continue

        if not all_results:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.PARTIAL,
                findings=[],
                error=(
                    "source-map-explorer did not return valid JSON for any file. "
                    "Ensure source maps are valid and not stripped."
                ),
                metrics={"files_analysed": 0},
            )

        # Normalise the combined results
        combined_data = {"results": all_results}
        normaliser = SourceMapExplorerNormaliser()
        findings = normaliser.normalise(combined_data)

        total_bytes = sum(
            r.get("totalBytes", 0) for r in all_results if isinstance(r, dict)
        )
        total_mapped = sum(
            r.get("mappedBytes", 0) for r in all_results if isinstance(r, dict)
        )

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "files_analysed": len(all_results),
                "total_bytes": total_bytes,
                "total_mapped_bytes": total_mapped,
                "total_findings": len(findings),
            },
        )

    def _find_analysable_files(self, target: Path) -> list[Path]:
        """Find JS files that have corresponding .js.map files."""
        map_files = self._glob_files(
            "dist/**/*.js.map",
            "build/**/*.js.map",
            "out/**/*.js.map",
            ".next/**/*.js.map",
        )

        js_files: list[Path] = []
        for map_file in map_files:
            js_file = map_file.with_suffix("")  # Remove .map to get .js
            if js_file.exists():
                js_files.append(js_file)

        # Sort by size descending to prioritise the largest bundles
        js_files.sort(key=lambda f: f.stat().st_size, reverse=True)
        return js_files

    def _find_dist_js_files(self, target: Path) -> list[Path]:
        """Find JS files in dist-like directories (may have inline source maps)."""
        js_files = self._glob_files(
            "dist/**/*.js",
            "build/**/*.js",
            "out/**/*.js",
        )

        # Filter to substantial files only (>5 KB)
        js_files = [f for f in js_files if f.stat().st_size > 5 * 1024]

        # Sort by size descending
        js_files.sort(key=lambda f: f.stat().st_size, reverse=True)
        return js_files
