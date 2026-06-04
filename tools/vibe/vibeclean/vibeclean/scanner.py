"""Orchestration -- runner dispatch, progress display, result aggregation."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.text import Text

from vibeclean.config import Config
from vibeclean.models import (
    Finding,
    ScanResult,
    RunnerResult,
    RunnerStatus,
    Severity,
)
from vibeclean.runners import ALL_RUNNERS


class Scanner:
    """Main scanner orchestrator."""

    def __init__(self, target: str, config: Config):
        self.target = str(Path(target).resolve())
        self.config = config
        self.console = Console(quiet=config.quiet)
        self.runner_statuses: dict[str, tuple[str, str]] = {}

    def _get_enabled_runners(self):
        runners = []
        for runner_cls in ALL_RUNNERS:
            runner = runner_cls(self.target, self.config)
            if not self.config.is_runner_enabled(runner.name):
                self.runner_statuses[runner.name] = ("-", "disabled")
                continue
            runners.append(runner)
        return runners

    def _build_progress_table(self) -> Table:
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column(width=3)
        table.add_column(width=18)
        table.add_column()

        for name, (icon, msg) in sorted(self.runner_statuses.items()):
            style = (
                "green" if icon == "✓"
                else "red" if icon == "✗"
                else "yellow" if icon == "⠋"
                else "dim"
            )
            table.add_row(
                Text(icon, style=style),
                Text(name, style="bold" if icon == "⠋" else ""),
                Text(msg, style="dim" if icon in ("✓", "-") else ""),
            )
        return table

    def scan(self) -> ScanResult:
        """Run all enabled runners and produce a scan result."""
        start = time.monotonic()
        timestamp = datetime.now(timezone.utc).isoformat()

        runners = self._get_enabled_runners()
        runner_results: list[RunnerResult] = []

        if not self.config.quiet:
            self.console.print()
            self.console.print("[bold]vibeclean[/bold] — scanning for code hygiene issues")
            self.console.print()

        for runner in runners:
            self.runner_statuses[runner.name] = ("⠋", "analysing...")

            if not self.config.quiet:
                self.console.print(
                    f"  [yellow]⠋[/yellow] [bold]{runner.name}[/bold] analysing...",
                    end="\r",
                )

            try:
                result = runner.run()
                count = len(result.findings)

                # Filter ignored rules, findings, and excluded paths
                result.findings = [
                    f for f in result.findings
                    if not self.config.should_ignore_rule(f.runner, f.rule_id)
                    and not self.config.should_ignore_finding(f.id)
                    and not self.config.is_path_excluded(f.file)
                ]

                count = len(result.findings)
                self.runner_statuses[runner.name] = (
                    "✓",
                    f"done — {result.duration_seconds:.1f}s — "
                    f"{count} finding{'s' if count != 1 else ''}",
                )

                if not self.config.quiet:
                    self.console.print(
                        f"  [green]✓[/green] [bold]{runner.name}[/bold] "
                        f"done — {result.duration_seconds:.1f}s — "
                        f"{count} finding{'s' if count != 1 else ''}",
                    )

            except Exception as e:
                result = RunnerResult(
                    runner=runner.name,
                    status=RunnerStatus.FAILED,
                    error=str(e),
                )
                self.runner_statuses[runner.name] = ("✗", f"error: {str(e)[:60]}")

                if not self.config.quiet:
                    self.console.print(
                        f"  [red]✗[/red] [bold]{runner.name}[/bold] error: {str(e)[:60]}",
                    )

            runner_results.append(result)

        # Collect all findings
        all_findings: list[Finding] = []
        for rr in runner_results:
            all_findings.extend(rr.findings)

        # Determine exit code
        exit_code = 0
        has_errors = any(
            rr.status == RunnerStatus.FAILED for rr in runner_results
        )

        above_threshold = [f for f in all_findings if f.severity >= self.config.fail_on]
        if above_threshold:
            exit_code = 1

        if has_errors and exit_code == 0:
            exit_code = 2

        elapsed = time.monotonic() - start

        return ScanResult(
            target=self.target,
            timestamp=timestamp,
            runner_results=runner_results,
            findings=all_findings,
            duration_seconds=elapsed,
            exit_code=exit_code,
        )
