"""Runner for imagemin — image file size analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.imagemin import ImageminNormaliser
from viberapid.runners.base import AsyncToolRunner

# Estimated compression savings by format (conservative percentages)
_ESTIMATED_SAVINGS: dict[str, int] = {
    ".png": 40,
    ".jpg": 25,
    ".jpeg": 25,
    ".gif": 15,
    ".bmp": 85,
    ".tiff": 80,
    ".tif": 80,
    ".webp": 10,
    ".svg": 30,
    ".ico": 20,
    ".avif": 5,
}


class ImageminRunner(AsyncToolRunner):
    """Analyse image files for size and optimisation opportunities."""

    name = "imagemin"

    def _get_image_files(self) -> list:
        """Glob for image files, applying default and per-tool excludes."""
        image_files = self._glob_files(
            "*.png", "*.jpg", "*.jpeg", "*.gif", "*.svg",
            "*.webp", "*.bmp", "*.tiff", "*.tif", "*.ico", "*.avif",
        )
        image_files = [
            f for f in image_files
            if "node_modules" not in str(f)
            and ".next" not in str(f)
            and ".git" not in str(f)
        ]
        return self._apply_tool_excludes(image_files)

    def should_run(self) -> bool:
        if not self._get_image_files():
            self.skip_reason = "no image files found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        image_files = self._get_image_files()

        if not image_files:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS,
                findings=[],
                metrics={"images_checked": 0},
            )

        results: list[dict[str, Any]] = []
        total_size = 0

        for img_file in image_files:
            try:
                file_size = img_file.stat().st_size
            except OSError:
                continue

            total_size += file_size
            ext = img_file.suffix.lower()
            savings_pct = _ESTIMATED_SAVINGS.get(ext, 20)

            relative_path = str(img_file.relative_to(self.target))
            results.append({
                "file": relative_path,
                "size": file_size,
                "extension": ext,
                "estimated_savings_pct": savings_pct,
            })

        # Sort by size descending for prioritisation
        results.sort(key=lambda r: r["size"], reverse=True)

        data = {
            "images": results,
            "total_size": total_size,
            "total_images": len(results),
        }

        normaliser = ImageminNormaliser()
        findings = normaliser.normalise(data)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "images_checked": len(results),
                "total_image_bytes": total_size,
                "images_over_1mb": sum(1 for r in results if r["size"] > 1_048_576),
                "images_over_200kb": sum(1 for r in results if r["size"] > 204_800),
            },
        )
