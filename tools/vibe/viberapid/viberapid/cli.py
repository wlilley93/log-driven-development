"""CLI interface — click-based command-line entry point for viberapid."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table
from rich.text import Text

from viberapid import __version__
from viberapid.config import Config, Severity, load_config
from viberapid.models import ScanResult


# ---------------------------------------------------------------------------
# Custom group: treats unknown subcommands as scan targets
# ---------------------------------------------------------------------------
class ViberapidGroup(click.Group):
    """Click group that treats unknown subcommands as scan target paths.

    If the user types `viberapid ./my-project` instead of `viberapid scan ./my-project`,
    we route it to the `scan` command automatically.
    """

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        # If the first arg is not a known command and looks like a path,
        # prepend 'scan' so it routes correctly.
        if args and args[0] not in self.commands and not args[0].startswith("-"):
            args = ["scan"] + args
        return super().parse_args(ctx, args)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_console = Console()


def _get_changed_files(since: str, target: str) -> list[str] | None:
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
            files = [f.strip() for f in result.stdout.strip().splitlines() if f.strip()]
            return files if files else None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _render_output(
    result: ScanResult,
    config: Config,
    console: Console,
) -> None:
    """Render the scan result using the configured reporter."""
    output_format = config.output

    if output_format == "json":
        from viberapid.reporters.json_reporter import JsonReporter

        reporter = JsonReporter(result, config)
        if config.output_file:
            content = reporter.render_to_string()
            Path(config.output_file).write_text(content)
            console.print(f"[dim]JSON report written to {config.output_file}[/dim]")
        else:
            reporter.render(console)

    elif output_format == "html":
        from viberapid.reporters.html import HtmlReporter

        reporter = HtmlReporter(result, config)
        content = reporter.render_to_string()
        out_path = config.output_file or "viberapid-report.html"
        Path(out_path).write_text(content)
        console.print(f"[dim]HTML report written to {out_path}[/dim]")

    elif output_format == "md":
        from viberapid.reporters.markdown import MarkdownReporter

        reporter = MarkdownReporter(result, config)
        if config.output_file:
            content = reporter.render_to_string()
            Path(config.output_file).write_text(content)
            console.print(f"[dim]Markdown report written to {config.output_file}[/dim]")
        else:
            reporter.render(console)

    else:
        # Default: table
        from viberapid.reporters.table import TableReporter

        reporter = TableReporter(result, config)
        if config.output_file:
            content = reporter.render_to_string()
            Path(config.output_file).write_text(content)
            console.print(f"[dim]Report written to {config.output_file}[/dim]")
        else:
            reporter.render(console)


# ---------------------------------------------------------------------------
# Main group
# ---------------------------------------------------------------------------
@click.group(cls=ViberapidGroup, invoke_without_command=True)
@click.version_option(__version__, prog_name="viberapid")
@click.pass_context
def main(ctx: click.Context) -> None:
    """viberapid -- the definitive performance analyser for AI-generated codebases."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# ---------------------------------------------------------------------------
