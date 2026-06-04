"""Runner for glyphhanger — font usage and subsetting analysis."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.glyphhanger import GlyphhangerNormaliser
from viberapid.runners.base import AsyncToolRunner


class GlyphhangerRunner(AsyncToolRunner):
    """Run glyphhanger to analyse font glyph usage and subsetting opportunities."""

    name = "glyphhanger"
    requires_node = True

    def should_run(self) -> bool:
        # Check for font files in the project
        font_files = self._glob_files("*.woff", "*.woff2", "*.ttf", "*.otf", "*.eot")
        font_files = [
            f for f in font_files
            if "node_modules" not in str(f)
        ]
        if not font_files:
            self.skip_reason = "no font files found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        font_files = self._glob_files("*.woff", "*.woff2", "*.ttf", "*.otf", "*.eot")
        font_files = [
            f for f in font_files
            if "node_modules" not in str(f)
        ]

        if not font_files:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS,
                findings=[],
                metrics={"font_files_checked": 0},
            )

        npx = self._npx_path()

        # First, determine which characters are used in content files
        content_files = self._glob_files(
            "*.html", "*.htm", "*.js", "*.jsx", "*.ts", "*.tsx", "*.vue", "*.svelte",
        )
        content_files = [
            f for f in content_files
            if "node_modules" not in str(f) and ".next" not in str(f)
        ]

        # Collect used characters from content
        used_chars = set()
        for cf in content_files[:100]:  # limit for performance
            try:
                text = cf.read_text(errors="ignore")
                used_chars.update(text)
            except (OSError, UnicodeDecodeError):
                continue

        font_results: list[dict[str, Any]] = []

        for font_file in font_files[:20]:  # limit to 20 fonts
            relative_path = str(font_file.relative_to(self.target))
            file_size = font_file.stat().st_size

            # Try to get glyph count using glyphhanger
            cmd = [npx, "glyphhanger", str(font_file)]
            result = self._exec(cmd, timeout=30)

            glyphs_in_font = set()
            if result.stdout.strip():
                # glyphhanger outputs unicode codepoints or character ranges
                output = result.stdout.strip()
                # Parse unicode ranges like "U+0020-007E, U+00A0-00FF"
                glyphs_in_font = self._parse_glyph_output(output)

            total_glyphs = len(glyphs_in_font) if glyphs_in_font else 0
            used_glyphs = len(glyphs_in_font & used_chars) if glyphs_in_font else 0
            unused_glyphs = total_glyphs - used_glyphs
            unused_pct = (unused_glyphs / total_glyphs * 100) if total_glyphs > 0 else 0

            font_results.append({
                "file": relative_path,
                "total_glyphs": total_glyphs,
                "used_glyphs": used_glyphs,
                "unused_glyphs": unused_glyphs,
                "unused_pct": round(unused_pct, 1),
                "file_size": file_size,
                "unicode_ranges": result.stdout.strip()[:200] if result.stdout else "",
            })

        data = {
            "fonts": font_results,
            "charset_size": len(used_chars),
        }

        normaliser = GlyphhangerNormaliser()
        findings = normaliser.normalise(data)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "font_files_checked": len(font_results),
                "content_files_scanned": len(content_files),
                "unique_chars_in_content": len(used_chars),
            },
        )

    @staticmethod
    def _parse_glyph_output(output: str) -> set[str]:
        """Parse glyphhanger output into a set of characters.

        Output may be like: "U+0020-007E, U+00A0-00FF" or actual characters.
        """
        chars = set()

        for part in output.split(","):
            part = part.strip()
            if part.startswith("U+"):
                # Unicode range
                if "-" in part:
                    try:
                        range_parts = part.replace("U+", "").split("-")
                        start = int(range_parts[0], 16)
                        end = int(range_parts[1], 16)
                        for cp in range(start, end + 1):
                            try:
                                chars.add(chr(cp))
                            except (ValueError, OverflowError):
                                continue
                    except (ValueError, IndexError):
                        continue
                else:
                    try:
                        cp = int(part.replace("U+", ""), 16)
                        chars.add(chr(cp))
                    except (ValueError, OverflowError):
                        continue
            else:
                # Direct characters
                chars.update(part)

        return chars
