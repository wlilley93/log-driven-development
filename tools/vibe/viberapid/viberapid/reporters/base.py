"""Base reporter class."""

from __future__ import annotations

from abc import ABC, abstractmethod

from rich.console import Console

from viberapid.config import Config
from viberapid.models import ScanResult


class BaseReporter(ABC):
    """Base class for all reporters."""

    def __init__(self, result: ScanResult, config: Config):
        self.result = result
        self.config = config

    @abstractmethod
    def render(self, console: Console) -> None:
        """Render the report to the console."""
        ...

    @abstractmethod
    def render_to_string(self) -> str:
        """Render the report to a string."""
        ...