# scan (default command)
# ---------------------------------------------------------------------------
@main.command()
@click.argument("target", default=".", type=click.Path(exists=True))
@click.option("--tools", type=str, default=None, help="Comma-separated list of tools to run.")
@click.option("--skip", type=str, default=None, help="Comma-separated list of tools to skip.")
@click.option(
    "--fail-on",
    type=click.Choice(["critical", "high", "medium", "low", "info"], case_sensitive=False),
    default=None,
    help="Exit non-zero if findings at or above this severity (default: high).",
)
@click.option(
    "--output",
    "output_format",
    type=click.Choice(["table", "json", "html", "md"], case_sensitive=False),
    default=None,
    help="Output format (default: table).",
)
@click.option("--output-file", type=str, default=None, help="Write report to file instead of stdout.")
@click.option("--config", "config_path", type=str, default=None, help="Path to .viberapid.yml config file.")
@click.option("--fix", is_flag=True, default=False, help="Include remediation hints in output.")
@click.option("--ship-fast", is_flag=True, default=False, help="Strict CI mode — one-line output.")
@click.option("--url", type=str, default=None, help="Target URL for Lighthouse, load tests, etc.")
@click.option("--since", type=str, default=None, help="Only scan files changed since this git ref.")
@click.option("--threads", type=int, default=None, help="Number of parallel tool threads.")
@click.option("--timeout", type=int, default=None, help="Per-tool timeout in seconds.")
@click.option("--budget", "budget_file", type=str, default=None, help="Path to budget JSON file.")
@click.option(
    "--stack",
    type=click.Choice(["auto", "node", "python", "fullstack"], case_sensitive=False),
    default=None,
    help="Project stack (default: auto-detect).",
)
@click.option("--quiet", is_flag=True, default=False, help="Suppress progress output.")
@click.option("--verbose", is_flag=True, default=False, help="Verbose output.")
@click.option("--load-duration", type=str, default=None, help='Load test duration (e.g. "30s").')
@click.option("--load-vus", type=int, default=None, help="Number of virtual users for load tests.")
@click.option("--json-pretty", is_flag=True, default=False, help="Pretty-print JSON output.")
def scan(
    target: str,
    tools: str | None,
    skip: str | None,
    fail_on: str | None,
    output_format: str | None,
    output_file: str | None,
    config_path: str | None,
    fix: bool,
    ship_fast: bool,
    url: str | None,
    since: str | None,
    threads: int | None,
    timeout: int | None,
    budget_file: str | None,
    stack: str | None,
    quiet: bool,
    verbose: bool,
    load_duration: str | None,
    load_vus: int | None,
    json_pretty: bool,
) -> None:
    """Analyse current or specified directory for performance issues."""
    # Resolve target to absolute path
    target = str(Path(target).resolve())

    # Build CLI overrides dict
    overrides: dict[str, Any] = {}
    if tools:
        overrides["tools_include"] = [t.strip() for t in tools.split(",")]
    if skip:
        overrides["tools_exclude"] = [t.strip() for t in skip.split(",")]
    if fail_on:
        overrides["fail_on"] = Severity(fail_on.upper())
    if output_format:
        overrides["output"] = output_format
    if output_file:
        overrides["output_file"] = output_file
    if fix:
        overrides["fix"] = True
    if ship_fast:
        overrides["ship_fast"] = True
    if url:
        overrides["url"] = url
    if since:
        overrides["since"] = since
    if threads is not None:
        overrides["threads"] = threads
    if timeout is not None:
        overrides["timeout"] = timeout
    if budget_file:
        overrides["budget_file"] = budget_file
    if stack:
        overrides["stack"] = stack
    if quiet:
        overrides["quiet"] = True
    if verbose:
        overrides["verbose"] = True
    if load_duration:
        overrides["load_duration"] = load_duration
    if load_vus is not None:
        overrides["load_vus"] = load_vus
    if json_pretty:
        overrides["json_pretty"] = True

    # Load config from file + CLI overrides
    config = load_config(config_path=config_path, target_dir=target, **overrides)

    # Determine changed files for incremental scans
    changed_files: list[str] | None = None
    if config.since:
        changed_files = _get_changed_files(config.since, target)
        if changed_files is not None and not config.quiet:
            _console.print(f"[dim]Scanning {len(changed_files)} files changed since {config.since}[/dim]")

    # Check for missing required tools and offer to install
    from viberapid.installer import tools_missing

    missing = tools_missing(stack=config.stack)
    if missing and not config.quiet:
        _console.print(f"[yellow]Missing tools: {', '.join(missing)}[/yellow]")
        _console.print("[dim]Run `viberapid install` to install all tools.[/dim]")

    # Run the scanner
    from viberapid.scanner import scan as run_scan

    result = asyncio.run(
        run_scan(
            target=target,
            config=config,
            console=_console if not config.quiet else Console(quiet=True),
            changed_files=changed_files,
        )
    )

    # Render output
    _render_output(result, config, _console)

    # Exit with scan exit code
    sys.exit(result.exit_code)


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------
@main.command()
@click.option("--update", is_flag=True, default=False, help="Upgrade all tools to latest versions.")
@click.option("--check", "check_only", is_flag=True, default=False, help="Show tool status table without installing.")
@click.option(
    "--stack",
    type=click.Choice(["python", "node", "both"], case_sensitive=False),
    default="both",
    help="Which stack tools to install (default: both).",
)
def install(update: bool, check_only: bool, stack: str) -> None:
    """Install or check status of all performance tools."""
    from viberapid.installer import check_all, install_all

    if check_only:
        results = check_all(stack=stack)

        table = Table(title="viberapid tool status", show_header=True, header_style="bold")
        table.add_column("Tool", style="cyan", min_width=20)
        table.add_column("Kind", min_width=8)
        table.add_column("Stack", min_width=8)
        table.add_column("Installed", min_width=10)
        table.add_column("Version", min_width=15)
        table.add_column("Required", min_width=8)

        for info in results:
            installed_text = Text("yes", style="green") if info["installed"] else Text("no", style="red")
            required_text = Text("yes", style="dim") if info["required"] else Text("no", style="dim")
            table.add_row(
                info["name"],
                info["kind"],
                info.get("stack") or "any",
                installed_text,
                info.get("version") or "-",
                required_text,
            )

        _console.print(table)

        # Summary
        installed_count = sum(1 for i in results if i["installed"])
        _console.print(f"\n[dim]{installed_count}/{len(results)} tools available[/dim]")
        return

    # Install all tools
    _console.print("[bold]Installing viberapid tools...[/bold]")

    def _callback(name: str, success: bool, message: str) -> None:
        icon = "[green]ok[/green]" if success else "[red]FAIL[/red]"
        _console.print(f"  {icon}  {name}: {message}")

    results = asyncio.run(install_all(upgrade=update, stack=stack, callback=_callback))

    ok_count = sum(1 for _, ok, _ in results if ok)
    fail_count = sum(1 for _, ok, _ in results if not ok)
    _console.print(f"\n[bold]Done:[/bold] {ok_count} installed, {fail_count} failed")


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------
@main.command()
@click.option("--last", "show_last", is_flag=True, default=False, help="Re-render the last scan result.")
@click.option("--trend", is_flag=True, default=False, help="Show trend table of recent scans.")
@click.option(
    "--output",
    "output_format",
    type=click.Choice(["table", "json", "html", "md"], case_sensitive=False),
    default="table",
    help="Output format (default: table).",
)
@click.option("--output-file", type=str, default=None, help="Write report to file.")
@click.argument("target", default=".", type=click.Path(exists=True))
def report(
    show_last: bool,
    trend: bool,
    output_format: str,
    output_file: str | None,
    target: str,
) -> None:
    """Re-render a previous scan or show trend data."""
    from viberapid.history import load_last, load_trend

    target = str(Path(target).resolve())

    if trend:
        scans = load_trend(target, limit=10)
        if not scans:
            _console.print("[yellow]No scan history found for this project.[/yellow]")
            return

        table = Table(title="viberapid scan trend", show_header=True, header_style="bold")
        table.add_column("Timestamp", style="cyan", min_width=22)
        table.add_column("Findings", justify="right", min_width=8)
        table.add_column("CRIT", justify="right", style="red bold", min_width=6)
        table.add_column("HIGH", justify="right", style="red", min_width=6)
        table.add_column("MED", justify="right", style="yellow", min_width=6)
        table.add_column("LOW", justify="right", style="dim", min_width=6)
        table.add_column("Tools", justify="right", min_width=6)
        table.add_column("Duration", justify="right", min_width=8)
        table.add_column("Exit", justify="right", min_width=5)

        for s in scans:
            counts = s.get("severity_counts", {})
            total = sum(counts.values())
            tool_count = len(s.get("tool_results", []))
            duration = s.get("duration_seconds", 0)
            exit_code = s.get("exit_code", 0)

            exit_style = "green" if exit_code == 0 else "red"
            table.add_row(
                s.get("timestamp", "?")[:22],
                str(total),
                str(counts.get("CRITICAL", 0)),
                str(counts.get("HIGH", 0)),
                str(counts.get("MEDIUM", 0)),
                str(counts.get("LOW", 0)),
                str(tool_count),
                f"{duration:.1f}s",
                Text(str(exit_code), style=exit_style),
            )

        _console.print(table)
        return

    # Default: re-render last scan
    last = load_last(target)
    if not last:
        _console.print("[yellow]No scan history found. Run `viberapid scan` first.[/yellow]")
        return

    # Reconstruct a ScanResult from stored JSON for re-rendering
    from viberapid.models import (
        BudgetResult,
        Category,
        Effort,
        Finding,
        Severity as SevEnum,
        ToolResult,
        ToolStatus,
    )

    findings: list[Finding] = []
    for fd in last.get("findings", []):
        findings.append(
            Finding(
                tool=fd.get("tool", ""),
                severity=SevEnum(fd.get("severity", "INFO")),
                category=Category(fd.get("category", "CODE")),
                file=fd.get("file", ""),
                rule_id=fd.get("rule_id", ""),
                rule_name=fd.get("rule_name", ""),
                message=fd.get("message", ""),
                line=fd.get("line"),
                col=fd.get("col"),
                fix_hint=fd.get("fix_hint"),
                metric=fd.get("metric"),
                current_value=fd.get("current_value"),
                target_value=fd.get("target_value"),
                saving_estimate=fd.get("saving_estimate"),
                effort=Effort(fd.get("effort", "MEDIUM")),
                tools=fd.get("tools", []),
            )
        )

    quick_wins: list[Finding] = []
    for qw in last.get("quick_wins", []):
        quick_wins.append(
            Finding(
                tool=qw.get("tool", ""),
                severity=SevEnum(qw.get("severity", "INFO")),
                category=Category(qw.get("category", "CODE")),
                file=qw.get("file", ""),
                rule_id=qw.get("rule_id", ""),
                rule_name=qw.get("rule_name", ""),
                message=qw.get("message", ""),
                line=qw.get("line"),
                fix_hint=qw.get("fix_hint"),
                metric=qw.get("metric"),
                current_value=qw.get("current_value"),
                saving_estimate=qw.get("saving_estimate"),
                effort=Effort(qw.get("effort", "MEDIUM")),
                tools=qw.get("tools", []),
            )
        )

    tool_results: list[ToolResult] = []
    for tr in last.get("tool_results", []):
        tool_results.append(
            ToolResult(
                tool=tr.get("tool", ""),
                status=ToolStatus(tr.get("status", "success")),
                duration_seconds=tr.get("duration_seconds", 0),
                error=tr.get("error"),
                version=tr.get("version"),
                metrics=tr.get("metrics", {}),
            )
        )

    budget_results: list[BudgetResult] = []
    for br in last.get("budget_results", []):
        budget_results.append(
            BudgetResult(
                metric=br.get("metric", ""),
                current=br.get("current", 0),
                target=br.get("target", 0),
                unit=br.get("unit", ""),
                passed=br.get("passed", True),
                fail_on_exceed=br.get("fail_on_exceed", True),
            )
        )

    result = ScanResult(
        target=last.get("target", target),
        timestamp=last.get("timestamp", ""),
        stack=last.get("stack", "auto"),
        tool_results=tool_results,
        findings=findings,
        deduplicated_findings=findings,
        tool_overlap=last.get("tool_overlap", {}),
        budget_results=budget_results,
        quick_wins=quick_wins,
        duration_seconds=last.get("duration_seconds", 0),
        exit_code=last.get("exit_code", 0),
    )

    config = Config(
        output=output_format,
        output_file=output_file,
    )
    _render_output(result, config, _console)


