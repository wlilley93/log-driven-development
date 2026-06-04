"""JSON reporter — structured machine-readable output."""

from __future__ import annotations

from rich.console import Console

from vibescan.config import Config
from vibescan.models import ScanResult
from vibescan.reporters.base import BaseReporter


class JsonReporter(BaseReporter):
    """Emit the scan result as a JSON document."""

    def __init__(self, result: ScanResult, config: Config):
        super().__init__(result, config)

    def render(self, console: Console) -> None:
        console.print_json(self.render_to_string())

    def render_to_string(self) -> str:
        return self.result.to_json(pretty=self.config.json_pretty)
