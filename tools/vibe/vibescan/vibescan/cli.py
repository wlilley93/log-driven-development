"""CLI entrypoint — click commands, flags, dispatch."""

from __future__ import annotations

import asyncio
import sys

import click
from rich.console import Console

from vibescan import __version__
from vibescan.config import load_config
from vibescan.models import Severity


class VibescanGroup(click.Group):
    """Custom group that treats unknown subcommands as scan targets."""

    def parse_args(self, ctx, args):
        # If first arg is not a known command and not a flag, treat it as scan target
        if args and args[0] not in self.commands and not args[0].startswith("-"):
            args = ["scan", *args]
        # If no args at all, default to scan with "."
        if not args:
            args = ["scan"]
        return super().parse_args(ctx, args)


@click.group(cls=VibescanGroup, invoke_without_command=True)
@click.version_option(__version__, prog_name="vibescan")
@click.pass_context
def main(ctx):
    """vibescan — the definitive security scanner for AI-generated codebases."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(scan)


# --- Scan command (default) ---

@main.command()
@click.argument("target", default=".")
@click.option("--tools", default=None, help="Run only named tools (comma-separated)")
@click.option("--skip", default=None, help="Skip named tools (comma-separated)")
@click.option(
    "--fail-on",
    type=click.Choice(["critical", "high", "medium", "low", "info"], case_sensitive=False),
    default=None,
    help="Exit 1 threshold (default: high)",
)
@click.option(
    "--output",
    "output_format",
    type=click.Choice(["table", "json", "html", "sarif", "md"], case_sensitive=False),
    default=None,
    help="Report format (default: table)",
)
@click.option("--output-file", default=None, help="Write report to file")
@click.option("--config", "config_path", default=None, help="Config file path")
@click.option("--fix", is_flag=True, help="Include remediation hints")
@click.option("--ship-safe", is_flag=True, help="Strict CI mode")
@click.option("--deep", is_flag=True, help="Include CodeQL (slow)")
@click.option("--no-secrets", is_flag=True, help="Skip all secret scanners")
@click.option("--since", default=None, help="Scan only files changed since git ref")
@click.option("--threads", type=int, default=None, help="Parallelism (default: cpu_count)")
@click.option("--timeout", type=int, default=None, help="Per-tool timeout in seconds")
@click.option("--json-pretty", is_flag=True, help="Pretty-print JSON output")
@click.option("--quiet", is_flag=True, help="Suppress progress, findings only")
@click.option("--verbose", is_flag=True, help="Debug output")
def scan(target, tools, skip, fail_on, output_format, output_file, config_path,
         fix, ship_safe, deep, no_secrets, since, threads, timeout, json_pretty,
         quiet, verbose):
    """Scan a directory for security issues (default command)."""
    # Build config
    overrides = {}
    if fail_on:
        overrides["fail_on"] = Severity(fail_on.upper())
    if output_format:
        overrides["output"] = output_format
    if output_file:
        overrides["output_file"] = output_file
    if fix:
        overrides["fix"] = True
    if ship_safe:
        overrides["ship_safe"] = True
    if deep:
        overrides["deep"] = True
    if no_secrets:
        overrides["no_secrets"] = True
    if since:
        overrides["since"] = since
    if threads is not None:
        overrides["threads"] = threads
    if timeout is not None:
        overrides["timeout"] = timeout
    if json_pretty:
        overrides["json_pretty"] = True
    if quiet:
        overrides["quiet"] = True
    if verbose:
        overrides["verbose"] = True
    if tools:
        overrides["tools_include"] = [t.strip() for t in tools.split(",")]
    if skip:
        overrides["tools_exclude"] = [t.strip() for t in skip.split(",")]

    config = load_config(config_path=config_path, target_dir=target, **overrides)
    console = Console(quiet=config.quiet)

    # Check if tools are installed
    from vibescan.installer import tools_missing

    missing = tools_missing()
    if missing:
        console.print(
            f"[yellow]Missing tools: {', '.join(missing)}[/yellow]\n"
            "Run [bold]vibescan install[/bold] to set up all tools."
        )
        console.print("[dim]Auto-installing missing tools...[/dim]")
        from vibescan.installer import install_all

        asyncio.run(install_all())
        missing = tools_missing()
        if missing:
            console.print(f"[red]Still missing: {', '.join(missing)}[/red]")
            console.print("Some tools could not be installed. Continuing with available tools.")

    # Run scan
    from vibescan.scanner import Scanner

    scanner = Scanner(target, config)
    result = asyncio.run(scanner.scan())

    # Render output
    _render_output(result, config, console)

    sys.exit(result.exit_code)


# --- Helpers ---

def _render_output(result, config, console):
    """Dispatch to the appropriate reporter."""
    from vibescan.reporters.table import TableReporter
    from vibescan.reporters.json_reporter import JsonReporter
    from vibescan.reporters.html import HtmlReporter
    from vibescan.reporters.sarif import SarifReporter
    from vibescan.reporters.markdown import MarkdownReporter

    reporters = {
        "table": TableReporter,
        "json": JsonReporter,
        "html": HtmlReporter,
        "sarif": SarifReporter,
        "md": MarkdownReporter,
    }

    reporter_cls = reporters.get(config.output, TableReporter)
    reporter = reporter_cls(result, config)

    if config.ship_safe and config.output == "table":
        reporter.render_ship_safe(console)
        _emit_github_annotations(result)
    elif config.output_file:
        content = reporter.render_to_string()
        with open(config.output_file, "w") as f:
            f.write(content)
        if not config.quiet:
            console.print(f"Report written to {config.output_file}")
    else:
        reporter.render(console)


def _emit_github_annotations(result):
    """Emit GitHub Actions annotations for blocking findings."""
    if not result.deduplicated_findings:
        return

    for f in result.deduplicated_findings:
        if f.severity >= Severity.HIGH:
            line_part = f",line={f.line}" if f.line else ""
            print(f"::error file={f.file}{line_part}::[{f.tool}] {f.message}")


# --- Install command ---

@main.command()
@click.option("--update", is_flag=True, help="Upgrade all tools to latest")
@click.option("--check", is_flag=True, help="Check tool status without installing")
def install(update, check):
    """Download and manage all security tools."""
    console = Console()

    if check:
        from vibescan.installer import check_all

        results = check_all()
        from rich.table import Table

        table = Table(title="vibescan tool status")
        table.add_column("Tool", style="bold")
        table.add_column("Kind")
        table.add_column("Status")
        table.add_column("Version")
        table.add_column("Notes")

        for info in results:
            status = "[green]✓[/green]" if info["installed"] else "[red]✗[/red]"
            notes = ""
            if info.get("skip_reason"):
                notes = info["skip_reason"]
            elif info.get("deep_only"):
                notes = "--deep only"
            elif not info["required"]:
                notes = "optional"

            table.add_row(
                info["name"],
                info["kind"],
                status,
                info.get("version") or "-",
                notes,
            )

        console.print(table)
        return

    console.print("[bold]vibescan install[/bold] — setting up security tools\n")

    def on_progress(name, success, msg):
        icon = "[green]✓[/green]" if success else "[red]✗[/red]"
        console.print(f"  {icon} {name}: {msg}")

    from vibescan.installer import install_all

    results = asyncio.run(install_all(upgrade=update, callback=on_progress))

    ok = sum(1 for _, s, _ in results if s)
    fail = sum(1 for _, s, _ in results if not s)
    console.print(f"\n[bold]{ok} installed, {fail} failed[/bold]")


# --- Report command ---

@main.command()
@click.option("--last", is_flag=True, help="Re-render last scan results")
@click.option("--trend", is_flag=True, help="Show finding count over time")
@click.option("--target", default=".", help="Project directory")
@click.option(
    "--output",
    "output_format",
    type=click.Choice(["table", "json", "html", "sarif", "md"], case_sensitive=False),
    default="table",
)
@click.option("--output-file", default=None)
def report(last, trend, target, output_format, output_file):
    """Re-render scan results without re-scanning."""
    console = Console()

    if trend:
        from vibescan.history import load_trend

        entries = load_trend(target)
        if not entries:
            console.print("[yellow]No scan history found.[/yellow]")
            return

        from rich.table import Table

        table = Table(title="vibescan scan trend")
        table.add_column("Date")
        table.add_column("Critical", style="red")
        table.add_column("High", style="yellow")
        table.add_column("Medium")
        table.add_column("Low", style="dim")
        table.add_column("Exit")

        for entry in entries:
            counts = entry.get("severity_counts", {})
            table.add_row(
                str(entry.get("timestamp", "?"))[:19],
                str(counts.get("CRITICAL", 0)),
                str(counts.get("HIGH", 0)),
                str(counts.get("MEDIUM", 0)),
                str(counts.get("LOW", 0)),
                str(entry.get("exit_code", "?")),
            )

        console.print(table)
        return

    if last:
        from vibescan.history import load_last
        from vibescan.models import ScanResult, Finding, Category, ToolResult, ToolStatus

        data = load_last(target)
        if not data:
            console.print("[yellow]No previous scan found.[/yellow]")
            return

        result = ScanResult(
            target=data.get("target", target),
            timestamp=data.get("timestamp", ""),
            duration_seconds=data.get("duration_seconds", 0),
            exit_code=data.get("exit_code", 0),
            tool_overlap=data.get("tool_overlap", {}),
        )

        for f_data in data.get("findings", []):
            finding = Finding(
                tool=f_data.get("tool", ""),
                severity=Severity(f_data.get("severity", "INFO")),
                category=Category(f_data.get("category", "CODE")),
                file=f_data.get("file", ""),
                rule_id=f_data.get("rule_id", ""),
                rule_name=f_data.get("rule_name", ""),
                message=f_data.get("message", ""),
                line=f_data.get("line"),
                cve=f_data.get("cve"),
                cvss=f_data.get("cvss"),
                licence=f_data.get("licence"),
                secret_verified=f_data.get("secret_verified"),
                fix_hint=f_data.get("fix_hint"),
                tools=f_data.get("tools", []),
            )
            result.deduplicated_findings.append(finding)

        for tr_data in data.get("tool_results", []):
            result.tool_results.append(
                ToolResult(
                    tool=tr_data.get("tool", ""),
                    status=ToolStatus(tr_data.get("status", "success")),
                    duration_seconds=tr_data.get("duration_seconds", 0),
                    error=tr_data.get("error"),
                )
            )

        config = load_config(target_dir=target, output=output_format, output_file=output_file)
        _render_output(result, config, console)
        return

    console.print("Specify --last or --trend. Run vibescan report --help for details.")


# --- Baseline command ---

@main.command()
@click.option("--create", is_flag=True, help="Create detect-secrets baseline")
@click.option("--update", "update_baseline", is_flag=True, help="Update existing baseline")
@click.argument("target", default=".")
def baseline(create, update_baseline, target):
    """Manage detect-secrets baseline."""
    console = Console()

    from vibescan.baseline import create_baseline, update_baseline as do_update
    from vibescan.installer import get_tool_bin

    bin_path = get_tool_bin("detect-secrets")

    if create:
        ok, msg = create_baseline(target, bin_path)
        style = "green" if ok else "red"
        console.print(f"[{style}]{msg}[/{style}]")
    elif update_baseline:
        ok, msg = do_update(target, bin_path)
        style = "green" if ok else "red"
        console.print(f"[{style}]{msg}[/{style}]")
    else:
        console.print("Specify --create or --update. Run vibescan baseline --help for details.")


if __name__ == "__main__":
    main()
