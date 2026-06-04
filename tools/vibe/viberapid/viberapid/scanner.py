"""Orchestrator — runs all tools in parallel, deduplicates, computes quick wins, checks budget."""

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

from viberapid.config import Config, detect_stack
from viberapid.models import (
    BudgetResult,
    Finding,
    ScanResult,
    Severity,
    ToolResult,
    ToolStatus,
)
from viberapid.runners.base import AsyncToolRunner

# ---------------------------------------------------------------------------
# Runner imports — files may not exist yet; that's fine, they'll be created
# in parallel. ImportError handling below ensures graceful degradation.
# ---------------------------------------------------------------------------
_RUNNER_CLASSES: list[type[AsyncToolRunner]] = []


def _try_import(module: str, cls_name: str) -> type[AsyncToolRunner] | None:
    """Attempt to import a runner class, returning None on failure."""
    try:
        mod = __import__(module, fromlist=[cls_name])
        return getattr(mod, cls_name, None)
    except (ImportError, AttributeError):
        return None


_RUNNER_SPECS: list[tuple[str, str]] = [
    # Bundle & JS
    ("viberapid.runners.depcheck", "DepcheckRunner"),
    ("viberapid.runners.knip", "KnipRunner"),
    ("viberapid.runners.jscpd", "JscpdRunner"),
    ("viberapid.runners.bundlephobia", "BundlephobiaRunner"),
    ("viberapid.runners.cost_of_modules", "CostOfModulesRunner"),
    ("viberapid.runners.size_limit", "SizeLimitRunner"),
    ("viberapid.runners.bundle_analyzer", "BundleAnalyzerRunner"),
    ("viberapid.runners.source_map_explorer", "SourceMapExplorerRunner"),
    ("viberapid.runners.bundlewatch", "BundlewatchRunner"),
    ("viberapid.runners.esbuild_bench", "EsbuildBenchRunner"),
    ("viberapid.runners.webpack_deadcode", "WebpackDeadcodeRunner"),
    ("viberapid.runners.npm_check", "NpmCheckRunner"),
    ("viberapid.runners.npm_check_updates", "NpmCheckUpdatesRunner"),
    ("viberapid.runners.duplicate_packages", "DuplicatePackagesRunner"),
    # CSS
    ("viberapid.runners.purgecss", "PurgecssRunner"),
    ("viberapid.runners.cssnano", "CssnanoRunner"),
    ("viberapid.runners.parker", "ParkerRunner"),
    ("viberapid.runners.stylestats", "StylestatsRunner"),
    ("viberapid.runners.uncss", "UncssRunner"),
    ("viberapid.runners.stylelint_perf", "StylelintPerfRunner"),
    # Fonts
    ("viberapid.runners.glyphhanger", "GlyphhangerRunner"),
    ("viberapid.runners.fonttools_runner", "FonttoolsRunner"),
    # Images
    ("viberapid.runners.svgo", "SvgoRunner"),
    ("viberapid.runners.imagemin", "ImageminRunner"),
    ("viberapid.runners.sharp_check", "SharpCheckRunner"),
    # Compression
    ("viberapid.runners.gzip_size", "GzipSizeRunner"),
    ("viberapid.runners.brotli_size", "BrotliSizeRunner"),
    ("viberapid.runners.zopfli", "ZopfliRunner"),
    # HTTP & Network
    ("viberapid.runners.lighthouse", "LighthouseRunner"),
    ("viberapid.runners.webhint", "WebhintRunner"),
    ("viberapid.runners.sitespeed", "SitespeedRunner"),
    ("viberapid.runners.psi", "PSIRunner"),
    ("viberapid.runners.h2spec", "H2specRunner"),
    ("viberapid.runners.yellowlab", "YellowLabRunner"),
    ("viberapid.runners.hstspreload", "HSTSPreloadRunner"),
    # Load Testing
    ("viberapid.runners.k6", "K6Runner"),
    ("viberapid.runners.artillery", "ArtilleryRunner"),
    ("viberapid.runners.autocannon", "AutocannonRunner"),
    ("viberapid.runners.wrk", "WrkRunner"),
    ("viberapid.runners.vegeta", "VegetaRunner"),
    ("viberapid.runners.bombardier", "BombardierRunner"),
    ("viberapid.runners.hyperfine", "HyperfineRunner"),
    ("viberapid.runners.locust", "LocustRunner"),
    # Database
    ("viberapid.runners.sqlfluff", "SqlfluffRunner"),
    ("viberapid.runners.pghero", "PgheroRunner"),
    ("viberapid.runners.pgbadger", "PgbadgerRunner"),
    ("viberapid.runners.pt_query_digest", "PtQueryDigestRunner"),
    ("viberapid.runners.django_check", "DjangoCheckRunner"),
    ("viberapid.runners.prisma_inspector", "PrismaInspectorRunner"),
    # Python Runtime
    ("viberapid.runners.scalene", "ScaleneRunner"),
    ("viberapid.runners.pyinstrument", "PyinstrumentRunner"),
    ("viberapid.runners.py_spy", "PySpyRunner"),
    ("viberapid.runners.memray", "MemrayRunner"),
    ("viberapid.runners.fil", "FilRunner"),
    ("viberapid.runners.austin", "AustinRunner"),
    ("viberapid.runners.speedscope", "SpeedscopeRunner"),
    # Node Runtime
    ("viberapid.runners.clinic", "ClinicRunner"),
    ("viberapid.runners.zero_x", "ZeroXRunner"),
    ("viberapid.runners.node_prof", "NodeProfRunner"),
    # React
    ("viberapid.runners.million_lint", "MillionLintRunner"),
    ("viberapid.runners.react_scan", "ReactScanRunner"),
    ("viberapid.runners.why_did_you_render", "WhyDidYouRenderRunner"),
    # Dependencies
    ("viberapid.runners.pipdeptree", "PipdeptreeRunner"),
    ("viberapid.runners.deptry", "DeptryRunner"),
    # AST (custom — no external tool)
    ("viberapid.runners.ast_analyser", "AstAnalyserRunner"),
]


