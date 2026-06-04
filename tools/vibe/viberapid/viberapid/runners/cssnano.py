"""Runner for cssnano — dry-run CSS minification analysis."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.cssnano import CssnanoNormaliser
from viberapid.runners.base import AsyncToolRunner


class CssnanoRunner(AsyncToolRunner):
    """Run cssnano in dry-run mode to quantify CSS minification savings
    without modifying source files. Uses PostCSS + cssnano via a temporary
    config to measure the delta between original and minified output."""

    name = "cssnano"
    requires_node = True

    def should_run(self) -> bool:
        css_files = self._glob_files("*.css")
        css_files = [
            f for f in css_files
            if "node_modules" not in str(f)
            and ".next" not in str(f)
            and "vendor" not in str(f)
            and ".min." not in str(f)
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
            and ".min." not in str(f)
        ]

        if not css_files:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS,
                findings=[],
                metrics={"css_files_checked": 0},
            )

        npx = self._npx_path()
        analysis_results: list[dict[str, Any]] = []

        with tempfile.TemporaryDirectory(prefix="viberapid-cssnano-") as tmp_dir:
            # Write a minimal PostCSS config that applies cssnano default preset
            config_path = Path(tmp_dir) / "postcss.config.cjs"
            config_path.write_text(
                "module.exports = {\n"
                "  plugins: [\n"
                "    require('cssnano')({ preset: 'default' })\n"
                "  ]\n"
                "};\n"
            )

            for css_file in css_files[:50]:
                original_size = css_file.stat().st_size
                if original_size == 0:
                    continue

                relative_path = str(css_file.relative_to(self.target))
                output_path = Path(tmp_dir) / css_file.name

                # Run postcss with cssnano via npx
                cmd = [
                    npx, "postcss",
                    str(css_file),
                    "--config", tmp_dir,
                    "--no-map",
                    "-o", str(output_path),
                ]

                result = self._exec(cmd, timeout=30)

                if output_path.exists():
                    minified_size = output_path.stat().st_size
                    savings = original_size - minified_size
                    pct = (savings / original_size * 100) if original_size > 0 else 0

                    analysis_results.append({
                        "file": relative_path,
                        "original_size": original_size,
                        "minified_size": minified_size,
                        "savings": max(0, savings),
                        "savings_pct": round(max(0, pct), 1),
                    })
                else:
                    # PostCSS/cssnano failed for this file
                    analysis_results.append({
                        "file": relative_path,
                        "original_size": original_size,
                        "minified_size": original_size,
                        "savings": 0,
                        "savings_pct": 0,
                        "error": result.stderr.strip()[:200] if result.stderr else None,
                    })

        total_original = sum(r["original_size"] for r in analysis_results)
        total_minified = sum(r["minified_size"] for r in analysis_results)
        total_savings = sum(r["savings"] for r in analysis_results)

        data = {
            "files": analysis_results,
            "total_original": total_original,
            "total_minified": total_minified,
            "total_savings": total_savings,
        }

        normaliser = CssnanoNormaliser()
        findings = normaliser.normalise(data)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "css_files_checked": len(analysis_results),
                "total_original_bytes": total_original,
                "total_minified_bytes": total_minified,
                "total_savings_bytes": total_savings,
            },
        )
