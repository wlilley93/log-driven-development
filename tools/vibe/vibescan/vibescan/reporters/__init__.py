"""Reporter implementations for vibescan output formats."""

from vibescan.reporters.base import BaseReporter
from vibescan.reporters.html import HtmlReporter
from vibescan.reporters.json_reporter import JsonReporter
from vibescan.reporters.markdown import MarkdownReporter
from vibescan.reporters.sarif import SarifReporter
from vibescan.reporters.table import TableReporter

REPORTERS: dict[str, type[BaseReporter]] = {
    "table": TableReporter,
    "json": JsonReporter,
    "html": HtmlReporter,
    "sarif": SarifReporter,
    "markdown": MarkdownReporter,
}

__all__ = [
    "BaseReporter",
    "HtmlReporter",
    "JsonReporter",
    "MarkdownReporter",
    "SarifReporter",
    "TableReporter",
    "REPORTERS",
]
