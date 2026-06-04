"""Base reporter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from rich.console import Console

from vibetest.config import Config
from vibetest.models import ScanResult


class BaseReporter(ABC):
    """Transform ScanResult into a human/machine-readable report."""

    def __init__(self, result: ScanResult, config: Config):
        self.result = result
        self.config = config

    @abstractmethod
    def render(self, console: Console) -> None:
        """Render the report to the console (interactive output)."""
        ...

    @abstractmethod
    def render_to_string(self) -> str:
        """Render the report to a string (for file output)."""
        ...
