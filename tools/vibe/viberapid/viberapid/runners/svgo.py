"""Runner for SVGO — SVG optimisation analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.svgo import SvgoNormaliser
from viberapid.runners.base import AsyncToolRunner


class SvgoRunner(AsyncToolRunner):
    """Run SVGO in dry-run mode to analyse SVG optimisation potential."""

    name = "svgo"
    requires_node = True

    def should_run(self) -> bool:
        svg_files = self._glob_files("*.svg")
        svg_files = [
            f for f in svg_files
            if "node_modules" not in str(f)
            and ".next" not in str(f)
            and ".git" not in str(f)
        ]
        if not svg_files:
            self.skip_reason = "no SVG files found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        svg_files = self._glob_files("*.svg")
        svg_files = [
            f for f in svg_files
            if "node_modules" not in str(f)
            and ".next" not in str(f)
            and ".git" not in str(f)
        ]

        if not svg_files:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS,
                findings=[],
                metrics={"svg_files_checked": 0},
            )

        npx = self._npx_path()
        results: list[dict[str, Any]] = []

        for svg_file in svg_files[:50]:  # limit to 50 SVGs
            original_size = svg_file.stat().st_size
            relative_path = str(svg_file.relative_to(self.target))

            # Run svgo with --dry-run to get optimised size without modifying files
            # svgo v3+ uses -o - for stdout output
            cmd = [
                npx, "svgo",
                str(svg_file),
                "--multipass",
                "-o", "-",
            ]

            result = self._exec(cmd, timeout=15)

            if result.returncode == 0 and result.stdout:
                optimized_size = len(result.stdout.encode("utf-8"))
                savings = original_size - optimized_size
                pct = (savings / original_size * 100) if original_size > 0 else 0

                results.append({
                    "file": relative_path,
                    "original_size": original_size,
                    "optimized_size": optimized_size,
                    "savings": max(0, savings),
                    "savings_pct": round(max(0, pct), 1),
                })
            else:
                # svgo may fail on malformed SVGs; try parsing stderr
                # Still record as-is for reporting
                results.append({
                    "file": relative_path,
                    "original_size": original_size,
                    "optimized_size": original_size,
                    "savings": 0,
                    "savings_pct": 0,
                })

        normaliser = SvgoNormaliser()
        findings = normaliser.normalise(results)

        total_original = sum(r["original_size"] for r in results)
        total_savings = sum(r["savings"] for r in results)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "svg_files_checked": len(results),
                "total_original_bytes": total_original,
                "total_savings_bytes": total_savings,
                "average_savings_pct": round(
                    sum(r["savings_pct"] for r in results) / len(results), 1
                ) if results else 0,
            },
        )
