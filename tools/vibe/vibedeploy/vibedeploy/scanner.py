"""Orchestration — async tool runner, progress display, result aggregation."""

from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.text import Text

from vibedeploy.config import Config
from vibedeploy.deduplicator import deduplicate
from vibedeploy.detector import detect_stack
from vibedeploy.history import save_scan, prune_history
from vibedeploy.models import (
    Finding,
    ScanResult,
    Severity,
    ToolResult,
    ToolStatus,
)


class Scanner:
    """Main scanner orchestrator."""

    def __init__(self, target: str, config: Config):
        self.target = str(Path(target).resolve())
        self.config = config
        self.console = Console(quiet=config.quiet)
        self.tool_statuses: dict[str, tuple[str, str]] = {}

    def _get_all_runner_classes(self) -> list:
        """Import and return all runner classes."""
        from vibedeploy.runners import ALL_RUNNERS
        return ALL_RUNNERS

    def _get_enabled_runners(self, stack_info: dict[str, Any]):
        """Filter runners based on config, stack detection, and tool flags."""
        recommended = set(stack_info.get("recommended_tools", []))
        url_tools = set(stack_info.get("url_tools", []))

        # Add URL tools if --url is provided
        if self.config.url:
            recommended.update(url_tools)

        runners = []
        for runner_cls in self._get_all_runner_classes():
            runner = runner_cls(self.target, self.config)

            # Config-level include/exclude
            if not self.config.is_tool_enabled(runner.name):
                continue

            # URL requirement check
            if runner.requires_url and not self.config.url:
                self.tool_statuses[runner.name] = ("-", "requires --url")
                continue

            # Stack relevance check (unless tools explicitly specified)
            if self.config.tools_include is None and runner.name not in recommended:
                # Custom tools run regardless of stack detection
                from vibedeploy.installer import get_tool_spec
                spec = get_tool_spec(runner.name)
                if spec and spec.kind != "custom":
                    self.tool_statuses[runner.name] = ("-", "not relevant for detected stack")
                    continue

            # Pre-flight check
            if not runner.should_run():
                reason = runner.skip_reason or "not applicable"
                self.tool_statuses[runner.name] = ("\u2298", reason)
                continue

            runners.append(runner)
        return runners

    def _build_progress_table(self) -> Table:
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column(width=3)
        table.add_column(width=22)
        table.add_column()

        for tool_name, (icon, msg) in sorted(self.tool_statuses.items()):
            style = "green" if icon == "\u2713" else "red" if icon == "\u2717" else "yellow" if icon == "\u280b" else "dim"
            table.add_row(
                Text(icon, style=style),
                Text(tool_name, style="bold" if icon == "\u280b" else ""),
                Text(msg, style="dim" if icon in ("\u2713", "-", "\u2298") else ""),
            )
        return table

    async def _run_tool(
        self,
        runner,
        executor: ThreadPoolExecutor,
    ) -> ToolResult:
        """Run a single tool with timeout."""
        self.tool_statuses[runner.name] = ("\u280b", "scanning...")

        start = time.monotonic()
        try:
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    executor,
                    lambda: runner.run(changed_files=None),
                ),
                timeout=self.config.timeout,
            )
            elapsed = time.monotonic() - start
            result.duration_seconds = elapsed

            # Filter ignored rules and findings
            result.findings = [
                f
                for f in result.findings
                if not self.config.should_ignore_rule(f.tool, f.rule_id)
                and not self.config.should_ignore_finding(f.id)
            ]

            count = len(result.findings)
            blockers = sum(1 for f in result.findings if f.blocks_deploy)
            status_msg = f"done \u2014 {elapsed:.1f}s \u2014 {count} finding{'s' if count != 1 else ''}"
            if blockers:
                status_msg += f" ({blockers} blocker{'s' if blockers != 1 else ''})"
            self.tool_statuses[runner.name] = ("\u2713", status_msg)
            return result

        except asyncio.TimeoutError:
            elapsed = time.monotonic() - start
            self.tool_statuses[runner.name] = ("\u2717", f"timeout after {self.config.timeout}s")
            return ToolResult(
                tool=runner.name,
                status=ToolStatus.TIMEOUT,
                duration_seconds=elapsed,
                error=f"Timed out after {self.config.timeout}s",
            )
        except Exception as e:
            elapsed = time.monotonic() - start
            self.tool_statuses[runner.name] = ("\u2717", f"error: {str(e)[:60]}")
            return ToolResult(
                tool=runner.name,
                status=ToolStatus.FAILED,
                duration_seconds=elapsed,
                error=str(e),
            )

    async def _run_ast_rules(self) -> list[Finding]:
        """Run AST-based source code rules."""
        from vibedeploy.ast_rules import ALL_AST_RULES

        all_findings = []
        for rule in ALL_AST_RULES:
            try:
                findings = rule.scan(self.target)
                all_findings.extend(findings)
            except Exception:
                continue
        return all_findings

    async def scan(self) -> ScanResult:
        """Run all enabled tools and produce a deduplicated scan result."""
        start = time.monotonic()
        timestamp = datetime.now(timezone.utc).isoformat()

        # Auto-detect stack
        stack_info = detect_stack(self.target, self.config.stack)
        if not self.config.quiet:
            tags = stack_info.get("tags", [])
            if tags:
                self.console.print(f"  [dim]Detected stack: {', '.join(tags)}[/dim]")
            tool_count = len(stack_info.get("recommended_tools", []))
            self.console.print(f"  [dim]{tool_count} relevant tools identified[/dim]")

        runners = self._get_enabled_runners(stack_info)

        executor = ThreadPoolExecutor(max_workers=self.config.threads)

        if self.config.quiet or self.config.verbose:
            tasks = [self._run_tool(r, executor) for r in runners]
            tool_results = list(await asyncio.gather(*tasks))
        else:
            tasks = [self._run_tool(r, executor) for r in runners]

            with Live(self._build_progress_table(), console=self.console, refresh_per_second=8) as live:
                gather_task = asyncio.gather(*tasks)

                while not gather_task.done():
                    live.update(self._build_progress_table())
                    await asyncio.sleep(0.15)

                tool_results = list(await gather_task)
                live.update(self._build_progress_table())

        executor.shutdown(wait=False)

        # Run AST rules
        ast_findings = await self._run_ast_rules()

        # Collect all findings
        all_findings: list[Finding] = []
        for tr in tool_results:
            all_findings.extend(tr.findings)
        all_findings.extend(ast_findings)

        # Add AST as a tool result
        if ast_findings:
            tool_results.append(ToolResult(
                tool="ast_rules",
                status=ToolStatus.SUCCESS,
                findings=ast_findings,
            ))

        # Ship-safe: check for secrets immediately
        if self.config.ship_safe:
            secrets = [
                f for f in all_findings
                if f.category.value == "ENV_SECRETS" and f.severity >= Severity.CRITICAL
            ]
            if secrets:
                elapsed = time.monotonic() - start
                result = ScanResult(
                    target=self.target,
                    timestamp=timestamp,
                    tool_results=tool_results,
                    findings=all_findings,
                    deduplicated_findings=secrets,
                    stack_info=stack_info,
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
            # Ship-safe: any deploy blocker → fail
            blockers = [f for f in deduped if f.blocks_deploy]
            if blockers:
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
            tool_results=tool_results,
            findings=all_findings,
            deduplicated_findings=deduped,
            tool_overlap=overlap,
            stack_info=stack_info,
            duration_seconds=elapsed,
            exit_code=exit_code,
        )

        # Persist to history
        save_scan(self.target, result.to_dict())
        prune_history(self.target, self.config.findings_retention)

        return result
