"""Reporter implementations for vibeclean output formats."""

from vibeclean.reporters.base import BaseReporter
from vibeclean.reporters.json_reporter import JsonReporter
from vibeclean.reporters.markdown import MarkdownReporter
from vibeclean.reporters.table import TableReporter

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
