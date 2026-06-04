"""Runner for gzip-size — measures gzip compression ratios of JS/CSS files."""

from __future__ import annotations

import gzip
import io
from pathlib import Path
from typing import Any

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.gzip_size import GzipSizeNormaliser
from viberapid.runners.base import AsyncToolRunner


class GzipSizeRunner(AsyncToolRunner):
    """Measure gzip compression ratios of JavaScript and CSS files using Python's gzip module."""

    name = "gzip-size"

    def _get_compressible_files(self) -> list:
        """Glob for JS/CSS files, applying default and per-tool excludes."""
        files = self._glob_files("*.js", "*.css", "*.mjs", "*.cjs")
        files = [
            f for f in files
            if "node_modules" not in str(f)
            and ".next" not in str(f)
            and ".git" not in str(f)
        ]
        return self._apply_tool_excludes(files)

    def should_run(self) -> bool:
        if not self._get_compressible_files():
            self.skip_reason = "no JS/CSS files found for compression analysis"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        # Find JS and CSS files, preferring build output directories
        files = self._get_compressible_files()

        if not files:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS,
                findings=[],
                metrics={"files_checked": 0},
            )

        # Sort by size descending and take top files
        try:
            files.sort(key=lambda f: f.stat().st_size, reverse=True)
        except OSError:
            pass

        max_files = self.tool_config.get("max_files", 50)
        files = files[:max_files]

        results: list[dict[str, Any]] = []
        total_original = 0
        total_gzipped = 0

        for filepath in files:
            try:
                original_data = filepath.read_bytes()
            except OSError:
                continue

            original_size = len(original_data)
            if original_size < 1024:  # Skip files < 1 KB
                continue

            # Gzip compress using Python's gzip module (level 9 = best)
            buf = io.BytesIO()
            with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=9) as gz:
                gz.write(original_data)

            gzip_size = buf.tell()
            ratio = ((original_size - gzip_size) / original_size * 100) if original_size > 0 else 0

            total_original += original_size
            total_gzipped += gzip_size

            relative_path = str(filepath.relative_to(self.target))
            results.append({
                "file": relative_path,
                "original_size": original_size,
                "gzip_size": gzip_size,
                "compression_ratio": round(ratio, 1),
            })

        normaliser = GzipSizeNormaliser()
        findings = normaliser.normalise(results)

        overall_ratio = (
            (total_original - total_gzipped) / total_original * 100
        ) if total_original > 0 else 0

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "files_checked": len(results),
                "total_original_bytes": total_original,
                "total_gzipped_bytes": total_gzipped,
                "overall_compression_ratio": round(overall_ratio, 1),
            },
        )
