"""JSON reporter — outputs scan result as formatted JSON."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from vibeaudit.models import ScanResult
from vibeaudit.reporters.base import Reporter


class JsonReporter(Reporter):
    """Outputs the full scan result as indented JSON."""

    def report(self, result: ScanResult, console: Console, output_path: Path | None = None) -> None:
        json_str = result.model_dump_json(indent=2)

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json_str, encoding="utf-8")
            console.print(f"[green]JSON report written to {output_path}[/green]")
        else:
            console.print(json_str, highlight=False)
