"""Runner for brotli-size — measures Brotli compression headroom over gzip."""

from __future__ import annotations

import gzip
import io
from pathlib import Path
from typing import Any

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.brotli_size import BrotliSizeNormaliser
from viberapid.runners.base import AsyncToolRunner


class BrotliSizeRunner(AsyncToolRunner):
    """Measure Brotli compression headroom over gzip for JS/CSS files."""

    name = "brotli-size"

    def _get_compressible_files(self) -> list:
        """Glob for JS/CSS/HTML files, applying default and per-tool excludes."""
        files = self._glob_files("*.js", "*.css", "*.mjs", "*.cjs", "*.html")
        files = [
            f for f in files
            if "node_modules" not in str(f)
            and ".next" not in str(f)
            and ".git" not in str(f)
        ]
        return self._apply_tool_excludes(files)

    def should_run(self) -> bool:
        # Check if brotli is available
        try:
            import brotli  # noqa: F401
        except ImportError:
            self.skip_reason = "brotli Python package not installed (pip install brotli)"
            return False

        if not self._get_compressible_files():
            self.skip_reason = "no JS/CSS/HTML files found for compression analysis"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        try:
            import brotli
        except ImportError:
            return self._make_error_result("brotli Python package not installed")

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
        total_gzip = 0
        total_brotli = 0

        for filepath in files:
            try:
                original_data = filepath.read_bytes()
            except OSError:
                continue

            original_size = len(original_data)
            if original_size < 1024:  # Skip files < 1 KB
                continue

            # Gzip compress
            gzip_buf = io.BytesIO()
            with gzip.GzipFile(fileobj=gzip_buf, mode="wb", compresslevel=9) as gz:
                gz.write(original_data)
            gzip_size = gzip_buf.tell()

            # Brotli compress (quality 11 = max)
            try:
                brotli_data = brotli.compress(original_data, quality=11)
                brotli_size = len(brotli_data)
            except Exception:
                continue

            total_gzip += gzip_size
            total_brotli += brotli_size

            improvement = (
                (gzip_size - brotli_size) / gzip_size * 100
            ) if gzip_size > 0 else 0

            brotli_ratio = (
                (original_size - brotli_size) / original_size * 100
            ) if original_size > 0 else 0

            relative_path = str(filepath.relative_to(self.target))
            results.append({
                "file": relative_path,
                "original_size": original_size,
                "gzip_size": gzip_size,
                "brotli_size": brotli_size,
                "brotli_vs_gzip_improvement": round(improvement, 1),
                "brotli_ratio": round(brotli_ratio, 1),
            })

        normaliser = BrotliSizeNormaliser()
        findings = normaliser.normalise(results)

        overall_improvement = (
            (total_gzip - total_brotli) / total_gzip * 100
        ) if total_gzip > 0 else 0

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "files_checked": len(results),
                "total_gzip_bytes": total_gzip,
                "total_brotli_bytes": total_brotli,
                "overall_brotli_improvement_pct": round(overall_improvement, 1),
            },
        )
