"""Reporter implementations for vibetest output formats."""

from vibetest.reporters.base import BaseReporter
from vibetest.reporters.json_reporter import JsonReporter
from vibetest.reporters.markdown import MarkdownReporter
from vibetest.reporters.table import TableReporter

REPORTERS: dict[str, type[BaseReporter]] = {
    "table": TableReporter,
    "json": JsonReporter,
    "md": MarkdownReporter,
}

__all__ = [
    "BaseReporter",
    "JsonReporter",
    "MarkdownReporter",
    "TableReporter",
    "REPORTERS",
]
