"""Orchestration — async tool runner, progress display, result aggregation."""

from __future__ import annotations

import asyncio
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.text import Text

from vibescan.config import Config
from vibescan.deduplicator import deduplicate
from vibescan.history import save_scan, prune_history
from vibescan.models import (
    Category,
    Finding,
    ScanResult,
    Severity,
    ToolResult,
    ToolStatus,
)

# Import all runners
from vibescan.runners.gitleaks import GitleaksRunner
from vibescan.runners.trufflehog import TrufflehogRunner
from vibescan.runners.detect_secrets import DetectSecretsRunner
from vibescan.runners.semgrep import SemgrepRunner
from vibescan.runners.bandit import BanditRunner
from vibescan.runners.codeql import CodeqlRunner
from vibescan.runners.trivy import TrivyRunner
from vibescan.runners.grype import GrypeRunner
from vibescan.runners.npm_audit import NpmAuditRunner
from vibescan.runners.pip_audit import PipAuditRunner
from vibescan.runners.snyk import SnykRunner
from vibescan.runners.kics import KicsRunner
from vibescan.runners.licence import LicenceRunner

ALL_RUNNERS = [
    GitleaksRunner,
    TrufflehogRunner,
    DetectSecretsRunner,
    SemgrepRunner,
    BanditRunner,
    CodeqlRunner,
    TrivyRunner,
    GrypeRunner,
    NpmAuditRunner,
    PipAuditRunner,
    SnykRunner,
    KicsRunner,
    LicenceRunner,
]


