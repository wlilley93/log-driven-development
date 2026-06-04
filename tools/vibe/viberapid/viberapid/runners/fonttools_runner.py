"""Runner for fonttools — Python-based font analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.fonttools_normaliser import FonttoolsNormaliser
from viberapid.runners.base import AsyncToolRunner


class FonttoolsRunner(AsyncToolRunner):
    """Analyse font files using the fonttools Python library."""

    name = "fonttools"
    requires_python = True

    def should_run(self) -> bool:
        font_files = self._glob_files("*.woff", "*.woff2", "*.ttf", "*.otf", "*.eot")
        font_files = [f for f in font_files if "node_modules" not in str(f)]
        if not font_files:
            self.skip_reason = "no font files found"
            return False

        # Check if fonttools is importable
        try:
            import fontTools  # noqa: F401
        except ImportError:
            self.skip_reason = "fonttools Python package not installed"
            return False

        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        font_files = self._glob_files("*.woff", "*.woff2", "*.ttf", "*.otf", "*.eot")
        font_files = [f for f in font_files if "node_modules" not in str(f)]

        if not font_files:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS,
                findings=[],
                metrics={"font_files_checked": 0},
            )

        results: list[dict[str, Any]] = []

        for font_file in font_files[:20]:  # limit to 20 fonts
            info = self._analyse_font(font_file)
            if info:
                results.append(info)

        normaliser = FonttoolsNormaliser()
        findings = normaliser.normalise(results)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "font_files_checked": len(results),
                "total_font_bytes": sum(r.get("file_size", 0) for r in results),
            },
        )

    def _analyse_font(self, font_path: Path) -> dict[str, Any] | None:
        """Analyse a single font file using fonttools."""
        try:
            from fontTools.ttLib import TTFont
        except ImportError:
            return None

        relative_path = str(font_path.relative_to(self.target))
        file_size = font_path.stat().st_size

        try:
            font = TTFont(str(font_path))
        except Exception:
            return None

        try:
            # Basic metrics
            num_glyphs = len(font.getGlyphOrder())
            tables = list(font.keys())

            # Detect format
            if "glyf" in font:
                font_format = "TrueType"
            elif "CFF " in font:
                font_format = "CFF"
            elif "CFF2" in font:
                font_format = "CFF2"
            else:
                font_format = "unknown"

            # Check for hinting
            has_hinting = "fpgm" in font or "prep" in font or "cvt " in font

            # Get family name
            family_name = "unknown"
            if "name" in font:
                name_table = font["name"]
                for record in name_table.names:
                    if record.nameID == 1:  # Font Family Name
                        try:
                            family_name = record.toUnicode()
                            break
                        except (UnicodeDecodeError, AttributeError):
                            continue

            # Check if variable font
            is_variable = "fvar" in font
            num_masters = 1
            if is_variable and "fvar" in font:
                try:
                    num_masters = len(font["fvar"].axes)
                except (AttributeError, TypeError):
                    pass

            # Estimate subsetting potential
            # Latin-only sites typically need ~300 glyphs
            subsetting_potential = max(0, (num_glyphs - 300) / num_glyphs) if num_glyphs > 300 else 0

            font.close()

            return {
                "file": relative_path,
                "file_size": file_size,
                "format": font_format,
                "num_glyphs": num_glyphs,
                "tables": tables,
                "has_hinting": has_hinting,
                "family_name": family_name,
                "is_variable": is_variable,
                "num_masters": num_masters,
                "subsetting_potential": round(subsetting_potential, 2),
            }

        except Exception:
            try:
                font.close()
            except Exception:
                pass
            return None
