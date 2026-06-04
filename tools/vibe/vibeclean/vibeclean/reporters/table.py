"""Rich terminal table reporter (default output format)."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from vibeclean.config import Config
from vibeclean.models import Category, Finding, ScanResult, Severity, RunnerStatus
from vibeclean.reporters.base import BaseReporter

_SEVERITY_STYLES: dict[Severity, str] = {
    Severity.CRITICAL: "bold red",
    Severity.HIGH: "yellow",
    Severity.MEDIUM: "default",
    Severity.LOW: "dim",
    Severity.INFO: "dim italic",
}

_CATEGORY_STYLES: dict[str, str] = {
    "DEAD_CODE": "red",
    "SLOP": "magenta",
    "COMPLEXITY": "yellow",
    "DUPLICATION": "cyan",
    "CONVENTION": "blue",
}

_STATUS_ICONS: dict[RunnerStatus, str] = {
    RunnerStatus.SUCCESS: "[green]\u2713[/green]",
    RunnerStatus.PARTIAL: "[yellow]\u2713[/yellow]",
    RunnerStatus.FAILED: "[red]\u2717[/red]",
    RunnerStatus.SKIPPED: "[dim]\u2298[/dim]",
}

_BAR_CHARS = {
    Severity.CRITICAL: ("\u2588", "red"),
    Severity.HIGH: ("\u2588", "yellow"),
    Severity.MEDIUM: ("\u2588", "default"),
    Severity.LOW: ("\u2588", "dim"),
    Severity.INFO: ("\u2588", "dim"),
}

_MAX_FINDINGS = 20
_BAR_MAX_WIDTH = 40


def _exit_reason(code: int) -> str:
    if code == 0:
        return "clean"
    if code == 1:
        return "findings above threshold"
    if code == 2:
        return "runner failure"
    return f"code {code}"


def _location(f: Finding) -> str:
    loc = f.file
    if f.line is not None:
        loc += f":{f.line}"
    return loc


class TableReporter(BaseReporter):
    """Rich terminal output with severity bar chart and top findings."""

    def __init__(self, result: ScanResult, config: Config):
        super().__init__(result, config)

    def render(self, console: Console) -> None:
        console.print()
        self._render_header(console)
        console.print()
        self._render_runner_status(console)
        console.print()
        self._render_severity_bar(console)
        console.print()
        self._render_category_breakdown(console)
        console.print()
        self._render_top_findings(console)
        console.print()
        self._render_exit(console)
        console.print()

    def render_to_string(self) -> str:
        buf = Console(file=None, force_terminal=False, width=120, record=True)
        self.render(buf)
        return buf.export_text()

    def _render_header(self, console: Console) -> None:
        title = Text.assemble(
            ("vibeclean", "bold cyan"),
            (" \u2014 ", "dim"),
            (self.result.target, "bold"),
        )
        console.print(Panel(title, expand=False, border_style="dim"))

    def _render_runner_status(self, console: Console) -> None:
        table = Table(
            title="Runner Status",
            title_style="bold",
            show_header=True,
            header_style="bold",
            padding=(0, 1),
            expand=False,
        )
        table.add_column("Runner", style="cyan", no_wrap=True)
        table.add_column("Status", justify="center", no_wrap=True)
        table.add_column("Findings", justify="right")
        table.add_column("Time", justify="right", style="dim")

        for rr in self.result.runner_results:
            icon = _STATUS_ICONS.get(rr.status, "?")
            status_label = f"{icon} {rr.status.value}"
            finding_count = str(len(rr.findings))
            duration = f"{rr.duration_seconds:.1f}s"

            error_note = ""
            if rr.error:
                error_note = f" [dim]({rr.error})[/dim]"

            table.add_row(rr.runner, status_label + error_note, finding_count, duration)

        console.print(table)

    def _render_severity_bar(self, console: Console) -> None:
        counts = self.result.severity_counts
        total = sum(counts.values())
        if total == 0:
            console.print("[green]No findings[/green]")
            return

        console.print(Text("Severity Breakdown", style="bold"))

        max_count = max(counts.values()) if counts else 1

        for sev in (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO):
            count = counts.get(sev.value, 0)
            if count == 0:
                continue

            bar_len = max(1, int((count / max_count) * _BAR_MAX_WIDTH))
            char, color = _BAR_CHARS[sev]
            bar = char * bar_len

            label = f"  {sev.value:<9}"
            console.print(
                Text.assemble(
                    (label, _SEVERITY_STYLES[sev]),
                    (" ", ""),
                    (bar, color),
                    (f" {count}", _SEVERITY_STYLES[sev]),
                )
            )

    def _render_category_breakdown(self, console: Console) -> None:
        cat_counts = self.result.findings_by_category
        if not cat_counts:
            return

        console.print(Text("Category Breakdown", style="bold"))
        for cat, count in sorted(cat_counts.items(), key=lambda x: x[1], reverse=True):
            style = _CATEGORY_STYLES.get(cat, "default")
            console.print(f"  [{style}]{cat:<14}[/{style}] {count}")

    def _render_top_findings(self, console: Console) -> None:
        findings = sorted(
            self.result.findings,
            key=lambda f: f.severity.rank,
            reverse=True,
        )[:_MAX_FINDINGS]

        if not findings:
            return

        total = len(self.result.findings)
        shown = len(findings)
        title = f"Top Findings (showing {shown}"
        if total > shown:
            title += f" of {total}"
        title += ")"

        table = Table(
            title=title,
            title_style="bold",
            show_header=True,
            header_style="bold",
            padding=(0, 1),
            expand=True,
        )
        table.add_column("Severity", no_wrap=True, width=10)
        table.add_column("Category", no_wrap=True, width=14)
        table.add_column("Location", no_wrap=True, ratio=1)
        table.add_column("Message", ratio=2)

        for f in findings:
            sev_text = Text(f.severity.value, style=_SEVERITY_STYLES[f.severity])
            cat_style = _CATEGORY_STYLES.get(f.category.value, "default")
            cat_text = Text(f.category.value, style=cat_style)
            location = _location(f)
            msg = f.message
            if self.config.fix and f.fix_hint:
                msg += f"\n  [dim italic]Fix: {f.fix_hint}[/dim italic]"
            table.add_row(sev_text, cat_text, location, msg)

        console.print(table)

    def _render_exit(self, console: Console) -> None:
        code = self.result.exit_code
        reason = _exit_reason(code)
        style = "green" if code == 0 else "red bold"
        duration = f"{self.result.duration_seconds:.1f}s"
        total = len(self.result.findings)
        console.print(
            Text.assemble(
                ("Exit: ", "bold"),
                (str(code), style),
                (f" ({reason})", "dim"),
                ("  |  ", "dim"),
                (f"{total} findings", "bold"),
                ("  |  ", "dim"),
                ("Duration: ", "bold"),
                (duration, "dim"),
            )
        )
