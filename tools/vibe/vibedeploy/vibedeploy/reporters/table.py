"""Rich terminal table reporter (default output format)."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from vibedeploy.config import Config
from vibedeploy.models import Finding, ScanResult, Severity, ToolStatus
from vibedeploy.reporters.base import BaseReporter

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

_MAX_FINDINGS = 20
_BAR_MAX_WIDTH = 40


def _exit_reason(code: int) -> str:
    if code == 0:
        return "deploy ready"
    if code == 1:
        return "findings above threshold"
    if code == 2:
        return "tool failure"
    if code == 3:
        return "required tools missing"
    if code == 4:
        return "secrets detected"
    return f"code {code}"


def _location(f: Finding) -> str:
    loc = f.file
    if f.line is not None:
        loc += f":{f.line}"
    return loc


class TableReporter(BaseReporter):
    """Rich terminal output with deploy readiness score, severity bars, and top findings."""

    def __init__(self, result: ScanResult, config: Config):
        super().__init__(result, config)

    def render(self, console: Console) -> None:
        console.print()
        self._render_header(console)
        console.print()
        self._render_readiness(console)
        console.print()

        # Deploy blockers section
        self.render_deploy_blockers(console)

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
        passed = self.result.exit_code == 0
        score = self.result.readiness_score
        blockers = len(self.result.deploy_blockers)

        parts: list[str] = []
        for sev in (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW):
            n = counts.get(sev.value, 0)
            if n > 0:
                parts.append(f"{n} {sev.value}")

        counts_str = ", ".join(parts) if parts else "0 findings"

        # Top blockers
        blocker_list: list[str] = []
        for f in self.result.deploy_blockers[:3]:
            blocker_list.append(f"{f.rule_id} in {f.file}")

        blocker_str = ""
        if blocker_list:
            blocker_str = f" | blockers: {'; '.join(blocker_list)}"

        status = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
        console.print(
            f"VIBEDEPLOY: {status} \u2014 score {score}/100 \u2014 {counts_str}"
            f" \u2014 {blockers} blocker(s){blocker_str}"
            f" | run [bold]vibedeploy report --last[/bold] for full report"
        )

    def _render_header(self, console: Console) -> None:
        title = Text.assemble(
            ("vibedeploy", "bold cyan"),
            (" \u2014 ", "dim"),
            (self.result.target, "bold"),
            (" \u2014 ", "dim"),
            (self.result.timestamp, "dim"),
        )
        console.print(Panel(title, expand=False, border_style="dim"))

    def _render_readiness(self, console: Console) -> None:
        score = self.result.readiness_score
        blockers = len(self.result.deploy_blockers)

        if score >= 90:
            style = "bold green"
            emoji = "READY"
        elif score >= 70:
            style = "bold yellow"
            emoji = "CAUTION"
        else:
            style = "bold red"
            emoji = "NOT READY"

        console.print(
            Text.assemble(
                ("Deploy Readiness: ", "bold"),
                (f"{score}/100", style),
                (f" ({emoji})", style),
                ("  |  ", "dim"),
                (f"{blockers} deploy blocker(s)", "bold red" if blockers > 0 else "green"),
            )
        )

        if self.result.stack_info.get("tags"):
            tags = ", ".join(self.result.stack_info["tags"])
            console.print(f"  [dim]Stack: {tags}[/dim]")

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
        table.add_column("Blockers", justify="right")
        table.add_column("Time", justify="right", style="dim")

        for tr in self.result.tool_results:
            icon = _STATUS_ICONS.get(tr.status, "?")
            status_label = f"{icon} {tr.status.value}"
            finding_count = str(len(tr.findings))
            blocker_count = str(sum(1 for f in tr.findings if f.blocks_deploy))
            duration = f"{tr.duration_seconds:.1f}s"

            error_note = ""
            if tr.error:
                error_note = f" [dim]({tr.error[:40]})[/dim]"

            table.add_row(tr.tool, status_label + error_note, finding_count, blocker_count, duration)

        console.print(table)

    def _render_severity_bar(self, console: Console) -> None:
        counts = self.result.severity_counts
        total = sum(counts.values())
        if total == 0:
            console.print("[green]No findings \u2014 ship it![/green]")
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
            key=lambda f: (-int(f.blocks_deploy), -f.severity.rank),
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
        table.add_column("Sev", no_wrap=True, width=10)
        table.add_column("Blocks", no_wrap=True, width=7)
        table.add_column("Tool", style="cyan", no_wrap=True, width=14)
        table.add_column("Location", no_wrap=True, ratio=1)
        table.add_column("Message", ratio=2)

        for f in findings:
            sev_text = Text(f.severity.value, style=_SEVERITY_STYLES[f.severity])
            blocks = "[red]YES[/red]" if f.blocks_deploy else "[dim]no[/dim]"
            location = _location(f)
            msg = f.message
            if self.config.fix and f.fix_hint:
                msg += f"\n  [dim italic]Fix: {f.fix_hint}[/dim italic]"
            if self.config.fix and f.fix_command:
                msg += f"\n  [dim]$ {f.fix_command}[/dim]"
            table.add_row(sev_text, blocks, f.tool, location, msg)

        console.print(table)

    def _render_overlap(self, console: Console) -> None:
        overlap = self.result.tool_overlap
        pair_overlap = overlap.get("pair_overlap", {})
        if not pair_overlap:
            return

        console.print(Text("Tool Overlap", style="bold"))
        for pair, count in pair_overlap.items():
            console.print(
                f"  [dim]{pair}[/dim]: "
                f"{count} shared finding{'s' if count != 1 else ''}"
            )

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
