"""Runner for PurgeCSS — finds unused CSS selectors."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.purgecss import PurgecssNormaliser
from viberapid.runners.base import AsyncToolRunner


class PurgecssRunner(AsyncToolRunner):
    """Run PurgeCSS to detect unused CSS by comparing CSS files against content files."""

    name = "purgecss"
    requires_node = True

    def should_run(self) -> bool:
        if not self._file_exists("package.json"):
            self.skip_reason = "no package.json found"
            return False
        css_files = self._glob_files("*.css")
        if not css_files:
            self.skip_reason = "no CSS files found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        # Find CSS files
        css_files = self._glob_files("*.css")
        # Exclude node_modules and common vendor dirs
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

        # Find content files (HTML, JS, JSX, TSX, Vue, etc.)
        content_files = self._glob_files(
            "*.html", "*.htm", "*.js", "*.jsx", "*.ts", "*.tsx",
            "*.vue", "*.svelte", "*.php",
        )
        content_files = [
            f for f in content_files
            if "node_modules" not in str(f)
            and ".next" not in str(f)
        ]

        if not content_files:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.PARTIAL,
                findings=[],
                error="No content files found to compare against CSS",
                metrics={"css_files_checked": len(css_files)},
            )

        npx = self._npx_path()
        analysis_results: list[dict[str, Any]] = []

        with tempfile.TemporaryDirectory(prefix="viberapid-purgecss-") as tmp_dir:
            # Build comma-separated file lists (limit to prevent arg too long)
            css_paths = [str(f) for f in css_files[:50]]
            content_paths = [str(f) for f in content_files[:200]]

            cmd = [
                npx, "purgecss",
                "--css", *css_paths,
                "--content", *content_paths,
                "--output", tmp_dir,
            ]

            result = self._exec(cmd, timeout=120)

            # Compare original sizes with purged sizes
            for css_file in css_files[:50]:
                original_size = css_file.stat().st_size
                purged_name = css_file.name
                purged_path = Path(tmp_dir) / purged_name

                if purged_path.exists():
                    purged_size = purged_path.stat().st_size
                else:
                    # If purgecss did not produce output, skip
                    continue

                savings = original_size - purged_size
                pct = (savings / original_size * 100) if original_size > 0 else 0

                relative_path = str(css_file.relative_to(self.target))

                analysis_results.append({
                    "file": relative_path,
                    "original_size": original_size,
                    "purged_size": purged_size,
                    "savings": savings,
                    "savings_pct": round(pct, 1),
                })

        total_original = sum(r["original_size"] for r in analysis_results)
        total_purged = sum(r["purged_size"] for r in analysis_results)
        total_savings = sum(r["savings"] for r in analysis_results)

        data = {
            "files": analysis_results,
            "total_original": total_original,
            "total_purged": total_purged,
            "total_savings": total_savings,
        }

        normaliser = PurgecssNormaliser()
        findings = normaliser.normalise(data)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "css_files_checked": len(analysis_results),
                "total_original_bytes": total_original,
                "total_purged_bytes": total_purged,
                "total_savings_bytes": total_savings,
            },
        )
