"""CLI entrypoint — click commands, flags, dispatch."""

from __future__ import annotations

import asyncio
import sys

import click
from rich.console import Console

from vibedeploy import __version__
from vibedeploy.config import load_config
from vibedeploy.models import Severity, Category


class VibedeployGroup(click.Group):
    """Custom group that treats unknown subcommands as scan targets."""

    def parse_args(self, ctx, args):
        if args and args[0] not in self.commands and not args[0].startswith("-"):
            args = ["scan", *args]
        if not args:
            args = ["scan"]
        return super().parse_args(ctx, args)


@click.group(cls=VibedeployGroup, invoke_without_command=True)
@click.version_option(__version__, prog_name="vibedeploy")
@click.pass_context
def main(ctx):
    """vibedeploy — pre-deploy readiness analyzer for AI-generated codebases."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(scan)


# ── Scan command (default) ──

@main.command()
@click.argument("target", default=".")
@click.option("--tools", default=None, help="Run only named tools (comma-separated)")
@click.option("--skip", default=None, help="Skip named tools (comma-separated)")
@click.option("--url", default=None, help="Target URL for live checks (SSL, headers, CORS)")
@click.option("--env", default=None, help="Environment hint (production, staging, development)")
@click.option("--stack", default=None, help="Stack override (comma-separated)")
@click.option("--cloud", default=None, help="Cloud provider (aws, gcp, azure)")
@click.option("--db", default=None, help="Database type (postgres, mysql, mongodb)")
@click.option(
    "--fail-on",
    type=click.Choice(["critical", "high", "medium", "low", "info"], case_sensitive=False),
    default=None,
    help="Exit 1 threshold (default: high)",
)
@click.option(
    "--output",
    "output_format",
    type=click.Choice(["table", "json", "html", "md", "checklist"], case_sensitive=False),
    default=None,
    help="Report format (default: table)",
)
@click.option("--output-file", default=None, help="Write report to file")
@click.option("--config", "config_path", default=None, help="Config file path")
@click.option("--fix", is_flag=True, help="Include fix commands and hints")
@click.option("--ship-safe", is_flag=True, help="Strict deploy gate — exit 1 on blockers")
@click.option("--dry-run", is_flag=True, help="Show what would run without executing")
@click.option("--threads", type=int, default=None, help="Parallelism (default: cpu_count)")
@click.option("--timeout", type=int, default=None, help="Per-tool timeout in seconds")
@click.option("--json-pretty", is_flag=True, help="Pretty-print JSON output")
@click.option("--quiet", is_flag=True, help="Suppress progress, findings only")
@click.option("--verbose", is_flag=True, help="Debug output")
def scan(target, tools, skip, url, env, stack, cloud, db, fail_on, output_format,
         output_file, config_path, fix, ship_safe, dry_run, threads, timeout,
         json_pretty, quiet, verbose):
    """Scan a directory for deploy readiness issues (default command)."""
    overrides = {}
    if fail_on:
        overrides["fail_on"] = Severity(fail_on.upper())
    if output_format:
        overrides["output"] = output_format
    if output_file:
        overrides["output_file"] = output_file
    if url:
        overrides["url"] = url
    if env:
        overrides["env"] = env
    if stack:
        overrides["stack"] = [s.strip() for s in stack.split(",")]
    if cloud:
        overrides["cloud"] = cloud
    if db:
        overrides["db"] = db
    if fix:
        overrides["fix"] = True
    if ship_safe:
        overrides["ship_safe"] = True
    if dry_run:
        overrides["dry_run"] = True
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

    if config.dry_run:
        _dry_run(target, config, console)
        return

    # Run scan
    from vibedeploy.scanner import Scanner

    scanner = Scanner(target, config)
    result = asyncio.run(scanner.scan())

    # Render output
    _render_output(result, config, console)

    sys.exit(result.exit_code)


# ── Helpers ──

def _dry_run(target, config, console):
    """Show what tools would run without executing."""
    from vibedeploy.detector import detect_stack

    stack_info = detect_stack(target, config.stack)
    console.print("[bold]vibedeploy --dry-run[/bold]\n")
    console.print(f"Target: {target}")

    tags = stack_info.get("tags", [])
    if tags:
        console.print(f"Stack: {', '.join(tags)}")

    console.print(f"\nRecommended tools ({len(stack_info.get('recommended_tools', []))}):")
    for tool in sorted(stack_info.get("recommended_tools", [])):
        enabled = config.is_tool_enabled(tool)
        icon = "[green]\u2713[/green]" if enabled else "[dim]-[/dim]"
        console.print(f"  {icon} {tool}")

    if config.url:
        console.print(f"\nURL tools ({len(stack_info.get('url_tools', []))}):")
        for tool in sorted(stack_info.get("url_tools", [])):
            console.print(f"  [green]\u2713[/green] {tool}")


def _render_output(result, config, console):
    """Dispatch to the appropriate reporter."""
    from vibedeploy.reporters.table import TableReporter
    from vibedeploy.reporters.json_reporter import JsonReporter
    from vibedeploy.reporters.html import HtmlReporter
    from vibedeploy.reporters.markdown import MarkdownReporter

    reporters = {
        "table": TableReporter,
        "json": JsonReporter,
        "html": HtmlReporter,
        "md": MarkdownReporter,
    }

    # Checklist is special
    if config.output == "checklist":
        from vibedeploy.checklist import render_checklist
        content = render_checklist(result)
        if config.output_file:
            with open(config.output_file, "w") as f:
                f.write(content)
            if not config.quiet:
                console.print(f"Checklist written to {config.output_file}")
        else:
            console.print(content)
        return

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
        if f.blocks_deploy or f.severity >= Severity.HIGH:
            line_part = f",line={f.line}" if f.line else ""
            print(f"::error file={f.file}{line_part}::[{f.tool}] {f.message}")


# ── Install command ──

@main.command()
@click.option("--update", is_flag=True, help="Upgrade all tools to latest")
@click.option("--check", is_flag=True, help="Check tool status without installing")
def install(update, check):
    """Download and manage all deploy readiness tools."""
    console = Console()

    if check:
        from vibedeploy.installer import check_all

        results = check_all()
        from rich.table import Table

        table = Table(title="vibedeploy tool status")
        table.add_column("Tool", style="bold")
        table.add_column("Kind")
        table.add_column("Status")
        table.add_column("Version")
        table.add_column("Notes")

        for info in results:
            status = "[green]\u2713[/green]" if info["installed"] else "[red]\u2717[/red]"
            notes_parts = []
            if info.get("skip_reason"):
                notes_parts.append(info["skip_reason"])
            if info.get("requires_url"):
                notes_parts.append("--url")
            if info.get("requires_docker"):
                notes_parts.append("docker")
            if info.get("requires_k8s"):
                notes_parts.append("k8s")
            if info.get("requires_cloud"):
                notes_parts.append("cloud")

            table.add_row(
                info["name"],
                info["kind"],
                status,
                info.get("version") or "-",
                ", ".join(notes_parts) if notes_parts else "",
            )

        console.print(table)
        return

    console.print("[bold]vibedeploy install[/bold] \u2014 setting up deploy readiness tools\n")

    def on_progress(name, success, msg):
        icon = "[green]\u2713[/green]" if success else "[red]\u2717[/red]"
        console.print(f"  {icon} {name}: {msg}")

    from vibedeploy.installer import install_all

    results = asyncio.run(install_all(upgrade=update, callback=on_progress))

    ok = sum(1 for _, s, _ in results if s)
    fail = sum(1 for _, s, _ in results if not s)
    console.print(f"\n[bold]{ok} installed, {fail} failed[/bold]")


# ── Report command ──

@main.command()
@click.option("--last", is_flag=True, help="Re-render last scan results")
@click.option("--trend", is_flag=True, help="Show readiness score over time")
@click.option("--target", default=".", help="Project directory")
@click.option(
    "--output",
    "output_format",
    type=click.Choice(["table", "json", "html", "md", "checklist"], case_sensitive=False),
    default="table",
)
@click.option("--output-file", default=None)
def report(last, trend, target, output_format, output_file):
    """Re-render scan results without re-scanning."""
    console = Console()

    if trend:
        from vibedeploy.history import load_trend

        entries = load_trend(target)
        if not entries:
            console.print("[yellow]No scan history found.[/yellow]")
            return

        from rich.table import Table

        table = Table(title="vibedeploy deploy readiness trend")
        table.add_column("Date")
        table.add_column("Score", style="bold")
        table.add_column("Ready")
        table.add_column("Blockers")
        table.add_column("Critical", style="red")
        table.add_column("High", style="yellow")
        table.add_column("Medium")
        table.add_column("Exit")

        for entry in entries:
            counts = entry.get("severity_counts", {})
            ready = "\u2713" if entry.get("deploy_ready") else "\u2717"
            ready_style = "green" if entry.get("deploy_ready") else "red"
            table.add_row(
                str(entry.get("timestamp", "?"))[:19],
                str(entry.get("readiness_score", "?")),
                f"[{ready_style}]{ready}[/{ready_style}]",
                str(entry.get("blocker_count", 0)),
                str(counts.get("CRITICAL", 0)),
                str(counts.get("HIGH", 0)),
                str(counts.get("MEDIUM", 0)),
                str(entry.get("exit_code", "?")),
            )

        console.print(table)
        return

    if last:
        from vibedeploy.history import load_last
        from vibedeploy.models import ScanResult, Finding, ToolResult, ToolStatus, Effort

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
            stack_info=data.get("stack_info", {}),
        )

        for f_data in data.get("findings", []):
            finding = Finding(
                tool=f_data.get("tool", ""),
                severity=Severity(f_data.get("severity", "INFO")),
                category=Category(f_data.get("category", "GENERAL")),
                file=f_data.get("file", ""),
                rule_id=f_data.get("rule_id", ""),
                rule_name=f_data.get("rule_name", ""),
                message=f_data.get("message", ""),
                line=f_data.get("line"),
                fix_hint=f_data.get("fix_hint"),
                fix_command=f_data.get("fix_command"),
                docs_url=f_data.get("docs_url"),
                blocks_deploy=f_data.get("blocks_deploy", False),
                effort=Effort(f_data.get("effort", "UNKNOWN")),
                cve=f_data.get("cve"),
                cvss=f_data.get("cvss"),
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

    console.print("Specify --last or --trend. Run vibedeploy report --help for details.")


# ── Checklist command ──

@main.command()
@click.option("--last", is_flag=True, help="Generate checklist from last scan")
@click.option("--target", default=".", help="Project directory")
@click.option("--output-file", default=None, help="Write checklist to file")
def checklist(last, target, output_file):
    """Generate a pre-deploy checklist from scan results."""
    console = Console()

    if not last:
        console.print("Specify --last. Run vibedeploy checklist --help for details.")
        return

    from vibedeploy.history import load_last
    from vibedeploy.models import ScanResult, Finding, ToolResult, ToolStatus, Effort

    data = load_last(target)
    if not data:
        console.print("[yellow]No previous scan found.[/yellow]")
        return

    result = ScanResult(
        target=data.get("target", target),
        timestamp=data.get("timestamp", ""),
    )
    for f_data in data.get("findings", []):
        result.deduplicated_findings.append(Finding(
            tool=f_data.get("tool", ""),
            severity=Severity(f_data.get("severity", "INFO")),
            category=Category(f_data.get("category", "GENERAL")),
            file=f_data.get("file", ""),
            rule_id=f_data.get("rule_id", ""),
            rule_name=f_data.get("rule_name", ""),
            message=f_data.get("message", ""),
            line=f_data.get("line"),
            fix_hint=f_data.get("fix_hint"),
            fix_command=f_data.get("fix_command"),
            blocks_deploy=f_data.get("blocks_deploy", False),
            effort=Effort(f_data.get("effort", "UNKNOWN")),
        ))

    from vibedeploy.checklist import render_checklist
    content = render_checklist(result)

    if output_file:
        with open(output_file, "w") as f:
            f.write(content)
        console.print(f"Checklist written to {output_file}")
    else:
        console.print(content)


# ── Fix command ──

@main.command()
@click.option("--last", is_flag=True, help="Generate fixes from last scan")
@click.option("--dry-run", is_flag=True, help="Show fix commands without executing")
@click.option("--target", default=".", help="Project directory")
def fix(last, dry_run, target):
    """Show or apply fix commands for findings."""
    console = Console()

    if not last:
        console.print("Specify --last. Run vibedeploy fix --help for details.")
        return

    from vibedeploy.history import load_last
    from vibedeploy.models import Finding, Effort

    data = load_last(target)
    if not data:
        console.print("[yellow]No previous scan found.[/yellow]")
        return

    findings = []
    for f_data in data.get("findings", []):
        findings.append(Finding(
            tool=f_data.get("tool", ""),
            severity=Severity(f_data.get("severity", "INFO")),
            category=Category(f_data.get("category", "GENERAL")),
            file=f_data.get("file", ""),
            rule_id=f_data.get("rule_id", ""),
            rule_name=f_data.get("rule_name", ""),
            message=f_data.get("message", ""),
            fix_hint=f_data.get("fix_hint"),
            fix_command=f_data.get("fix_command"),
            blocks_deploy=f_data.get("blocks_deploy", False),
            effort=Effort(f_data.get("effort", "UNKNOWN")),
        ))

    from vibedeploy.fix_generator import generate_fixes

    fixes = generate_fixes(findings)
    if not fixes:
        console.print("[green]No fixable findings.[/green]")
        return

    console.print(f"[bold]Fix Plan ({len(fixes)} actions)[/bold]\n")

    for fix_item in fixes:
        priority = fix_item["priority"]
        blocks = "[red]BLOCKER[/red]" if fix_item["blocks_deploy"] else ""
        sev = fix_item["severity"]

        console.print(f"  [bold]#{priority}[/bold] [{sev}] {fix_item['message'][:80]} {blocks}")
        console.print(f"       [dim]{fix_item['file']}[/dim]")

        if fix_item["fix_hint"]:
            console.print(f"       [italic]{fix_item['fix_hint']}[/italic]")

        if fix_item["fix_command"]:
            prefix = "[dim]would run:[/dim]" if dry_run else "[dim]$[/dim]"
            console.print(f"       {prefix} [bold]{fix_item['fix_command']}[/bold]")

        console.print()

    if dry_run:
        console.print("[dim]Dry run — no commands were executed.[/dim]")


# ── Diff command ──

@main.command()
@click.option("--target", default=".", help="Project directory")
def diff(target):
    """Compare current scan with previous scan."""
    console = Console()

    from vibedeploy.history import load_trend

    entries = load_trend(target, limit=2)
    if len(entries) < 2:
        console.print("[yellow]Need at least 2 scans to diff. Run vibedeploy scan first.[/yellow]")
        return

    prev = entries[0]
    curr = entries[1]

    console.print("[bold]vibedeploy diff[/bold]\n")
    console.print(f"  Previous: {prev.get('timestamp', '?')[:19]}")
    console.print(f"  Current:  {curr.get('timestamp', '?')[:19]}")
    console.print()

    prev_score = prev.get("readiness_score", 0)
    curr_score = curr.get("readiness_score", 0)
    delta = curr_score - prev_score

    delta_style = "green" if delta > 0 else "red" if delta < 0 else "dim"
    delta_str = f"+{delta}" if delta > 0 else str(delta)

    console.print(f"  Score: {prev_score} \u2192 {curr_score} ([{delta_style}]{delta_str}[/{delta_style}])")

    prev_blockers = prev.get("blocker_count", 0)
    curr_blockers = curr.get("blocker_count", 0)
    blocker_delta = curr_blockers - prev_blockers
    b_style = "green" if blocker_delta < 0 else "red" if blocker_delta > 0 else "dim"
    b_str = f"+{blocker_delta}" if blocker_delta > 0 else str(blocker_delta)
    console.print(f"  Blockers: {prev_blockers} \u2192 {curr_blockers} ([{b_style}]{b_str}[/{b_style}])")

    # Severity comparison
    for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        p = prev.get("severity_counts", {}).get(sev, 0)
        c = curr.get("severity_counts", {}).get(sev, 0)
        if p == 0 and c == 0:
            continue
        d = c - p
        d_style = "green" if d < 0 else "red" if d > 0 else "dim"
        d_str = f"+{d}" if d > 0 else str(d)
        console.print(f"  {sev}: {p} \u2192 {c} ([{d_style}]{d_str}[/{d_style}])")


if __name__ == "__main__":
    main()
