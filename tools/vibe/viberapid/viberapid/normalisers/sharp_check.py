"""Normaliser for sharp image metadata analysis output."""

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


# Reasonable dimension thresholds for web images
_MAX_WEB_WIDTH = 2000
_MAX_WEB_HEIGHT = 2000
_LARGE_PIXEL_COUNT = 4_000_000  # ~2000x2000

# Expected bytes per pixel for well-compressed formats (rough estimates)
_EXPECTED_BPP: dict[str, float] = {
    "jpeg": 0.5,
    "jpg": 0.5,
    "png": 1.5,
    "webp": 0.35,
    "avif": 0.25,
    "gif": 0.8,
    "tiff": 3.0,
    "tif": 3.0,
}


class SharpCheckNormaliser(BaseNormaliser):
    """Convert sharp image metadata analysis to Finding objects.

    Input shape (built by the runner):
    [
      {
        "file": "public/hero.png",
        "width": 3840,
        "height": 2160,
        "format": "png",
        "channels": 4,
        "hasAlpha": true,
        "size": 4500000,
        "space": "srgb",
        "density": 72
      }
    ]
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, list):
            return []

        findings: list[Finding] = []

        for entry in raw_data:
            if not isinstance(entry, dict):
                continue

            # Skip entries with errors
            if "error" in entry:
                continue

            filepath = entry.get("file", "unknown")
            width = entry.get("width", 0)
            height = entry.get("height", 0)
            fmt = entry.get("format", "unknown")
            size = entry.get("size", 0)
            has_alpha = entry.get("hasAlpha", False)
            channels = entry.get("channels", 3)

            if size <= 0 or width <= 0 or height <= 0:
                continue

            pixel_count = width * height

            # Check 1: Oversized dimensions for web delivery
            if width > _MAX_WEB_WIDTH or height > _MAX_WEB_HEIGHT:
                max_dim = max(width, height)
                # Estimate savings from resizing to 2000px max
                scale_factor = _MAX_WEB_WIDTH / max_dim
                estimated_new_size = int(size * (scale_factor ** 2))
                savings = size - estimated_new_size

                findings.append(Finding(
                    tool="sharp-check",
                    severity=Severity.HIGH if max_dim > 4000 else Severity.MEDIUM,
                    category=Category.ASSET,
                    file=filepath,
                    rule_id="oversized-dimensions",
                    rule_name="Image dimensions too large for web",
                    message=(
                        f"'{filepath}' is {width}x{height}px ({_format_bytes(size)}). "
                        f"Images wider than {_MAX_WEB_WIDTH}px are rarely needed for web. "
                        f"Resizing to {_MAX_WEB_WIDTH}px max could save ~{_format_bytes(savings)}."
                    ),
                    metric="image_max_dimension",
                    current_value=float(max_dim),
                    target_value=float(_MAX_WEB_WIDTH),
                    fix_hint=(
                        f"Resize with: `npx sharp-cli -i {filepath} -o {filepath} "
                        f"--resize {_MAX_WEB_WIDTH}`. Use `<picture>` with srcset for "
                        f"responsive images at multiple breakpoints."
                    ),
                    saving_estimate=f"~{_format_bytes(savings)} from resizing",
                    effort=Effort.LOW,
                    raw=entry,
                ))

            # Check 2: Uncompressed or legacy format
            if fmt in ("tiff", "tif", "bmp"):
                findings.append(Finding(
                    tool="sharp-check",
                    severity=Severity.HIGH,
                    category=Category.ASSET,
                    file=filepath,
                    rule_id="legacy-format",
                    rule_name="Legacy image format not suited for web",
                    message=(
                        f"'{filepath}' uses {fmt.upper()} format ({_format_bytes(size)}). "
                        f"This format is uncompressed or poorly compressed for web delivery."
                    ),
                    metric="image_file_size",
                    current_value=float(size),
                    target_value=204800.0,
                    fix_hint=(
                        f"Convert to WebP or AVIF: `npx sharp-cli -i {filepath} "
                        f"-o {filepath.rsplit('.', 1)[0]}.webp --format webp`. "
                        f"Expected 80-90% size reduction."
                    ),
                    saving_estimate=f"~{_format_bytes(int(size * 0.85))} by converting to WebP",
                    effort=Effort.LOW,
                    raw=entry,
                ))

            # Check 3: PNG with no alpha (should be JPEG/WebP)
            if fmt == "png" and not has_alpha and size > 102_400:
                estimated_jpeg_size = int(pixel_count * _EXPECTED_BPP.get("jpeg", 0.5))
                savings = size - estimated_jpeg_size

                if savings > 0:
                    findings.append(Finding(
                        tool="sharp-check",
                        severity=Severity.MEDIUM if size > 512_000 else Severity.LOW,
                        category=Category.ASSET,
                        file=filepath,
                        rule_id="png-without-alpha",
                        rule_name="PNG without transparency (use JPEG/WebP instead)",
                        message=(
                            f"'{filepath}' is a {_format_bytes(size)} PNG with no alpha channel. "
                            f"Converting to JPEG or WebP could save ~{_format_bytes(savings)}."
                        ),
                        metric="image_file_size",
                        current_value=float(size),
                        target_value=float(estimated_jpeg_size),
                        fix_hint=(
                            f"Convert to WebP: `npx sharp-cli -i {filepath} "
                            f"-o {filepath.rsplit('.', 1)[0]}.webp --format webp -q 85`. "
                            f"This image has no transparency, so PNG's lossless compression "
                            f"is unnecessary."
                        ),
                        saving_estimate=f"~{_format_bytes(savings)} by converting format",
                        effort=Effort.LOW,
                        raw=entry,
                    ))

            # Check 4: Very large file size relative to dimensions
            expected_bpp = _EXPECTED_BPP.get(fmt, 1.0)
            expected_size = int(pixel_count * expected_bpp)

            if size > expected_size * 2 and size > 204_800:
                ratio = size / expected_size
                savings = size - expected_size

                findings.append(Finding(
                    tool="sharp-check",
                    severity=Severity.MEDIUM if ratio > 3 else Severity.LOW,
                    category=Category.ASSET,
                    file=filepath,
                    rule_id="oversized-filesize",
                    rule_name="Image file size exceeds expected compression ratio",
                    message=(
                        f"'{filepath}' ({width}x{height} {fmt.upper()}) is "
                        f"{_format_bytes(size)}, which is {ratio:.1f}x the expected "
                        f"size for this format and resolution. "
                        f"The image may be under-compressed or contain excessive metadata."
                    ),
                    metric="image_size_ratio",
                    current_value=float(ratio),
                    target_value=1.0,
                    fix_hint=(
                        f"Re-compress with: `npx sharp-cli -i {filepath} -o {filepath} "
                        f"-q 80`. Strip metadata with `--withMetadata false`. "
                        f"Consider converting to WebP or AVIF for better compression."
                    ),
                    saving_estimate=f"~{_format_bytes(savings)} with proper compression",
                    effort=Effort.LOW,
                    raw=entry,
                ))

        return findings
