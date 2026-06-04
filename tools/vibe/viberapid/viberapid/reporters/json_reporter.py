"""JSON reporter — simple serialisation of ScanResult."""

from __future__ import annotations

from rich.console import Console

from viberapid.config import Config
from viberapid.models import ScanResult
from viberapid.reporters.base import BaseReporter


class JsonReporter(BaseReporter):
    """Outputs the scan result as JSON."""

    def render(self, console: Console) -> None:
        """Print JSON to the console."""
        output = self.result.to_json(pretty=self.config.json_pretty)
        console.print(output, highlight=False)

    def render_to_string(self) -> str:
        """Return JSON as a string."""
        return self.result.to_json(pretty=self.config.json_pretty)
