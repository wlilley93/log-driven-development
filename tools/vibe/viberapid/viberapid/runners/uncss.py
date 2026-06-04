"""Runner for UnCSS — detects unused CSS rules by rendering pages."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.uncss import UncssNormaliser
from viberapid.runners.base import AsyncToolRunner


class UncssRunner(AsyncToolRunner):
    """Run UnCSS to detect unused CSS by rendering HTML pages and comparing
    against stylesheets. UnCSS uses PhantomJS/jsdom to load HTML and determine
    which CSS selectors are actually used."""

    name = "uncss"
    requires_node = True

    def should_run(self) -> bool:
        # Need both HTML and CSS files to compare
        html_files = self._glob_files("*.html", "*.htm")
        html_files = [
            f for f in html_files
            if "node_modules" not in str(f)
            and ".next" not in str(f)
            and "vendor" not in str(f)
        ]
        if not html_files:
            self.skip_reason = "no HTML files found"
            return False

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
        html_files = self._glob_files("*.html", "*.htm")
        html_files = [
            f for f in html_files
            if "node_modules" not in str(f)
            and ".next" not in str(f)
            and "vendor" not in str(f)
        ]

        css_files = self._glob_files("*.css")
        css_files = [
            f for f in css_files
            if "node_modules" not in str(f)
            and ".next" not in str(f)
            and "vendor" not in str(f)
        ]

        if not html_files or not css_files:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS,
                findings=[],
                metrics={"css_files_checked": 0, "html_files_checked": 0},
            )

        npx = self._npx_path()
        analysis_results: list[dict[str, Any]] = []

        # UnCSS accepts HTML files and outputs cleaned CSS to stdout.
        # Process each CSS file by passing HTML files as context.
        html_paths = [str(f) for f in html_files[:100]]

        for css_file in css_files[:50]:
            original_size = css_file.stat().st_size
            relative_path = str(css_file.relative_to(self.target))

            # uncss takes HTML files as positional args and --stylesheets for CSS
            cmd = [
                npx, "uncss",
                *html_paths[:20],  # Limit HTML files per invocation
                "--stylesheets", str(css_file),
                "--timeout", "10000",
            ]

            result = self._exec(cmd, timeout=60)

            if result.returncode == 0 and result.stdout.strip():
                cleaned_size = len(result.stdout.encode("utf-8"))
                savings = original_size - cleaned_size
                pct = (savings / original_size * 100) if original_size > 0 else 0

                analysis_results.append({
                    "file": relative_path,
                    "original_size": original_size,
                    "cleaned_size": cleaned_size,
                    "savings": max(0, savings),
                    "savings_pct": round(max(0, pct), 1),
                })
            else:
                # uncss failed for this file; record without savings data
                analysis_results.append({
                    "file": relative_path,
                    "original_size": original_size,
                    "cleaned_size": original_size,
                    "savings": 0,
                    "savings_pct": 0,
                    "error": result.stderr.strip()[:200] if result.stderr else None,
                })

        total_original = sum(r["original_size"] for r in analysis_results)
        total_cleaned = sum(r["cleaned_size"] for r in analysis_results)
        total_savings = sum(r["savings"] for r in analysis_results)

        data = {
            "files": analysis_results,
            "total_original": total_original,
            "total_cleaned": total_cleaned,
            "total_savings": total_savings,
        }

        normaliser = UncssNormaliser()
        findings = normaliser.normalise(data)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "css_files_checked": len(analysis_results),
                "html_files_used": len(html_paths),
                "total_original_bytes": total_original,
                "total_cleaned_bytes": total_cleaned,
                "total_savings_bytes": total_savings,
            },
        )
