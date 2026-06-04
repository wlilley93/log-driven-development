"""Orchestration — runner execution, progress display, result aggregation."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.text import Text

from vibetest.config import Config
from vibetest.models import (
    Finding,
    ScanResult,
    Severity,
    RunnerResult,
    RunnerStatus,
)
from vibetest.runners import ALL_RUNNERS


class Scanner:
    """Main scanner orchestrator."""

    def __init__(self, target: str, config: Config):
        self.target = str(Path(target).resolve())
        self.config = config
        self.console = Console(quiet=config.quiet)

    def _get_enabled_runners(self):
        runners = []
        for runner_cls in ALL_RUNNERS:
            runner = runner_cls(self.target, self.config)
            if not self.config.is_runner_enabled(runner.name):
                continue
            if not runner.should_run():
                continue
            runners.append(runner)
        return runners

    def scan(self) -> ScanResult:
        """Run all enabled runners and produce a scan result."""
        start = time.monotonic()
        timestamp = datetime.now(timezone.utc).isoformat()

        runners = self._get_enabled_runners()

        if not self.config.quiet:
            self.console.print(
                f"\n[bold]vibetest[/bold] — scanning [cyan]{self.target}[/cyan] "
                f"with {len(runners)} runner{'s' if len(runners) != 1 else ''}\n"
            )

        runner_results: list[RunnerResult] = []
        all_findings: list[Finding] = []

        for runner in runners:
            if not self.config.quiet:
                self.console.print(f"  [dim]running[/dim] [bold]{runner.name}[/bold]...", end=" ")

            try:
                result = runner.run()
                result.duration_seconds = time.monotonic() - start

                # Filter ignored rules and excluded paths
                result.findings = [
                    f
                    for f in result.findings
                    if not self.config.should_ignore_rule(f.runner, f.rule_id)
                    and not self.config.is_path_excluded(f.file)
                ]

                count = len(result.findings)
                if not self.config.quiet:
                    self.console.print(
                        f"[green]done[/green] — {count} finding{'s' if count != 1 else ''}"
                    )

            except Exception as e:
                result = RunnerResult(
                    runner=runner.name,
                    status=RunnerStatus.FAILED,
                    error=str(e),
                )
                if not self.config.quiet:
                    self.console.print(f"[red]error[/red]: {e}")

            runner_results.append(result)
            all_findings.extend(result.findings)

        # Determine exit code
        exit_code = 0
        above_threshold = [f for f in all_findings if f.severity >= self.config.fail_on]
        if above_threshold:
            exit_code = 1

        has_errors = any(rr.status == RunnerStatus.FAILED for rr in runner_results)
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
