"""Rich terminal table reporter (default output format)."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from vibescan.config import Config
from vibescan.models import Finding, ScanResult, Severity, ToolStatus
from vibescan.reporters.base import BaseReporter

_SEVERITY_STYLES: dict[Severity, str] = {
    Severity.CRITICAL: "bold red",
    Severity.HIGH: "yellow",
    Severity.MEDIUM: "default",
    Severity.LOW: "dim",
    Severity.INFO: "dim italic",
}

_STATUS_ICONS: dict[ToolStatus, str] = {
    ToolStatus.SUCCESS: "[green]\u2713[/green]",
    ToolStatus.PARTIAL: "[yellow]\u2713[/yellow]",
    ToolStatus.FAILED: "[red]\u2717[/red]",
    ToolStatus.SKIPPED: "[dim]\u2298[/dim]",
    ToolStatus.TIMEOUT: "[red]\u2298[/red]",
}

_BAR_CHARS = {
    Severity.CRITICAL: ("\u2588", "red"),
    Severity.HIGH: ("\u2588", "yellow"),
    Severity.MEDIUM: ("\u2588", "default"),
    Severity.LOW: ("\u2588", "dim"),
    Severity.INFO: ("\u2588", "dim"),
}

_MAX_FINDINGS = 15
_BAR_MAX_WIDTH = 40


def _exit_reason(code: int) -> str:
    if code == 0:
        return "clean"
    if code == 1:
        return "findings above threshold"
    if code == 2:
        return "tool failure"
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

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def render(self, console: Console) -> None:
        console.print()
        self._render_header(console)
        console.print()
        self._render_tool_status(console)
        console.print()
        self._render_severity_bar(console)
        console.print()
        self._render_top_findings(console)

        if self.result.tool_overlap:
            console.print()
            self._render_overlap(console)

        console.print()
        self._render_exit(console)
        console.print()

    def render_to_string(self) -> str:
        buf = Console(file=None, force_terminal=False, width=120, record=True)
        self.render(buf)
        return buf.export_text()

    def render_ship_safe(self, console: Console) -> None:
        """One-line ship-safe summary for CI pipelines."""
        counts = self.result.severity_counts
        total = sum(counts.values())
        passed = self.result.exit_code == 0

        parts: list[str] = []
        for sev in (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW):
            n = counts.get(sev.value, 0)
            if n > 0:
                parts.append(f"{n} {sev.value}")

        counts_str = ", ".join(parts) if parts else "0 findings"

        # Top blockers: findings at or above fail_on threshold
        blockers: list[str] = []
        for f in sorted(
            self.result.deduplicated_findings,
            key=lambda x: x.severity.rank,
            reverse=True,
        ):
            if f.severity >= self.config.fail_on and len(blockers) < 3:
                blockers.append(f"{f.rule_id} in {f.file}")

        blocker_str = ""
        if blockers:
            blocker_str = f" | top: {'; '.join(blockers)}"

        status = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
        console.print(
            f"VIBESCAN: {status} \u2014 {counts_str}{blocker_str} "
            f"| run [bold]vibescan --last[/bold] for full report"
        )

    # ------------------------------------------------------------------
    # Private rendering helpers
    # ------------------------------------------------------------------

    def _render_header(self, console: Console) -> None:
        title = Text.assemble(
            ("vibescan", "bold cyan"),
            (" \u2014 ", "dim"),
            (self.result.target, "bold"),
            (" \u2014 ", "dim"),
            (self.result.timestamp, "dim"),
        )
        console.print(Panel(title, expand=False, border_style="dim"))

    def _render_tool_status(self, console: Console) -> None:
        table = Table(
            title="Tool Status",
            title_style="bold",
            show_header=True,
            header_style="bold",
            padding=(0, 1),
            expand=False,
        )
        table.add_column("Tool", style="cyan", no_wrap=True)
        table.add_column("Status", justify="center", no_wrap=True)
        table.add_column("Findings", justify="right")
        table.add_column("Time", justify="right", style="dim")

        for tr in self.result.tool_results:
            icon = _STATUS_ICONS.get(tr.status, "?")
            status_label = f"{icon} {tr.status.value}"
            finding_count = str(len(tr.findings))
            duration = f"{tr.duration_seconds:.1f}s"

            error_note = ""
            if tr.error:
                error_note = f" [dim]({tr.error})[/dim]"

            table.add_row(tr.tool, status_label + error_note, finding_count, duration)

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

    def _render_top_findings(self, console: Console) -> None:
        findings = sorted(
            self.result.deduplicated_findings,
            key=lambda f: f.severity.rank,
            reverse=True,
        )[:_MAX_FINDINGS]

        if not findings:
            return

        table = Table(
            title=f"Top Findings (max {_MAX_FINDINGS})",
            title_style="bold",
            show_header=True,
            header_style="bold",
            padding=(0, 1),
            expand=True,
        )
        table.add_column("Severity", no_wrap=True, width=10)
        table.add_column("Tool", style="cyan", no_wrap=True, width=12)
        table.add_column("Location", no_wrap=True, ratio=1)
        table.add_column("Message", ratio=2)

        for f in findings:
            sev_text = Text(f.severity.value, style=_SEVERITY_STYLES[f.severity])
            location = _location(f)
            msg = f.message
            if self.config.fix and f.fix_hint:
                msg += f"\n  [dim italic]Fix: {f.fix_hint}[/dim italic]"
            table.add_row(sev_text, f.tool, location, msg)

        console.print(table)

    def _render_overlap(self, console: Console) -> None:
        overlap = self.result.tool_overlap
        if not overlap:
            return

        console.print(Text("Tool Overlap", style="bold"))
        for group_key, group_data in overlap.items():
            if isinstance(group_data, dict):
                tools = group_data.get("tools", [])
                count = group_data.get("count", 0)
                if tools and count:
                    console.print(
                        f"  [dim]{' + '.join(tools)}[/dim]: "
                        f"{count} shared finding{'s' if count != 1 else ''}"
                    )
            elif isinstance(group_data, (int, float)):
                console.print(f"  [dim]{group_key}[/dim]: {group_data}")

    def _render_exit(self, console: Console) -> None:
        code = self.result.exit_code
        reason = _exit_reason(code)
        style = "green" if code == 0 else "red bold"
        duration = f"{self.result.duration_seconds:.1f}s"
        console.print(
            Text.assemble(
                ("Exit: ", "bold"),
                (str(code), style),
                (f" ({reason})", "dim"),
                ("  |  ", "dim"),
                ("Duration: ", "bold"),
                (duration, "dim"),
            )
        )
