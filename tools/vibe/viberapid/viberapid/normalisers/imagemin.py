"""Normaliser for imagemin (image size analysis) output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser


def _format_bytes(size_bytes: int | float) -> str:
    """Format byte count to human-readable string."""
    if size_bytes >= 1_048_576:
        return f"{size_bytes / 1_048_576:.1f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{int(size_bytes)} B"


class ImageminNormaliser(BaseNormaliser):
    """Convert image size analysis to Finding objects.

    Input shape (built by the runner):
    {
      "images": [
        {
          "file": "public/hero.png",
          "size": 1250000,
          "extension": ".png",
          "estimated_savings_pct": 45
        }
      ],
      "total_size": 5000000,
      "total_images": 15
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        findings: list[Finding] = []

        for img in raw_data.get("images", []):
            if not isinstance(img, dict):
                continue

            filepath = img.get("file", "unknown")
            size = img.get("size", 0)
            ext = img.get("extension", "").lower()
            savings_pct = img.get("estimated_savings_pct", 0)

            if size <= 0:
                continue

            if size > 1_048_576:  # > 1 MB
                severity = Severity.HIGH
                rule_id = "large-image"
                rule_name = "Large image (>1 MB)"
            elif size > 204_800:  # > 200 KB
                severity = Severity.MEDIUM
                rule_id = "medium-image"
                rule_name = "Medium-large image (>200 KB)"
            elif size > 102_400:  # > 100 KB
                severity = Severity.LOW
                rule_id = "unoptimized-image"
                rule_name = "Image optimisation opportunity"
            else:
                continue  # Skip small images

            estimated_savings = int(size * savings_pct / 100)

            findings.append(Finding(
                tool="imagemin",
                severity=severity,
                category=Category.ASSET,
                file=filepath,
                rule_id=rule_id,
                rule_name=rule_name,
                message=(
                    f"Image '{filepath}' is {_format_bytes(size)}. "
                    f"Estimated compression savings: ~{savings_pct}% "
                    f"({_format_bytes(estimated_savings)})."
                ),
                metric="image_file_size",
                current_value=float(size),
                target_value=204800.0,
                fix_hint=_get_fix_hint(filepath, ext, size),
                saving_estimate=f"~{_format_bytes(estimated_savings)} with compression",
                effort=Effort.LOW,
                raw=img,
            ))

        return findings


def _get_fix_hint(filepath: str, ext: str, size: int) -> str:
    """Generate format-specific compression hints."""
    if ext in (".png",):
        return (
            f"Compress with `npx imagemin {filepath} --plugin=pngquant`. "
            f"For photos, convert to WebP or AVIF for 30-50% smaller files. "
            f"Use `<picture>` with WebP fallback for browser compatibility."
        )
    if ext in (".jpg", ".jpeg"):
        return (
            f"Compress with `npx imagemin {filepath} --plugin=mozjpeg`. "
            f"Set quality to 80-85 for visually lossless compression. "
            f"Convert to WebP for additional 25-34% savings."
        )
    if ext in (".gif",):
        return (
            f"Convert animated GIFs to MP4 or WebM video for 80-90% size reduction. "
            f"For static GIFs, convert to PNG or WebP."
        )
    if ext in (".svg",):
        return f"Optimise with `npx svgo {filepath}` to remove unnecessary metadata."
    if ext in (".webp",):
        if size > 512_000:
            return (
                f"Even as WebP, '{filepath}' is large. Consider reducing dimensions, "
                f"increasing compression, or using AVIF format."
            )
        return f"WebP is already well-compressed. Consider AVIF for further savings."
    if ext in (".bmp", ".tiff", ".tif"):
        return (
            f"Convert '{filepath}' from {ext} to WebP or PNG. "
            f"BMP/TIFF are uncompressed formats not suitable for web delivery."
        )
    return (
        f"Compress '{filepath}' using appropriate tools. "
        f"Consider converting to WebP or AVIF for modern browsers."
    )
