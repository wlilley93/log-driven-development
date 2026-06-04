"""Runner for zopfli — compression headroom analysis vs standard gzip."""

from __future__ import annotations

import gzip
import shutil
import tempfile
from pathlib import Path
from typing import Any

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.zopfli import ZopfliNormaliser
from viberapid.runners.base import AsyncToolRunner

# File extensions worth analysing for compression headroom.
_COMPRESSIBLE_EXTENSIONS = {
    ".html", ".htm", ".css", ".js", ".mjs", ".cjs",
    ".json", ".xml", ".svg", ".txt", ".md",
    ".map", ".ts", ".tsx", ".jsx",
}

# Minimum file size to bother analysing (bytes)
_MIN_FILE_SIZE = 1024  # 1 KB


class ZopfliRunner(AsyncToolRunner):
    """Measure compression headroom by comparing zopfli (optimal deflate)
    against standard gzip for static assets. Zopfli produces smaller output
    than standard gzip at the cost of slower compression, making it ideal
    for pre-compressed static assets."""

    name = "zopfli"

    def should_run(self) -> bool:
        compressible = self._find_compressible_files()
        if not compressible:
            self.skip_reason = "no compressible text assets found"
            return False

        # Check if zopfli binary is available (system or viberapid-managed)
        if not self._tool_exists() and not shutil.which("zopfli"):
            self.skip_reason = "zopfli binary not found"
            return False

        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        compressible = self._find_compressible_files()

        if not compressible:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS,
                findings=[],
                metrics={"files_checked": 0},
            )

        analysis_results: list[dict[str, Any]] = []

        with tempfile.TemporaryDirectory(prefix="viberapid-zopfli-") as tmp_dir:
            for src_file in compressible[:80]:  # limit to 80 files
                original_size = src_file.stat().st_size
                if original_size < _MIN_FILE_SIZE:
                    continue

                relative_path = str(src_file.relative_to(self.target))

                # Standard gzip compression (Python built-in, level 9)
                try:
                    raw_content = src_file.read_bytes()
                    gzip_compressed = gzip.compress(raw_content, compresslevel=9)
                    gzip_size = len(gzip_compressed)
                except OSError:
                    continue

                # Zopfli compression via CLI
                tmp_src = Path(tmp_dir) / src_file.name
                tmp_src.write_bytes(raw_content)

                zopfli_bin = self.bin_path
                if not Path(zopfli_bin).exists():
                    zopfli_bin = shutil.which("zopfli") or "zopfli"

                cmd = [
                    zopfli_bin,
                    "--gzip",
                    "--i15",  # 15 iterations (good balance of speed vs compression)
                    str(tmp_src),
                ]

                result = self._exec(cmd, cwd=tmp_dir, timeout=30)

                zopfli_output = Path(str(tmp_src) + ".gz")
                if zopfli_output.exists():
                    zopfli_size = zopfli_output.stat().st_size
                else:
                    # zopfli failed; skip this file
                    continue

                # Calculate headroom: how much smaller zopfli is vs gzip
                headroom = gzip_size - zopfli_size
                headroom_pct = (headroom / gzip_size * 100) if gzip_size > 0 else 0

                gzip_ratio = (1 - gzip_size / original_size) * 100 if original_size > 0 else 0
                zopfli_ratio = (1 - zopfli_size / original_size) * 100 if original_size > 0 else 0

                analysis_results.append({
                    "file": relative_path,
                    "original_size": original_size,
                    "gzip_size": gzip_size,
                    "zopfli_size": zopfli_size,
                    "headroom": max(0, headroom),
                    "headroom_pct": round(max(0, headroom_pct), 2),
                    "gzip_ratio": round(gzip_ratio, 1),
                    "zopfli_ratio": round(zopfli_ratio, 1),
                })

                # Clean up temp files
                tmp_src.unlink(missing_ok=True)
                zopfli_output.unlink(missing_ok=True)

        total_gzip = sum(r["gzip_size"] for r in analysis_results)
        total_zopfli = sum(r["zopfli_size"] for r in analysis_results)
        total_headroom = sum(r["headroom"] for r in analysis_results)

        data = {
            "files": analysis_results,
            "total_gzip": total_gzip,
            "total_zopfli": total_zopfli,
            "total_headroom": total_headroom,
        }

        normaliser = ZopfliNormaliser()
        findings = normaliser.normalise(data)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "files_checked": len(analysis_results),
                "total_gzip_bytes": total_gzip,
                "total_zopfli_bytes": total_zopfli,
                "total_headroom_bytes": total_headroom,
                "average_headroom_pct": round(
                    sum(r["headroom_pct"] for r in analysis_results) / len(analysis_results), 2
                ) if analysis_results else 0,
            },
        )

    def _find_compressible_files(self) -> list[Path]:
        """Find text-based files worth analysing for compression."""
        patterns = [f"*{ext}" for ext in _COMPRESSIBLE_EXTENSIONS]
        files = self._glob_files(*patterns)
        return [
            f for f in files
            if "node_modules" not in str(f)
            and ".next" not in str(f)
            and ".git" not in str(f)
            and "vendor" not in str(f)
            and f.stat().st_size >= _MIN_FILE_SIZE
        ]
