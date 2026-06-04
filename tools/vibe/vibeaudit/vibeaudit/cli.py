"""Click CLI for vibeaudit."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import click
from rich.console import Console

from vibeaudit.config import VibeauditConfig, load_config
from vibeaudit.models import Severity, VulnClass

console = Console()

# Exit codes
EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_PROVIDER_ERROR = 2
EXIT_NOT_CONFIGURED = 3
EXIT_BUDGET_EXCEEDED = 4


def _resolve_config(ctx: click.Context) -> VibeauditConfig:
    """Build config from file + CLI flags."""
    overrides: dict = {}
    params = ctx.params

    if params.get("provider"):
        overrides["provider.name"] = params["provider"]
    if params.get("model"):
        overrides["provider.model"] = params["model"]
    if params.get("classes"):
        overrides["scan.vuln_classes"] = params["classes"].split(",")
    if params.get("workers"):
        overrides["scan.concurrency"] = params["workers"]
    if params.get("budget"):
        overrides["cost.hard_cap_usd"] = params["budget"]
    if params.get("output"):
        overrides["output.format"] = params["output"]
    if params.get("output_file"):
        overrides["output.output_file"] = params["output_file"]
    if params.get("deep"):
        overrides["agent.enabled"] = True

    return load_config(
        config_path=params.get("config"),
        cli_overrides=overrides,
    )


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """vibeaudit — AI-powered security scanner for Claude Code.

    Run 'vibeaudit scan [TARGET_DIR]' to extract code regions for analysis.
    """
    ctx.ensure_object(dict)

    if ctx.invoked_subcommand is not None:
        return

    # Default command is scan with cwd
    ctx.invoke(scan)


@cli.command()
@click.argument("target_dir", required=False, default=None)
@click.option("--provider", "-p", type=click.Choice(["anthropic", "openai", "azure", "ollama", "groq"]),
              help="LLM provider (opt-in: sends code to an LLM API)")
@click.option("--model", "-m", help="Model name override (requires --provider)")
@click.option("--classes", "-c", help="Comma-separated vuln classes to scan")
@click.option("--skip", help="Comma-separated vuln classes to skip")
@click.option("--file", "scan_file", help="Scan a specific file only")
@click.option("--confidence", type=click.Choice(["high", "medium", "low"]), help="Minimum confidence to report")
@click.option("--fail-on", type=click.Choice(["critical", "high", "medium", "low", "info"]),
              help="Fail if findings >= this severity")
@click.option("--output", "-o", type=click.Choice(["json", "table", "html", "markdown", "sarif", "quiet"]),
              default="json", help="Output format (default: json for extraction)")
@click.option("--output-file", "-f", help="Write output to file")
@click.option("--config", help="Path to .vibeaudit.yml")
@click.option("--ship-safe", is_flag=True, help="CI mode: fail on critical/high")
@click.option("--deep", is_flag=True, help="Enable agentic deep scan (requires --provider)")
@click.option("--budget", type=float, help="Max spend in USD (requires --provider)")
@click.option("--since", help="Git ref — only scan files changed since")
@click.option("--context", type=int, help="Extra context lines around snippets")
@click.option("--workers", "-w", type=int, help="Concurrent workers")
@click.option("--quiet", "-q", is_flag=True, help="Suppress progress output")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--dry-run", is_flag=True, help="Show what would be scanned without doing extraction")
@click.pass_context
def scan(ctx: click.Context, target_dir: str | None, **kwargs: object) -> None:
    """Scan a codebase for security vulnerabilities.

    Default mode: extracts code regions and outputs structured JSON.
    Claude Code reads this output, analyses each region, and feeds
    findings back via 'vibeaudit report'.

    With --provider: sends extracted code to an LLM API for analysis
    (requires the provider's API key in the environment).
    """
    if kwargs.get("ship_safe") and not kwargs.get("fail_on"):
        kwargs["fail_on"] = "high"

    config = _resolve_config(ctx)

    if target_dir:
        config.scan.target_dir = target_dir
    elif not config.scan.target_dir or config.scan.target_dir == ".":
        config.scan.target_dir = str(Path.cwd())

    # Apply --skip
    skip_raw = kwargs.get("skip")
    if skip_raw and isinstance(skip_raw, str):
        skip_classes = set(skip_raw.split(","))
        config.scan.vuln_classes = [c for c in config.scan.vuln_classes if c not in skip_classes]

    # Apply --file
    scan_file = kwargs.get("scan_file")
    if scan_file and isinstance(scan_file, str):
        config.scan.include = [scan_file]

    dry_run = bool(kwargs.get("dry_run"))
    quiet = bool(kwargs.get("quiet"))
    provider_name = kwargs.get("provider")
    use_provider = provider_name is not None

    from vibeaudit.scanner import Scanner
    scanner = Scanner(config, console=console, quiet=quiet)

    if dry_run:
        # Just show counts, no extraction
        result = asyncio.run(scanner.dry_run(since=kwargs.get("since")))  # type: ignore[arg-type]
        sys.exit(EXIT_CLEAN)

    if use_provider:
        # ── Provider-based LLM scan ──────────────────────────────────
        if config.provider.name not in ("ollama",) and not config.provider.api_key:
            console.print(f"[red]No API key found for provider '{config.provider.name}'.[/red]")
            console.print("Set the appropriate env var (e.g. ANTHROPIC_API_KEY).")
            sys.exit(EXIT_NOT_CONFIGURED)

        try:
            from vibeaudit.cost_tracker import BudgetExceededError
            start = time.time()
            result = asyncio.run(scanner.run(since=kwargs.get("since")))  # type: ignore[arg-type]
            result.duration_seconds = time.time() - start
        except BudgetExceededError as e:
            console.print(f"[yellow]Budget exceeded: {e}[/yellow]")
            sys.exit(EXIT_BUDGET_EXCEEDED)
        except Exception as e:
            console.print(f"[red]Provider error: {e}[/red]")
            if kwargs.get("verbose"):
                console.print_exception()
            sys.exit(EXIT_PROVIDER_ERROR)

        # Filter by confidence
        confidence_filter = kwargs.get("confidence")
        if confidence_filter and isinstance(confidence_filter, str):
            from vibeaudit.models import Confidence
            min_conf = Confidence(confidence_filter)
            conf_rank = {"high": 0, "medium": 1, "low": 2}
            min_rank = conf_rank[min_conf.value]
            result.findings = [f for f in result.findings if conf_rank.get(f.confidence.value, 2) <= min_rank]

        # Report
        from vibeaudit.reporters import create_reporter
        reporter = create_reporter(config.output.format)
        output_path = Path(config.output.output_file) if config.output.output_file else None
        reporter.report(result, console, output_path)

        # Store in history
        from vibeaudit.history import store_scan
        store_scan(result, Path(config.scan.target_dir))

        # Exit code
        fail_on = kwargs.get("fail_on")
        if fail_on and isinstance(fail_on, str):
            threshold = Severity(fail_on)
            for f in result.findings:
                if f.severity.rank <= threshold.rank:
                    sys.exit(EXIT_FINDINGS)

        sys.exit(EXIT_CLEAN)

    # ── Default: extraction-only mode ────────────────────────────────
    start = time.time()
    extraction_data = scanner.extract_all(since=kwargs.get("since"))  # type: ignore[arg-type]
    extraction_data["duration_seconds"] = time.time() - start

    # Format extraction output
    output_format = kwargs.get("output")
    if output_format == "markdown":
        lines = ["# Extraction Results", ""]
        extractions = extraction_data.get("extractions", [])
        if extractions:
            lines.append("| File | Line | Finding Type | Description |")
            lines.append("|------|------|-------------|-------------|")
            for ext in extractions:
                file_path = ext.get("file_path", "")
                vuln_class = ext.get("vuln_class", "")
                for snippet in ext.get("snippets", []):
                    line_num = snippet.get("start_line", "")
                    # Use first line of snippet content as description
                    content = snippet.get("content", "").split("\n")[0].strip()
                    # Escape pipes in content for markdown table
                    content = content.replace("|", "\\|")
                    lines.append(f"| {file_path} | {line_num} | {vuln_class} | {content} |")
        else:
            lines.append("No findings extracted.")
        lines.append("")
        lines.append(f"_Scanned in {extraction_data.get('duration_seconds', 0):.1f}s_")
        formatted = "\n".join(lines)
    else:
        formatted = json.dumps(extraction_data, indent=2)

    # Write output
    output_file = kwargs.get("output_file")
    if output_file and isinstance(output_file, str):
        Path(output_file).write_text(formatted)
        if not quiet:
            console.print(f"[green]Wrote extraction to {output_file}[/green]")
    else:
        # Output to stdout
        click.echo(formatted)

    sys.exit(EXIT_CLEAN)


@cli.command()
def install() -> None:
    """Configure vibeaudit providers interactively."""
    from vibeaudit.config import DEFAULT_CONFIG_FILE
    from rich.prompt import Prompt

    console.print("[bold]vibeaudit setup[/bold]\n")

    provider = Prompt.ask(
        "LLM provider",
        choices=["anthropic", "openai", "azure", "ollama", "groq"],
        default="anthropic",
    )

    config_data: dict = {"provider": {"name": provider}}

    if provider != "ollama":
        env_var_map = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "azure": "AZURE_OPENAI_KEY",
            "groq": "GROQ_API_KEY",
        }
        env_var = env_var_map[provider]
        console.print(f"\nSet [bold]{env_var}[/bold] in your environment.")
        console.print(f"  export {env_var}=sk-...")
    else:
        console.print("\nEnsure Ollama is running at http://localhost:11434")

    path = Path(DEFAULT_CONFIG_FILE)
    if not path.exists():
        import yaml

        with open(DEFAULT_CONFIG_FILE, "w") as f:
            yaml.dump(config_data, f, default_flow_style=False)
        console.print(f"\nWrote [bold]{DEFAULT_CONFIG_FILE}[/bold]")
    else:
        console.print(f"\n[dim]{DEFAULT_CONFIG_FILE} already exists, not overwriting.[/dim]")

    console.print("\n[green]Ready![/green] Run [bold]vibeaudit scan .[/bold] to start.")


@cli.group()
def baseline() -> None:
    """Manage scan baselines."""


@baseline.command("create")
@click.option("--config", help="Path to .vibeaudit.yml")
def baseline_create(config: str | None) -> None:
    """Create a baseline from the last scan."""
    from vibeaudit.baseline import create_baseline
    from vibeaudit.history import get_last_scan

    result = get_last_scan(Path.cwd())
    if result is None:
        console.print("[red]No scan history found. Run a scan first.[/red]")
        sys.exit(1)

    path = create_baseline(result, Path.cwd())
    console.print(f"[green]Baseline created:[/green] {path} ({len(result.findings)} findings)")


@baseline.command("update")
@click.option("--config", help="Path to .vibeaudit.yml")
def baseline_update(config: str | None) -> None:
    """Update the baseline with findings from the last scan."""
    from vibeaudit.baseline import update_baseline
    from vibeaudit.history import get_last_scan

    result = get_last_scan(Path.cwd())
    if result is None:
        console.print("[red]No scan history found. Run a scan first.[/red]")
        sys.exit(1)

    path = update_baseline(result, Path.cwd())
    console.print(f"[green]Baseline updated:[/green] {path}")


@cli.command()
@click.argument("finding_id")
def verify(finding_id: str) -> None:
    """Re-analyse a specific finding."""
    from vibeaudit.history import get_last_scan

    result = get_last_scan(Path.cwd())
    if result is None:
        console.print("[red]No scan history found.[/red]")
        sys.exit(1)

    finding = next((f for f in result.findings if f.id == finding_id), None)
    if not finding:
        console.print(f"[red]Finding {finding_id} not found.[/red]")
        sys.exit(1)

    console.print(f"[bold]{finding.title}[/bold]")
    console.print(f"Severity: {finding.severity.value} | Confidence: {finding.confidence.value}")
    console.print(f"Class: {finding.vuln_class.value}")
    console.print(f"\n[bold]Description:[/bold]\n{finding.description}")
    console.print(f"\n[bold]Attack Scenario:[/bold]\n{finding.attack_scenario}")
    console.print(f"\n[bold]Remediation:[/bold]\n{finding.remediation}")
    if finding.reasoning:
        console.print(f"\n[bold]LLM Reasoning:[/bold]\n{finding.reasoning}")


@cli.command("false-positive")
@click.argument("finding_id")
@click.option("--reason", "-r", help="Reason for marking as false positive")
def false_positive(finding_id: str, reason: str | None) -> None:
    """Mark a finding as a false positive."""
    from vibeaudit.feedback import record_feedback

    record_feedback(finding_id, true_positive=False, reason=reason or "", base_dir=Path.cwd())
    console.print(f"[green]Marked {finding_id} as false positive.[/green]")


@cli.command()
@click.option("--last", is_flag=True, help="Re-render the last scan")
@click.option("--findings-file", help="Path to findings JSON file (from Claude Code analysis)")
@click.option("--output", "-o", type=click.Choice(["table", "json", "html", "markdown", "sarif"]), default="table")
@click.option("--output-file", "-f", help="Write output to file")
def report(last: bool, findings_file: str | None, output: str, output_file: str | None) -> None:
    """Generate a report from findings.

    Use --findings-file to render a report from a findings JSON file
    (produced by Claude Code analysis of extraction output).

    Use --last to re-render the most recent provider-based scan.
    """
    from vibeaudit.reporters import create_reporter

    if findings_file:
        result = _load_findings_file(Path(findings_file))
    elif last:
        from vibeaudit.history import get_last_scan
        result = get_last_scan(Path.cwd())
        if result is None:
            console.print("[red]No scan history found.[/red]")
            sys.exit(1)
    else:
        console.print("[red]Use --findings-file <path> or --last.[/red]")
        sys.exit(1)

    reporter = create_reporter(output)
    output_path = Path(output_file) if output_file else None
    reporter.report(result, console, output_path)


def _load_findings_file(path: Path) -> "ScanResult":
    """Load a findings JSON file into a ScanResult."""
    from vibeaudit.models import (
        CodeSnippet, Confidence, Finding, ScanResult, Severity, VulnClass,
    )

    data = json.loads(path.read_text())
    if isinstance(data, list):
        findings_data = data
        data = {}
    else:
        findings_data = data.get("findings", [])

    findings: list[Finding] = []
    for f in findings_data:
        snippets = []
        # Accept snippets array or file_path + start_line + end_line
        if "snippets" in f:
            for s in f["snippets"]:
                snippets.append(CodeSnippet(
                    file_path=s.get("file_path", ""),
                    start_line=s.get("start_line", 0),
                    end_line=s.get("end_line", 0),
                    content=s.get("content", ""),
                    language=s.get("language", "unknown"),
                ))
        elif "file_path" in f:
            snippets.append(CodeSnippet(
                file_path=f["file_path"],
                start_line=f.get("start_line", 0),
                end_line=f.get("end_line", 0),
                content=f.get("code", ""),
                language=f.get("language", "unknown"),
            ))

        findings.append(Finding(
            vuln_class=VulnClass(f["vuln_class"]),
            severity=Severity(f.get("severity", "medium").lower()),
            confidence=Confidence(f.get("confidence", "medium").lower()),
            title=f.get("title", ""),
            description=f.get("description", ""),
            attack_scenario=f.get("attack_scenario", ""),
            impact=f.get("impact", ""),
            remediation=f.get("remediation", ""),
            fix_example=f.get("fix_example", ""),
            snippets=snippets,
            cwe_id=f.get("cwe_id", ""),
            owasp_category=f.get("owasp_category", ""),
            reasoning=f.get("reasoning", ""),
            source="claude_code",
        ))

    return ScanResult(
        findings=findings,
        scanned_files=data.get("scanned_files", 0),
        scanned_classes=data.get("scanned_classes", []),
        provider=data.get("provider", "claude_code"),
        model=data.get("model", ""),
    )


@cli.command()
@click.argument("git_ref")
@click.option("--output", "-o", type=click.Choice(["table", "json", "html", "markdown", "sarif"]), default="table")
def diff(git_ref: str, output: str) -> None:
    """Show new findings since a git ref or previous scan."""
    from vibeaudit.history import get_last_scan, get_scan_by_ref
    from vibeaudit.reporters import create_reporter
    from vibeaudit.models import ScanResult

    current = get_last_scan(Path.cwd())
    if current is None:
        console.print("[red]No scan history found.[/red]")
        sys.exit(1)

    previous = get_scan_by_ref(git_ref, Path.cwd())
    if previous is None:
        console.print(f"[red]No scan found for ref '{git_ref}'.[/red]")
        sys.exit(1)

    old_ids = {f.id for f in previous.findings}
    new_findings = [f for f in current.findings if f.id not in old_ids]

    diff_result = ScanResult(
        findings=new_findings,
        scanned_files=current.scanned_files,
        scanned_classes=current.scanned_classes,
        provider=current.provider,
        model=current.model,
    )

    reporter = create_reporter(output)
    reporter.report(diff_result, console, None)


@cli.command()
@click.argument("finding_id")
def explain(finding_id: str) -> None:
    """Detailed explanation and PoC for a finding."""
    from vibeaudit.history import get_last_scan

    result = get_last_scan(Path.cwd())
    if result is None:
        console.print("[red]No scan history found.[/red]")
        sys.exit(1)

    finding = next((f for f in result.findings if f.id == finding_id), None)
    if not finding:
        console.print(f"[red]Finding {finding_id} not found.[/red]")
        sys.exit(1)

    console.print(f"\n[bold red]{'━' * 60}[/bold red]")
    console.print(f"[bold]{finding.title}[/bold] ({finding.id})")
    console.print(f"[bold red]{'━' * 60}[/bold red]\n")

    console.print(f"[bold]Vulnerability Class:[/bold] {finding.vuln_class.value}")
    console.print(f"[bold]Severity:[/bold] {finding.severity.value}")
    console.print(f"[bold]Confidence:[/bold] {finding.confidence.value}")
    console.print(f"[bold]CWE:[/bold] {finding.cwe_id}")
    console.print(f"[bold]OWASP:[/bold] {finding.owasp_category}")

    console.print(f"\n[bold]Description:[/bold]\n{finding.description}")
    console.print(f"\n[bold]Attack Scenario:[/bold]\n{finding.attack_scenario}")
    console.print(f"\n[bold]Impact:[/bold]\n{finding.impact}")
    console.print(f"\n[bold]Remediation:[/bold]\n{finding.remediation}")

    if finding.fix_example:
        console.print(f"\n[bold]Fix Example:[/bold]\n```\n{finding.fix_example}\n```")

    if finding.snippets:
        console.print(f"\n[bold]Affected Code:[/bold]")
        for s in finding.snippets:
            console.print(f"  {s.file_path}:{s.start_line}-{s.end_line}")
            for i, line in enumerate(s.content.split("\n"), s.start_line):
                console.print(f"    {i:4d} │ {line}")

    if finding.reasoning:
        console.print(f"\n[bold]LLM Reasoning:[/bold]\n{finding.reasoning}")


@cli.command()
@click.argument("files", nargs=-1, required=True)
@click.option("--output", "-o", type=click.Choice(["table", "json", "html", "markdown", "sarif"]), default="table")
@click.option("--output-file", "-f", help="Write merged output to file")
def merge(files: tuple[str, ...], output: str, output_file: str | None) -> None:
    """Merge vibeaudit JSON + SARIF files into a unified report."""
    from vibeaudit.reporters import create_reporter
    from vibeaudit.vibereport import merge_reports

    result = merge_reports([Path(f) for f in files])
    reporter = create_reporter(output)
    output_path = Path(output_file) if output_file else None
    reporter.report(result, console, output_path)


if __name__ == "__main__":
    cli()