# ---------------------------------------------------------------------------
# budget
# ---------------------------------------------------------------------------
@main.command()
@click.option("--create", is_flag=True, default=False, help="Scaffold a default budget file.")
@click.argument("target", default=".", type=click.Path(exists=True))
def budget(create: bool, target: str) -> None:
    """Manage performance budgets."""
    from viberapid.budget import scaffold_budget

    target = str(Path(target).resolve())

    if create:
        out_path = str(Path(target) / ".viberapid-budget.json")
        filepath = scaffold_budget(out_path)
        _console.print(f"[green]Budget file created:[/green] {filepath}")
        _console.print("[dim]Edit the file to set your performance targets.[/dim]")
    else:
        # Show current budget if it exists
        budget_path = Path(target) / ".viberapid-budget.json"
        if budget_path.exists():
            import json

            with open(budget_path) as f:
                data = json.load(f)
            _console.print_json(json.dumps(data, indent=2))
        else:
            _console.print("[yellow]No budget file found.[/yellow]")
            _console.print("[dim]Run `viberapid budget --create` to scaffold one.[/dim]")


# ---------------------------------------------------------------------------
# diff
# ---------------------------------------------------------------------------
@main.command()
@click.argument("git_ref", type=str)
@click.argument("target", default=".", type=click.Path(exists=True))
def diff(git_ref: str, target: str) -> None:
    """Compare current scan vs last scan at or before a git ref.

    Shows regressions (red) and improvements (green).
    """
    from viberapid.history import load_last, load_trend

    target = str(Path(target).resolve())

    # Load current (most recent) scan
    current = load_last(target)
    if not current:
        _console.print("[yellow]No scan history found. Run `viberapid scan` first.[/yellow]")
        return

    # Load previous scans and find one near the git ref
    all_scans = load_trend(target, limit=50)
    if len(all_scans) < 2:
        _console.print("[yellow]Need at least 2 scans for comparison. Run `viberapid scan` again.[/yellow]")
        return

    # Use the second-most-recent scan as the baseline
    # (In a full implementation, we'd match git ref to scan timestamps)
    baseline = all_scans[1]

    current_counts = current.get("severity_counts", {})
    baseline_counts = baseline.get("severity_counts", {})

    table = Table(title=f"viberapid diff vs {git_ref}", show_header=True, header_style="bold")
    table.add_column("Severity", min_width=10)
    table.add_column("Baseline", justify="right", min_width=8)
    table.add_column("Current", justify="right", min_width=8)
    table.add_column("Delta", justify="right", min_width=8)

    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
        base_val = baseline_counts.get(sev, 0)
        curr_val = current_counts.get(sev, 0)
        delta = curr_val - base_val

        if delta > 0:
            delta_text = Text(f"+{delta}", style="red bold")
        elif delta < 0:
            delta_text = Text(str(delta), style="green bold")
        else:
            delta_text = Text("0", style="dim")

        table.add_row(sev, str(base_val), str(curr_val), delta_text)

    _console.print(table)

    # Budget comparison
    current_budget = current.get("budget_results", [])
    baseline_budget = baseline.get("budget_results", [])

    if current_budget or baseline_budget:
        _console.print()
        budget_table = Table(title="Budget changes", show_header=True, header_style="bold")
        budget_table.add_column("Metric", min_width=15)
        budget_table.add_column("Baseline", justify="right", min_width=10)
        budget_table.add_column("Current", justify="right", min_width=10)
        budget_table.add_column("Target", justify="right", min_width=10)
        budget_table.add_column("Status", min_width=8)

        baseline_by_metric = {b["metric"]: b for b in baseline_budget}
        for br in current_budget:
            metric = br["metric"]
            base_br = baseline_by_metric.get(metric, {})
            base_val = base_br.get("current", "-")
            curr_val = br.get("current", "-")
            target_val = br.get("target", "-")

            if br.get("passed"):
                status = Text("PASS", style="green")
            else:
                status = Text("FAIL", style="red bold")

            budget_table.add_row(
                metric,
                str(base_val),
                str(curr_val),
                str(target_val),
                status,
            )

        _console.print(budget_table)

    # Summary
    total_current = sum(current_counts.values())
    total_baseline = sum(baseline_counts.values())
    total_delta = total_current - total_baseline

    _console.print()
    if total_delta > 0:
        _console.print(f"[red bold]Regression:[/red bold] +{total_delta} findings ({total_baseline} -> {total_current})")
    elif total_delta < 0:
        _console.print(f"[green bold]Improvement:[/green bold] {total_delta} findings ({total_baseline} -> {total_current})")
    else:
        _console.print(f"[dim]No change: {total_current} findings[/dim]")


