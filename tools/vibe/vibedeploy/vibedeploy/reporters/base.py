"""Base reporter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from rich.console import Console

from vibedeploy.config import Config
from vibedeploy.models import ScanResult


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

    def render_ship_safe(self, console: Console) -> None:
        """Render ship-safe one-liner. Override for table reporter."""
        self.render(console)

    def render_deploy_blockers(self, console: Console) -> None:
        """Render deploy-blocking findings prominently."""
        blockers = self.result.deploy_blockers
        if not blockers:
            return
        console.print(f"\n[bold red]DEPLOY BLOCKERS ({len(blockers)})[/bold red]")
        for f in blockers:
            loc = f.file
            if f.line:
                loc += f":{f.line}"
            console.print(f"  [red]✗[/red] [{f.tool}] {f.message}")
            console.print(f"    [dim]{loc}[/dim]")
            if f.fix_hint:
                console.print(f"    [dim italic]Fix: {f.fix_hint}[/dim italic]")
