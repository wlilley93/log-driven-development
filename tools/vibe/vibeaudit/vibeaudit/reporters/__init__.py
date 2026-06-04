"""Reporter factory — create a reporter by format name."""

from __future__ import annotations

from vibeaudit.reporters.base import Reporter


def create_reporter(format: str) -> Reporter:
    """Create a reporter instance from a format string.

    Supported formats: table, json, html, markdown, sarif, quiet.

    Args:
        format: The output format name.

    Returns:
        A Reporter instance for the given format.

    Raises:
        ValueError: If the format is not recognized.
    """
    format = format.lower().strip()

    if format == "table":
        from vibeaudit.reporters.table_reporter import TableReporter
        return TableReporter()

    if format == "json":
        from vibeaudit.reporters.json_reporter import JsonReporter
        return JsonReporter()

    if format == "html":
        from vibeaudit.reporters.html_reporter import HtmlReporter
        return HtmlReporter()

    if format == "markdown":
        from vibeaudit.reporters.markdown_reporter import MarkdownReporter
        return MarkdownReporter()

    if format == "sarif":
        from vibeaudit.reporters.sarif_reporter import SarifReporter
        return SarifReporter()

    if format == "quiet":
        from vibeaudit.reporters.table_reporter import TableReporter
        return TableReporter(quiet=True)

    supported = ", ".join(["table", "json", "html", "markdown", "sarif", "quiet"])
    raise ValueError(f"Unknown output format '{format}'. Supported formats: {supported}")


__all__ = ["Reporter", "create_reporter"]
