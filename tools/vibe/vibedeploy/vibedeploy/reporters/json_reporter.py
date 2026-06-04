"""JSON reporter."""

from __future__ import annotations

from rich.console import Console

from vibedeploy.reporters.base import BaseReporter


class JsonReporter(BaseReporter):
    """JSON serialization of scan results."""

    def render(self, console: Console) -> None:
        console.print(self.result.to_json(pretty=self.config.json_pretty))

    def render_to_string(self) -> str:
        return self.result.to_json(pretty=True)