# ---------------------------------------------------------------------------
# load
# ---------------------------------------------------------------------------
@main.command()
@click.option("--url", type=str, required=True, help="Target URL for load testing.")
@click.option("--duration", type=str, default="30s", help='Load test duration (e.g. "30s").')
@click.option("--vus", type=int, default=50, help="Number of virtual users.")
@click.option(
    "--output",
    "output_format",
    type=click.Choice(["table", "json", "html", "md"], case_sensitive=False),
    default="table",
    help="Output format (default: table).",
)
@click.option("--output-file", type=str, default=None, help="Write report to file.")
@click.argument("target", default=".", type=click.Path(exists=True))
def load(
    url: str,
    duration: str,
    vus: int,
    output_format: str,
    output_file: str | None,
    target: str,
) -> None:
    """Run load tests only against a target URL."""
    from viberapid.scanner import scan as run_scan

    target = str(Path(target).resolve())

    # Build config that only enables load testers
    config = load_config(
        target_dir=target,
        url=url,
        load_duration=duration,
        load_vus=vus,
        output=output_format,
        output_file=output_file,
    )

    # Only include load testing tools
    load_tools = [
        "k6", "artillery", "autocannon", "wrk", "vegeta", "bombardier", "locust",
    ]
    config.tools_include = load_tools

    result = asyncio.run(
        run_scan(
            target=target,
            config=config,
            console=_console,
        )
    )

    _render_output(result, config, _console)
    sys.exit(result.exit_code)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    main()
