"""Runner for esbuild benchmark — compares current dist size against esbuild baseline."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.esbuild_bench import EsbuildBenchNormaliser
from viberapid.runners.base import AsyncToolRunner


class EsbuildBenchRunner(AsyncToolRunner):
    """Run esbuild as a benchmark build and compare output size vs current dist.

    This runner:
    1. Detects the project entry point (from package.json main/module or common paths)
    2. Runs esbuild --bundle --minify on the entry point
    3. Measures the resulting output size
    4. Compares it against the current dist/ output
    5. Reports the gap as a finding
    """

    name = "esbuild-bench"
    requires_node = True

    def should_run(self) -> bool:
        if not self._file_exists("package.json"):
            self.skip_reason = "no package.json found"
            return False

        # Need at least a dist/ or build/ directory to compare against
        if not self._file_exists("dist", "build", "out", ".next"):
            self.skip_reason = "no dist/ or build/ directory found to compare against"
            return False

        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        target = Path(self.target)

        # Step 1: Detect entry point
        entry_point = self._detect_entry_point(target)
        if entry_point is None:
            return self._make_error_result(
                "Could not detect an entry point. Ensure package.json has a "
                "'main', 'module', or 'source' field, or that src/index.ts exists."
            )

        # Step 2: Measure current dist size
        current_files = self._measure_dist(target)
        current_total = sum(f["size"] for f in current_files)

        if current_total == 0:
            return self._make_error_result(
                "Current dist directory is empty or contains no JS/CSS files. "
                "Build the project first."
            )

        # Step 3: Run esbuild benchmark
        npx = self._npx_path()
        outfile = target / ".viberapid-esbuild-bench-out.js"

        # Determine the platform from package.json
        platform = self._detect_platform(target)

        cmd = [
            npx, "esbuild",
            str(entry_point),
            "--bundle",
            "--minify",
            f"--outfile={outfile}",
            f"--platform={platform}",
            "--sourcemap=external",
            "--tree-shaking=true",
            "--target=es2020",
        ]

        # Add external patterns for node_modules in node platform
        if platform == "node":
            cmd.append("--packages=external")

        start_time = time.monotonic()
        try:
            result = self._exec(cmd, timeout=120)
        except Exception as exc:
            return self._make_error_result(f"esbuild failed: {exc}")
        finally:
            # Always clean up temp file
            if outfile.exists():
                esbuild_size = outfile.stat().st_size
                outfile.unlink(missing_ok=True)
            else:
                esbuild_size = 0

            # Clean up source map too
            map_file = outfile.with_suffix(".js.map")
            map_file.unlink(missing_ok=True)

        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        if result.returncode != 0 and esbuild_size == 0:
            return self._make_error_result(
                f"esbuild exited with code {result.returncode}. "
                f"stderr: {result.stderr[:500]}"
            )

        # Step 4: Compute gap
        gap = current_total - esbuild_size
        gap_pct = (gap / esbuild_size * 100) if esbuild_size > 0 else 0

        bench_data: dict[str, Any] = {
            "entry_point": str(entry_point.relative_to(target)),
            "esbuild_output_size": esbuild_size,
            "current_dist_size": current_total,
            "gap": max(gap, 0),
            "gap_pct": round(max(gap_pct, 0), 1),
            "esbuild_time_ms": elapsed_ms,
            "output_files": [{"path": ".viberapid-esbuild-bench-out.js", "size": esbuild_size}],
            "current_files": current_files,
        }

        normaliser = EsbuildBenchNormaliser()
        findings = normaliser.normalise(bench_data)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "entry_point": str(entry_point.relative_to(target)),
                "esbuild_output_bytes": esbuild_size,
                "current_dist_bytes": current_total,
                "gap_bytes": max(gap, 0),
                "gap_pct": round(max(gap_pct, 0), 1),
                "esbuild_time_ms": elapsed_ms,
            },
        )

    def _detect_entry_point(self, target: Path) -> Path | None:
        """Detect the project entry point from package.json or common paths."""
        pkg_path = target / "package.json"
        try:
            pkg_data = json.loads(pkg_path.read_text())
        except (json.JSONDecodeError, OSError):
            pkg_data = {}

        # Try fields in order of preference
        for field in ("source", "module", "main"):
            entry = pkg_data.get(field)
            if entry:
                entry_path = target / entry
                if entry_path.exists():
                    return entry_path

        # Common entry point paths
        candidates = [
            "src/index.ts",
            "src/index.tsx",
            "src/index.js",
            "src/index.jsx",
            "src/main.ts",
            "src/main.tsx",
            "src/main.js",
            "index.ts",
            "index.js",
        ]

        for candidate in candidates:
            path = target / candidate
            if path.exists():
                return path

        return None

    def _measure_dist(self, target: Path) -> list[dict[str, Any]]:
        """Measure total JS/CSS size in the dist-like directories."""
        files: list[dict[str, Any]] = []

        for dir_name in ("dist", "build", "out"):
            dist_dir = target / dir_name
            if not dist_dir.is_dir():
                continue

            for ext in ("**/*.js", "**/*.mjs", "**/*.css"):
                for filepath in dist_dir.rglob(ext.split("/")[-1]):
                    # Skip source maps and node_modules
                    rel = str(filepath.relative_to(target))
                    if ".map" in rel or "node_modules" in rel:
                        continue
                    try:
                        size = filepath.stat().st_size
                        files.append({
                            "path": rel,
                            "size": size,
                        })
                    except OSError:
                        continue

        return files

    def _detect_platform(self, target: Path) -> str:
        """Detect whether the project targets browser or node."""
        pkg_path = target / "package.json"
        try:
            pkg_data = json.loads(pkg_path.read_text())
        except (json.JSONDecodeError, OSError):
            return "browser"

        # If package.json has "browser" field, target browser
        if "browser" in pkg_data:
            return "browser"

        # Check for common indicators
        deps = set(pkg_data.get("dependencies", {}).keys())
        dev_deps = set(pkg_data.get("devDependencies", {}).keys())
        all_deps = deps | dev_deps

        browser_indicators = {"react", "vue", "angular", "svelte", "webpack", "vite"}
        node_indicators = {"express", "fastify", "koa", "hapi", "nestjs"}

        if browser_indicators & all_deps:
            return "browser"
        if node_indicators & all_deps:
            return "node"

        return "browser"