def _load_all_runners() -> list[type[AsyncToolRunner]]:
    """Import all runner classes, skipping those that fail."""
    runners = []
    for module, cls_name in _RUNNER_SPECS:
        cls = _try_import(module, cls_name)
        if cls is not None:
            runners.append(cls)
    return runners


ALL_RUNNERS: list[type[AsyncToolRunner]] = _load_all_runners()


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------
EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_TOOL_ERROR = 2
EXIT_TOOLS_MISSING = 3
EXIT_ALL_CRITICAL_BUDGET = 4


# ---------------------------------------------------------------------------
# Stack filtering
# ---------------------------------------------------------------------------
def _runner_matches_stack(runner_cls: type[AsyncToolRunner], stack: str) -> bool:
    """Return True if a runner is appropriate for the detected stack."""
    # Fullstack — everything runs
    if stack == "fullstack":
        return True

    requires_node = getattr(runner_cls, "requires_node", False)
    requires_python = getattr(runner_cls, "requires_python", False)

    # If runner has no stack requirement, it runs everywhere
    if not requires_node and not requires_python:
        return True

    if stack == "node":
        return not requires_python
    if stack == "python":
        return not requires_node

    return True


# ---------------------------------------------------------------------------
# Progress display
# ---------------------------------------------------------------------------
def _build_status_table(
    statuses: dict[str, str],
    title: str = "viberapid",
) -> Table:
    """Build a Rich table showing runner statuses."""
    table = Table(title=title, show_header=True, header_style="bold")
    table.add_column("Tool", style="cyan", min_width=20)
    table.add_column("Status", min_width=12)
    table.add_column("Findings", justify="right", min_width=8)

    for tool_name, status_str in statuses.items():
        # Parse status string: "running", "done:5", "skipped:reason", "error:msg"
        if status_str.startswith("done:"):
            parts = status_str.split(":", 1)
            count = parts[1] if len(parts) > 1 else "0"
            status_text = Text("done", style="green")
            count_text = Text(count, style="yellow" if int(count) > 0 else "dim")
        elif status_str.startswith("error:"):
            msg = status_str.split(":", 1)[1] if ":" in status_str else ""
            status_text = Text("error", style="red")
            count_text = Text(msg[:30], style="dim red")
        elif status_str.startswith("skipped:"):
            reason = status_str.split(":", 1)[1] if ":" in status_str else ""
            status_text = Text("skipped", style="dim")
            count_text = Text(reason[:30], style="dim")
        elif status_str == "running":
            status_text = Text("running...", style="bold yellow")
            count_text = Text("-", style="dim")
        elif status_str == "pending":
            status_text = Text("pending", style="dim")
            count_text = Text("-", style="dim")
        else:
            status_text = Text(status_str, style="dim")
            count_text = Text("-", style="dim")

        table.add_row(tool_name, status_text, count_text)

    return table