def _get_changed_files(target: str, since: str) -> list[str] | None:
    """Get files changed since a git ref."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", since],
            cwd=target,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return [f for f in result.stdout.strip().split("\n") if f]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


class Scanner:
    """Main scanner orchestrator."""

    def __init__(self, target: str, config: Config):
        self.target = str(Path(target).resolve())
        self.config = config
        self.console = Console(quiet=config.quiet)
        self.tool_statuses: dict[str, tuple[str, str]] = {}  # tool -> (status_icon, message)

    def _get_enabled_runners(self):
        runners = []
        for runner_cls in ALL_RUNNERS:
            runner = runner_cls(self.target, self.config)
            if not self.config.is_tool_enabled(runner.name):
                continue
            if runner.deep_only and not self.config.deep:
                self.tool_statuses[runner.name] = ("-", "use --deep")
                continue
            if self.config.no_secrets and runner.is_secret_scanner:
                self.tool_statuses[runner.name] = ("-", "skipped (--no-secrets)")
                continue
            if not runner.should_run():
                reason = runner.skip_reason or "not applicable"
                self.tool_statuses[runner.name] = ("⊘", reason)
                continue
            runners.append(runner)
        return runners

    def _build_progress_table(self) -> Table:
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column(width=3)
        table.add_column(width=18)
        table.add_column()

        for tool_name, (icon, msg) in sorted(self.tool_statuses.items()):
            style = "green" if icon == "✓" else "red" if icon == "✗" else "yellow" if icon == "⠋" else "dim"
            table.add_row(
                Text(icon, style=style),
                Text(tool_name, style="bold" if icon == "⠋" else ""),
                Text(msg, style="dim" if icon in ("✓", "-", "⊘") else ""),
            )
        return table

    async def _run_tool(
        self,
        runner,
        executor: ThreadPoolExecutor,
        changed_files: list[str] | None,
    ) -> ToolResult:
        """Run a single tool with timeout."""
        self.tool_statuses[runner.name] = ("⠋", "scanning...")

        start = time.monotonic()
        try:
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    executor,
                    lambda: runner.run(changed_files=changed_files),
                ),
                timeout=self.config.timeout,
            )
            elapsed = time.monotonic() - start
            result.duration_seconds = elapsed

            # Filter ignored rules, findings, and globally excluded paths
            result.findings = [
                f
                for f in result.findings
                if not self.config.should_ignore_rule(f.tool, f.rule_id)
                and not self.config.should_ignore_finding(f.id)
                and not self.config.is_path_excluded(f.file)
            ]

            count = len(result.findings)
            self.tool_statuses[runner.name] = (
                "✓",
                f"done — {elapsed:.1f}s — {count} finding{'s' if count != 1 else ''}",
            )
            return result

        except asyncio.TimeoutError:
            elapsed = time.monotonic() - start
            self.tool_statuses[runner.name] = ("✗", f"timeout after {self.config.timeout}s")
            return ToolResult(
                tool=runner.name,
                status=ToolStatus.TIMEOUT,
                duration_seconds=elapsed,
                error=f"Timed out after {self.config.timeout}s",
            )
        except Exception as e:
            elapsed = time.monotonic() - start
            self.tool_statuses[runner.name] = ("✗", f"error: {str(e)[:60]}")
            return ToolResult(
                tool=runner.name,
                status=ToolStatus.FAILED,
                duration_seconds=elapsed,
                error=str(e),
            )

    async def scan(self) -> ScanResult:
        """Run all enabled tools and produce a deduplicated scan result."""
        start = time.monotonic()
        timestamp = datetime.now(timezone.utc).isoformat()

        runners = self._get_enabled_runners()
        changed_files = None
        if self.config.since:
            changed_files = _get_changed_files(self.target, self.config.since)
            if changed_files is not None and not self.config.quiet:
                self.console.print(
                    f"  Scanning {len(changed_files)} changed file(s) since {self.config.since}"
                )

        executor = ThreadPoolExecutor(max_workers=self.config.threads)

        if self.config.quiet or self.config.verbose:
            # No live progress display
            tasks = [self._run_tool(r, executor, changed_files) for r in runners]
            tool_results = await asyncio.gather(*tasks)
        else:
            tasks = [self._run_tool(r, executor, changed_files) for r in runners]

            with Live(self._build_progress_table(), console=self.console, refresh_per_second=8) as live:
                gather_task = asyncio.gather(*tasks)

                while not gather_task.done():
                    live.update(self._build_progress_table())
                    await asyncio.sleep(0.15)

                tool_results = await gather_task
                live.update(self._build_progress_table())

        executor.shutdown(wait=False)

        # Collect all findings
        all_findings: list[Finding] = []
        for tr in tool_results:
            all_findings.extend(tr.findings)

        # Ship-safe: check for verified secrets immediately
        if self.config.ship_safe:
            verified = [
                f for f in all_findings if f.secret_verified is True
            ]
            if verified:
                elapsed = time.monotonic() - start
                result = ScanResult(
                    target=self.target,
                    timestamp=timestamp,
                    tool_results=list(tool_results),
                    findings=all_findings,
                    deduplicated_findings=verified,
                    duration_seconds=elapsed,
                    exit_code=4,
                )
                save_scan(self.target, result.to_dict())
                return result

        # Deduplicate
        deduped, overlap = deduplicate(all_findings)

        # Determine exit code
        exit_code = 0
        has_errors = any(tr.status in (ToolStatus.FAILED, ToolStatus.TIMEOUT) for tr in tool_results)

        if self.config.ship_safe:
            # Ship-safe: any CRITICAL or HIGH → fail
            blockers = [f for f in deduped if f.severity >= Severity.HIGH]
            licence_blockers = [
                f
                for f in deduped
                if f.category == Category.LICENCE
                and f.licence
                and f.licence in self.config.licence_blocklist
            ]
            if blockers or licence_blockers:
                exit_code = 1
        else:
            # Normal mode: check against fail_on threshold
            above_threshold = [f for f in deduped if f.severity >= self.config.fail_on]
            if above_threshold:
                exit_code = 1

        if has_errors and exit_code == 0:
            exit_code = 2

        elapsed = time.monotonic() - start

        result = ScanResult(
            target=self.target,
            timestamp=timestamp,
            tool_results=list(tool_results),
            findings=all_findings,
            deduplicated_findings=deduped,
            tool_overlap=overlap,
            duration_seconds=elapsed,
            exit_code=exit_code,
        )

        # Persist to history
        save_scan(self.target, result.to_dict())
        prune_history(self.target, self.config.findings_retention)

        return result
