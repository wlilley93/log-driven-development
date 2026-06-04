"""Abstract reporter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from rich.console import Console

from vibeaudit.models import ScanResult


class Reporter(ABC):
    """Base class for all output reporters."""

    @abstractmethod
    def report(self, result: ScanResult, console: Console, output_path: Path | None = None) -> None:
        """Render the scan result.

        Args:
            result: The completed scan result with findings.
            console: Rich console for terminal output.
            output_path: Optional file path to write the report to.
        """
        ...