# ---------------------------------------------------------------------------
# Core scan
# ---------------------------------------------------------------------------
async def scan(
    target: str,
    config: Config,
    console: Console | None = None,
    changed_files: list[str] | None = None,
) -> ScanResult:
    """Run all matching tools in parallel, deduplicate, check budget, compute quick wins.

    Args:
        target: Project directory to scan.
        config: Loaded Config object.
        console: Rich Console for output (uses default if None).
        changed_files: Optional list of changed files for incremental scans.

    Returns:
        ScanResult with all findings, dedup, budget, quick wins, and exit code.
    """
    from viberapid.budget import check_budget, load_budget, any_budget_failures, all_critical_exceeded
    from viberapid.deduplicator import deduplicate
    from viberapid.quick_wins import compute_quick_wins
    from viberapid.history import save_scan

    if console is None:
        console = Console()

    # When outputting JSON, route all status/progress messages to stderr
    # so that only the final JSON goes to stdout and remains parseable.
    progress_console = (
        Console(stderr=True) if config.output == "json" else console
    )

    start_time = time.monotonic()
    timestamp = datetime.now(timezone.utc).isoformat()

    # Resolve stack
    effective_stack = config.stack if config.stack != "auto" else detect_stack(target)

    # Reload runners (in case new ones were added after initial import)
    global ALL_RUNNERS
    ALL_RUNNERS = _load_all_runners()

    # ---- Instantiate and filter runners ----
    runners: list[AsyncToolRunner] = []
    skipped: list[tuple[str, str]] = []

    for runner_cls in ALL_RUNNERS:
        name = getattr(runner_cls, "name", runner_cls.__name__)

        # Check if tool is enabled in config
        if not config.is_tool_enabled(name):
            skipped.append((name, "disabled in config"))
            continue

        # Stack filter
        if not _runner_matches_stack(runner_cls, effective_stack):
            skipped.append((name, f"not for {effective_stack} stack"))
            continue

        # Instantiate
        runner = runner_cls(target, config)

        # URL filter
        if runner.requires_url and not config.url:
            skipped.append((name, "no --url provided"))
            continue

        # Load tester filter (same as requires_url — needs a target URL)
        if runner.is_load_tester and not config.url:
            skipped.append((name, "no --url provided (load tester)"))
            continue

        # Pre-flight check
        if not runner.should_run():
            reason = runner.skip_reason or "should_run() returned False"
            skipped.append((name, reason))
            continue

        runners.append(runner)

    if not runners:
        progress_console.print("[yellow]No tools matched the current stack/config.[/yellow]")
        return ScanResult(
            target=target,
            timestamp=timestamp,
            stack=effective_stack,
            exit_code=EXIT_CLEAN,
            duration_seconds=time.monotonic() - start_time,
        )

    # ---- Parallel execution ----
    statuses: dict[str, str] = {}
    for r in runners:
        statuses[r.name] = "pending"
    for name, reason in skipped:
        statuses[name] = f"skipped:{reason}"

    tool_results: list[ToolResult] = []
    all_findings: list[Finding] = []
    has_tool_error = False

    def _run_single(runner: AsyncToolRunner) -> ToolResult:
        """Execute a single runner (blocking, called from thread pool)."""
        t0 = time.monotonic()
        try:
            result = runner.run(changed_files=changed_files)
            result.duration_seconds = time.monotonic() - t0
            return result
        except Exception as exc:
            return ToolResult(
                tool=runner.name,
                status=ToolStatus.FAILED,
                error=str(exc),
                duration_seconds=time.monotonic() - t0,
            )

    loop = asyncio.get_event_loop()

    if config.ship_fast or config.quiet:
        # No live display — just run and collect
        with ThreadPoolExecutor(max_workers=config.threads) as pool:
            futures = {
                loop.run_in_executor(pool, _run_single, runner): runner
                for runner in runners
            }
            for coro in asyncio.as_completed(futures):
                result = await coro
                tool_results.append(result)
                if result.status == ToolStatus.FAILED:
                    has_tool_error = True
    else:
        # Live progress display
        with Live(
            _build_status_table(statuses),
            console=progress_console,
            refresh_per_second=4,
            transient=True,
        ) as live:
            with ThreadPoolExecutor(max_workers=config.threads) as pool:
                pending_futures: dict[asyncio.Future, AsyncToolRunner] = {}

                for runner in runners:
                    statuses[runner.name] = "running"
                    fut = loop.run_in_executor(pool, _run_single, runner)
                    pending_futures[fut] = runner

                live.update(_build_status_table(statuses))

                for coro in asyncio.as_completed(pending_futures):
                    result = await coro
                    tool_results.append(result)

                    if result.status == ToolStatus.FAILED:
                        has_tool_error = True
                        statuses[result.tool] = f"error:{result.error or 'unknown'}"
                    else:
                        count = len(result.findings)
                        statuses[result.tool] = f"done:{count}"

                    live.update(_build_status_table(statuses))

    # ---- Collect findings and filter ignored rules ----
    for tr in tool_results:
        for finding in tr.findings:
            # Ignore by rule
            if config.should_ignore_rule(finding.tool, finding.rule_id):
                continue
            # Ignore by finding ID
            if config.should_ignore_finding(finding.id):
                continue
            all_findings.append(finding)

    # ---- Deduplicate ----
    deduped, overlap = deduplicate(all_findings)

    # ---- Quick wins ----
    quick_wins = compute_quick_wins(deduped)

    # ---- Budget check ----
    budget_results: list[BudgetResult] = []
    budget_path = config.budget_file or ".viberapid-budget.json"
    if Path(target).joinpath(budget_path).exists():
        budget = load_budget(str(Path(target) / budget_path))
        # Aggregate metrics from tool results
        merged_metrics: dict[str, Any] = {}
        for tr in tool_results:
            merged_metrics.update(tr.metrics)
        # Also scan findings for metric values
        for f in deduped:
            if f.metric and f.current_value is not None:
                merged_metrics[f.metric] = f.current_value

        scan_result_for_budget = ScanResult(
            target=target,
            timestamp=timestamp,
            stack=effective_stack,
            tool_results=tool_results,
            findings=all_findings,
            deduplicated_findings=deduped,
        )
        # Inject merged metrics for budget checker
        scan_result_for_budget._merged_metrics = merged_metrics  # type: ignore[attr-defined]
        budget_results = check_budget(budget, scan_result_for_budget)

    # ---- Determine exit code ----
    exit_code = EXIT_CLEAN

    # Check if any findings meet or exceed the fail_on threshold
    for f in deduped:
        if f.severity >= config.fail_on:
            exit_code = EXIT_FINDINGS
            break

    # Budget failures override
    if budget_results and any_budget_failures(budget_results):
        exit_code = EXIT_FINDINGS

    # All critical budget metrics exceeded
    if budget_results and all_critical_exceeded(budget_results):
        exit_code = EXIT_ALL_CRITICAL_BUDGET

    # Tool errors
    if has_tool_error and exit_code == EXIT_CLEAN:
        exit_code = EXIT_TOOL_ERROR

    # ---- Assemble result ----
    duration = time.monotonic() - start_time

    scan_result = ScanResult(
        target=target,
        timestamp=timestamp,
        stack=effective_stack,
        tool_results=tool_results,
        findings=all_findings,
        deduplicated_findings=deduped,
        tool_overlap=overlap,
        budget_results=budget_results,
        quick_wins=quick_wins,
        duration_seconds=duration,
        exit_code=exit_code,
    )

    # ---- Save history ----
    try:
        save_scan(scan_result)
    except Exception:
        pass  # Don't fail scan on history write error

    # ---- ship_fast mode output ----
    if config.ship_fast:
        counts = scan_result.severity_counts
        total = sum(counts.values())
        crits = counts.get("CRITICAL", 0)
        highs = counts.get("HIGH", 0)
        budget_fail = any_budget_failures(budget_results) if budget_results else False
        summary = (
            f"viberapid: {total} findings "
            f"({crits}C/{highs}H) "
            f"in {duration:.1f}s"
        )
        if budget_fail:
            summary += " [BUDGET EXCEEDED]"
        progress_console.print(summary)
    else:
        # Print summary line
        counts = scan_result.severity_counts
        total = len(deduped)
        progress_console.print()
        progress_console.print(
            f"[bold]Scan complete:[/bold] {total} findings, "
            f"{len(tool_results)} tools, "
            f"{duration:.1f}s"
        )
        if scan_result.severity_counts.get("CRITICAL", 0) > 0:
            progress_console.print(
                f"  [red bold]{counts['CRITICAL']} CRITICAL[/red bold]  "
                f"[red]{counts.get('HIGH', 0)} HIGH[/red]  "
                f"[yellow]{counts.get('MEDIUM', 0)} MEDIUM[/yellow]  "
                f"[dim]{counts.get('LOW', 0)} LOW  {counts.get('INFO', 0)} INFO[/dim]"
            )

    return scan_result
