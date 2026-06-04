"""Normaliser for zopfli compression headroom analysis output."""

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


class ZopfliNormaliser(BaseNormaliser):
    """Convert zopfli compression headroom analysis to Finding objects.

    Zopfli is a Zlib-compatible compressor that achieves 3-8% smaller output
    than standard gzip at the cost of much slower compression. The headroom
    represents "free" size savings achievable by switching to zopfli for
    pre-compressed static assets.

    Input shape (built by the runner):
    {
      "files": [
        {
          "file": "dist/app.js",
          "original_size": 250000,
          "gzip_size": 68000,
          "zopfli_size": 64500,
          "headroom": 3500,
          "headroom_pct": 5.15,
          "gzip_ratio": 72.8,
          "zopfli_ratio": 74.2
        }
      ],
      "total_gzip": 150000,
      "total_zopfli": 141000,
      "total_headroom": 9000
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        findings: list[Finding] = []

        # Aggregate finding: overall compression headroom
        total_headroom = raw_data.get("total_headroom", 0)
        total_gzip = raw_data.get("total_gzip", 0)
        files = raw_data.get("files", [])

        if total_headroom > 0 and total_gzip > 0:
            overall_pct = (total_headroom / total_gzip * 100)
            if overall_pct > 3 and total_headroom > 10240:
                findings.append(Finding(
                    tool="zopfli",
                    severity=Severity.MEDIUM if total_headroom > 51200 else Severity.LOW,
                    category=Category.COMPRESSION,
                    file="(aggregate)",
                    rule_id="total-compression-headroom",
                    rule_name="Total compression headroom with zopfli",
                    message=(
                        f"Switching from standard gzip to zopfli for static assets "
                        f"would save {_format_bytes(total_headroom)} total "
                        f"({overall_pct:.1f}% improvement over gzip). "
                        f"Analysed {len(files)} compressible files."
                    ),
                    metric="total_compression_headroom",
                    current_value=float(total_gzip),
                    target_value=float(total_gzip - total_headroom),
                    fix_hint=(
                        "Pre-compress static assets with zopfli during your build step: "
                        "`find dist -type f \\( -name '*.js' -o -name '*.css' -o -name '*.html' "
                        "-o -name '*.svg' \\) -exec zopfli --gzip {} \\;`. "
                        "Configure your web server to serve .gz files with "
                        "`Content-Encoding: gzip`. For Nginx: `gzip_static on;`."
                    ),
                    saving_estimate=f"{_format_bytes(total_headroom)} total transfer reduction",
                    effort=Effort.LOW,
                    raw={"total_headroom": total_headroom, "total_gzip": total_gzip},
                ))

        # Per-file findings for significant headroom
        for entry in files:
            if not isinstance(entry, dict):
                continue

            filepath = entry.get("file", "unknown")
            original = entry.get("original_size", 0)
            gzip_size = entry.get("gzip_size", 0)
            zopfli_size = entry.get("zopfli_size", 0)
            headroom = entry.get("headroom", 0)
            headroom_pct = entry.get("headroom_pct", 0)
            gzip_ratio = entry.get("gzip_ratio", 0)
            zopfli_ratio = entry.get("zopfli_ratio", 0)

            # Only report files with meaningful headroom (>3% improvement, >1KB)
            if headroom_pct < 3 or headroom < 1024:
                continue

            if headroom_pct > 8:
                severity = Severity.MEDIUM
                rule_id = "high-compression-headroom"
                rule_name = "High compression headroom with zopfli (>8%)"
            elif headroom_pct > 5:
                severity = Severity.LOW
                rule_id = "moderate-compression-headroom"
                rule_name = "Moderate compression headroom with zopfli (>5%)"
            else:
                severity = Severity.INFO
                rule_id = "low-compression-headroom"
                rule_name = "Low compression headroom with zopfli (>3%)"

            findings.append(Finding(
                tool="zopfli",
                severity=severity,
                category=Category.COMPRESSION,
                file=filepath,
                rule_id=rule_id,
                rule_name=rule_name,
                message=(
                    f"'{filepath}' ({_format_bytes(original)}): "
                    f"gzip={_format_bytes(gzip_size)} ({gzip_ratio:.1f}% ratio), "
                    f"zopfli={_format_bytes(zopfli_size)} ({zopfli_ratio:.1f}% ratio). "
                    f"Headroom: {_format_bytes(headroom)} ({headroom_pct:.1f}% smaller)."
                ),
                metric="zopfli_headroom_pct",
                current_value=float(headroom_pct),
                target_value=0.0,
                fix_hint=(
                    f"Pre-compress '{filepath}' with `zopfli --gzip --i15 {filepath}` "
                    f"during your build step. The resulting .gz file is {headroom_pct:.1f}% "
                    f"smaller than standard gzip. Serve via your web server's "
                    f"`gzip_static` directive."
                ),
                saving_estimate=f"{_format_bytes(headroom)} transfer reduction",
                effort=Effort.LOW,
                raw=entry,
            ))

        return findings
