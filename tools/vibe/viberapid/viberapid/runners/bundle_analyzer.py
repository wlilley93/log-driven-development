"""Runner for webpack-bundle-analyzer — analyses webpack stats for large chunks."""

from __future__ import annotations

import json
from pathlib import Path

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.bundle_analyzer import BundleAnalyzerNormaliser
from viberapid.runners.base import AsyncToolRunner


class BundleAnalyzerRunner(AsyncToolRunner):
    """Run webpack-bundle-analyzer in JSON mode or parse an existing stats.json.

    Tries to locate webpack stats data in this order:
    1. Pre-existing stats.json in the project root or dist/
    2. Generate stats.json via webpack --json, then parse it
    3. Fall back to reading any stats.json found via glob
    """

    name = "bundle-analyzer"
    requires_node = True

    def should_run(self) -> bool:
        if not self._file_exists("package.json"):
            self.skip_reason = "no package.json found"
            return False

        # Need either a webpack config, stats.json, or a dist directory
        has_webpack_config = self._file_exists(
            "webpack.config.js",
            "webpack.config.ts",
            "webpack.config.cjs",
            "webpack.config.mjs",
        )
        has_stats = self._file_exists("stats.json", "dist/stats.json", "build/stats.json")
        has_dist = self._file_exists("dist", "build")

        if not has_webpack_config and not has_stats and not has_dist:
            self.skip_reason = (
                "no webpack config, stats.json, or dist/ directory found"
            )
            return False

        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        target = Path(self.target)

        # Step 1: Try to load an existing stats.json
        stats_data = self._load_stats_json(target)

        # Step 2: If no stats.json, try to generate one via webpack --json
        if stats_data is None:
            stats_data = self._generate_stats_json(target)

        # Step 3: Fall back to glob for stats.json anywhere in the project
        if stats_data is None:
            stats_files = self._glob_files("**/stats.json")
            for stats_file in stats_files:
                try:
                    stats_data = json.loads(stats_file.read_text())
                    if isinstance(stats_data, dict) and (
                        "assets" in stats_data or "chunks" in stats_data
                    ):
                        break
                    stats_data = None
                except (json.JSONDecodeError, OSError):
                    stats_data = None

        if stats_data is None:
            return self._make_error_result(
                "Could not find or generate a webpack stats.json. "
                "Run `webpack --json > stats.json` first, or ensure "
                "webpack-bundle-analyzer is configured."
            )

        normaliser = BundleAnalyzerNormaliser()
        findings = normaliser.normalise(stats_data)

        # Compute metrics
        assets = stats_data.get("assets", [])
        total_size = sum(
            a.get("size", 0) for a in assets if isinstance(a, dict)
        )
        js_assets = [
            a for a in assets
            if isinstance(a, dict) and a.get("name", "").endswith((".js", ".mjs"))
        ]
        css_assets = [
            a for a in assets
            if isinstance(a, dict) and a.get("name", "").endswith(".css")
        ]

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "total_assets": len(assets),
                "total_size_bytes": total_size,
                "js_assets": len(js_assets),
                "css_assets": len(css_assets),
                "js_total_bytes": sum(a.get("size", 0) for a in js_assets),
                "css_total_bytes": sum(a.get("size", 0) for a in css_assets),
            },
        )

    def _load_stats_json(self, target: Path) -> dict | None:
        """Try to load stats.json from well-known locations."""
        candidates = [
            target / "stats.json",
            target / "dist" / "stats.json",
            target / "build" / "stats.json",
            target / ".next" / "stats.json",
        ]

        for path in candidates:
            if path.exists():
                try:
                    data = json.loads(path.read_text())
                    if isinstance(data, dict) and ("assets" in data or "chunks" in data):
                        return data
                except (json.JSONDecodeError, OSError):
                    continue

        return None

    def _generate_stats_json(self, target: Path) -> dict | None:
        """Try to generate stats.json by running webpack --json."""
        npx = self._npx_path()

        # Only attempt if there is a webpack config
        has_config = any(
            (target / name).exists()
            for name in (
                "webpack.config.js",
                "webpack.config.ts",
                "webpack.config.cjs",
                "webpack.config.mjs",
            )
        )

        if not has_config:
            return None

        cmd = [npx, "webpack", "--json"]
        try:
            data, stderr = self._exec_json(cmd, timeout=120)
            if isinstance(data, dict) and ("assets" in data or "chunks" in data):
                return data
        except Exception:
            pass

        return None
