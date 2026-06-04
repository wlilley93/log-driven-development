"""Rich terminal table reporter — severity breakdown, quick wins, budget, GA annotations."""

from __future__ import annotations

import os
from io import StringIO

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from viberapid.config import Config
from viberapid.models import Finding, ScanResult, Severity
from viberapid.reporters.base import BaseReporter


# ---------------------------------------------------------------------------
# Severity styling
# ---------------------------------------------------------------------------
_SEVERITY_STYLES: dict[str, str] = {
    "CRITICAL": "bold white on red",
    "HIGH": "red bold",
    "MEDIUM": "yellow",
    "LOW": "dim",
    "INFO": "dim cyan",
}

_SEVERITY_COLORS: dict[str, str] = {
    "CRITICAL": "red",
    "HIGH": "red",
    "MEDIUM": "yellow",
    "LOW": "blue",
    "INFO": "cyan",
}

_EFFORT_STYLES: dict[str, str] = {
    "LOW": "green",
    "MEDIUM": "yellow",
    "HIGH": "red",
}


def _severity_badge(sev: str) -> Text:
    """Return a styled severity badge."""
    style = _SEVERITY_STYLES.get(sev, "dim")
    return Text(f" {sev} ", style=style)


# ---------------------------------------------------------------------------
# Table Reporter
# ---------------------------------------------------------------------------
class TableReporter(BaseReporter):
    """Rich terminal table output with severity bars, quick wins, and budget."""

    def render(self, console: Console) -> None:
        """Render the full report to the console."""
        result = self.result
        config = self.config

        # -- ship_fast mode: one-line output + GA annotations --
        if config.ship_fast:
            self._render_ship_fast(console)
            return

        console.print()

        # -- Header --
        self._render_header(console)

        # -- Stack & tool summary --
        self._render_stack_info(console)

        # -- Severity breakdown bar chart --
        self._render_severity_bar(console)

        # -- Quick wins panel --
        if result.quick_wins:
            self._render_quick_wins(console)

        # -- Estimated gains --
        gains = result.estimated_gains
        if gains:
            self._render_estimated_gains(console, gains)

        # -- Top findings table --
        if result.deduplicated_findings:
            self._render_findings_table(console)

        # -- Budget results --
        if result.budget_results:
            self._render_budget(console)

        # -- Exit code summary --
        self._render_exit_summary(console)

        # -- GitHub Actions annotations --
        self._emit_ga_annotations()

    def render_to_string(self) -> str:
        """Render the report to a string (for file output)."""
        buf = StringIO()
        file_console = Console(file=buf, force_terminal=True, width=120)
        self.render(file_console)
        return buf.getvalue()

    # -----------------------------------------------------------------
    # ship_fast mode
    # -----------------------------------------------------------------
    def _render_ship_fast(self, console: Console) -> None:
        """One-line CI output for ship_fast mode."""
        result = self.result
        counts = result.severity_counts
        total = sum(counts.values())
        status = "PASS" if result.exit_code == 0 else "FAIL"

        parts = [f"VIBERAPID: {status}"]

        # Key metrics from findings
        lcp = self._find_metric("LCP")
        if lcp is not None:
            parts.append(f"LCP {lcp:.1f}ms")

        bundle_size = self._find_metric("total_js")
        if bundle_size is not None:
            if bundle_size > 1024:
                parts.append(f"{bundle_size / 1024:.1f}MB JS bundle")
            else:
                parts.append(f"{bundle_size:.0f}kB JS bundle")

        # Budget failures
        budget_fails = [b for b in result.budget_results if not b.passed and b.fail_on_exceed]
        for bf in budget_fails[:2]:
            parts.append(f"{bf.metric} {bf.current}{bf.unit} (budget {bf.target}{bf.unit})")

        if total > 0:
            parts.append(f"{counts.get('CRITICAL', 0)}C/{counts.get('HIGH', 0)}H findings")

        parts.append("run viberapid --last for full report")

        line = " | ".join(parts)
        style = "red bold" if result.exit_code != 0 else "green bold"
        console.print(f"[{style}]{line}[/{style}]")

        # Emit GA annotations even in ship_fast mode
        self._emit_ga_annotations()

    # -----------------------------------------------------------------
    # Header
    # -----------------------------------------------------------------
    def _render_header(self, console: Console) -> None:
        target = self.result.target
        ts = self.result.timestamp[:19].replace("T", " ")
        console.print(
            Panel(
                f"[bold]viberapid[/bold]  --  [cyan]{target}[/cyan]  --  [dim]{ts}[/dim]",
                border_style="bright_blue",
                expand=True,
            )
        )

    # -----------------------------------------------------------------
    # Stack info
    # -----------------------------------------------------------------
    def _render_stack_info(self, console: Console) -> None:
        result = self.result
        ok_count = sum(
            1 for tr in result.tool_results if tr.status.value in ("success", "partial")
        )
        fail_count = sum(
            1 for tr in result.tool_results if tr.status.value in ("failed", "timeout")
        )
        skip_count = sum(
            1 for tr in result.tool_results if tr.status.value == "skipped"
        )

        stack_label = result.stack.capitalize() if result.stack != "fullstack" else "Node + Python"
        console.print(
            f"  Stack: [bold]{stack_label}[/bold]  |  "
            f"Tools run: [green]{ok_count} ok[/green]"
            + (f"  [red]{fail_count} failed[/red]" if fail_count else "")
            + (f"  [dim]{skip_count} skipped[/dim]" if skip_count else "")
            + f"  |  Duration: [bold]{result.duration_seconds:.1f}s[/bold]"
        )
        console.print()

    # -----------------------------------------------------------------
    # Severity breakdown bar chart
    # -----------------------------------------------------------------
    def _render_severity_bar(self, console: Console) -> None:
        counts = self.result.severity_counts
        total = sum(counts.values())

        if total == 0:
            console.print("  [green bold]No findings[/green bold]")
            console.print()
            return

        bar_width = 50
        parts: list[tuple[str, int, str]] = []

        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
            count = counts.get(sev, 0)
            if count > 0:
                width = max(1, round(count / total * bar_width))
                color = _SEVERITY_COLORS.get(sev, "white")
                parts.append((sev, count, color))

        bar = Text("  ")
        for sev, count, color in parts:
            width = max(1, round(count / total * bar_width))
            bar.append("=" * width, style=color)

        console.print(bar)

        # Legend
        legend_parts = []
        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
            count = counts.get(sev, 0)
            if count > 0:
                style = _SEVERITY_STYLES.get(sev, "dim")
                legend_parts.append(f"[{style}]{sev}: {count}[/{style}]")

        console.print("  " + "  ".join(legend_parts) + f"  [dim]Total: {total}[/dim]")
        console.print()

    # -----------------------------------------------------------------
    # Quick wins panel
    # -----------------------------------------------------------------
    def _render_quick_wins(self, console: Console) -> None:
        qw_table = Table(
            title="Quick Wins (top 5 by ROI)",
            show_header=True,
            header_style="bold green",
            title_style="bold green",
            expand=True,
            padding=(0, 1),
        )
        qw_table.add_column("#", justify="right", style="dim", width=3)
        qw_table.add_column("Sev", min_width=8)
        qw_table.add_column("Tool", style="cyan", min_width=12)
        qw_table.add_column("Message", min_width=30, max_width=60)
        qw_table.add_column("Effort", min_width=8)
        qw_table.add_column("Saving", min_width=12)
        qw_table.add_column("Score", justify="right", min_width=6)

        for i, qw in enumerate(self.result.quick_wins[:5], 1):
            effort_style = _EFFORT_STYLES.get(qw.effort.value, "dim")
            qw_table.add_row(
                str(i),
                _severity_badge(qw.severity.value),
                qw.tool,
                qw.message[:60],
                Text(qw.effort.value, style=effort_style),
                qw.saving_estimate or "-",
                f"{qw.quick_win_score:.1f}",
            )

        console.print(qw_table)
        console.print()

    # -----------------------------------------------------------------
    # Estimated gains
    # -----------------------------------------------------------------
    def _render_estimated_gains(
        self,
        console: Console,
        gains: dict[str, str],
    ) -> None:
        console.print("[bold]Estimated gains from fixing CRITICAL + HIGH:[/bold]")
        for category, savings in gains.items():
            console.print(f"  [cyan]{category}:[/cyan] {savings}")
        console.print()

    # -----------------------------------------------------------------
    # Findings table
    # -----------------------------------------------------------------
    def _render_findings_table(self, console: Console) -> None:
        findings = self.result.deduplicated_findings
        show_fix = self.config.fix

        table = Table(
            title=f"Findings ({len(findings)})",
            show_header=True,
            header_style="bold",
            expand=True,
            padding=(0, 1),
        )
        table.add_column("Sev", min_width=8)
        table.add_column("Tool", style="cyan", min_width=10)
        table.add_column("Location", min_width=15, max_width=40)
        table.add_column("Message", min_width=20, max_width=50)
        table.add_column("Metric", min_width=10)
        table.add_column("Effort", min_width=7)

        if show_fix:
            table.add_column("Fix", min_width=15, max_width=40)

        for f in findings:
            location = f.file
            if f.line:
                location += f":{f.line}"

            metric_str = ""
            if f.metric:
                metric_str = f.metric
                if f.current_value is not None:
                    metric_str += f"={f.current_value}"
                if f.target_value is not None:
                    metric_str += f" (target: {f.target_value})"

            effort_style = _EFFORT_STYLES.get(f.effort.value, "dim")

            row = [
                _severity_badge(f.severity.value),
                ", ".join(f.tools) if f.tools else f.tool,
                location,
                f.message[:50],
                metric_str[:20] if metric_str else "-",
                Text(f.effort.value, style=effort_style),
            ]

            if show_fix:
                row.append(f.fix_hint or "-")

            table.add_row(*row)

        console.print(table)
        console.print()

    # -----------------------------------------------------------------
    # Budget
    # -----------------------------------------------------------------
    def _render_budget(self, console: Console) -> None:
        budget_table = Table(
            title="Budget Results",
            show_header=True,
            header_style="bold",
            expand=True,
            padding=(0, 1),
        )
        budget_table.add_column("Metric", style="cyan", min_width=15)
        budget_table.add_column("Current", justify="right", min_width=10)
        budget_table.add_column("Target", justify="right", min_width=10)
        budget_table.add_column("Unit", min_width=6)
        budget_table.add_column("Status", min_width=8)
        budget_table.add_column("Blocking", min_width=8)

        for br in self.result.budget_results:
            if br.passed:
                status = Text("PASS", style="green bold")
            else:
                status = Text("FAIL", style="red bold")

            blocking = Text("yes", style="red") if br.fail_on_exceed else Text("no", style="dim")

            budget_table.add_row(
                br.metric,
                f"{br.current}",
                f"{br.target}",
                br.unit,
                status,
                blocking,
            )

        console.print(budget_table)
        console.print()

    # -----------------------------------------------------------------
    # Exit summary
    # -----------------------------------------------------------------
    def _render_exit_summary(self, console: Console) -> None:
        code = self.result.exit_code
        reasons = {
            0: "All clear -- no blocking findings.",
            1: "Findings at or above threshold detected.",
            2: "One or more tools failed to execute.",
            3: "Required tools are missing.",
            4: "All critical budget metrics exceeded.",
        }
        reason = reasons.get(code, f"Unknown exit code {code}.")

        if code == 0:
            style = "green bold"
        else:
            style = "red bold"

        console.print(
            f"  [{style}]Exit {code}[/{style}]: {reason}"
        )
        console.print()

    # -----------------------------------------------------------------
    # GitHub Actions annotations
    # -----------------------------------------------------------------
    def _emit_ga_annotations(self) -> None:
        """Emit GitHub Actions annotation commands for blocking findings."""
        if not os.environ.get("GITHUB_ACTIONS"):
            return

        for f in self.result.deduplicated_findings:
            if f.severity >= Severity.HIGH:
                level = "error" if f.severity >= Severity.HIGH else "warning"
                file_part = f"file={f.file}" if f.file else ""
                line_part = f",line={f.line}" if f.line else ""
                col_part = f",col={f.col}" if f.col else ""
                title = f"viberapid/{f.tool}: {f.rule_id}"
                msg = f.message.replace("\n", " ")

                print(
                    f"::{level} {file_part}{line_part}{col_part},title={title}::{msg}"
                )

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------
    def _find_metric(self, name: str) -> float | None:
        """Find a metric value from tool results or findings."""
        for tr in self.result.tool_results:
            if name in tr.metrics:
                val = tr.metrics[name]
                if isinstance(val, (int, float)):
                    return float(val)

        for f in self.result.deduplicated_findings:
            if f.metric == name and f.current_value is not None:
                return f.current_value

        return None
