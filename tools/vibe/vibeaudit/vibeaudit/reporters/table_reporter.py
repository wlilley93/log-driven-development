"""Rich terminal table reporter with severity-colored output."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from vibeaudit.models import ScanResult, Severity
from vibeaudit.reporters.base import Reporter

# Severity -> Rich style mapping
_SEVERITY_STYLES: dict[Severity, str] = {
    Severity.CRITICAL: "bold red",
    Severity.HIGH: "red",
    Severity.MEDIUM: "yellow",
    Severity.LOW: "blue",
    Severity.INFO: "dim",
}


class TableReporter(Reporter):
    """Rich terminal output with severity-colored table and summary panel."""

    def __init__(self, quiet: bool = False) -> None:
        self._quiet = quiet

    def report(self, result: ScanResult, console: Console, output_path: Path | None = None) -> None:
        if not result.findings:
            if not self._quiet:
                console.print("\n[bold green]No security findings detected.[/bold green]")
                self._print_summary(result, console)
            return

        if not self._quiet:
            console.print()

        # Main findings table
        table = Table(
            title="Security Findings" if not self._quiet else None,
            show_header=True,
            header_style="bold",
            border_style="dim",
            expand=False,
        )
        table.add_column("ID", style="dim", width=10)
        table.add_column("Severity", width=10)
        table.add_column("Class", width=20)
        table.add_column("File:Line", width=35)
        table.add_column("Title", min_width=30)
        table.add_column("Confidence", width=12)

        for finding in result.findings:
            style = _SEVERITY_STYLES.get(finding.severity, "")
            severity_text = Text(finding.severity.value.upper(), style=style)

            # Truncate long file paths
            file_loc = finding.file_location
            if len(file_loc) > 35:
                file_loc = "..." + file_loc[-32:]

            table.add_row(
                finding.id[:10],
                severity_text,
                finding.vuln_class.value,
                file_loc,
                finding.title,
                finding.confidence.value,
            )

        console.print(table)

        if not self._quiet:
            # Expanded details for CRITICAL and HIGH findings
            critical_high = [
                f for f in result.findings
                if f.severity in (Severity.CRITICAL, Severity.HIGH)
            ]
            if critical_high:
                console.print()
                for finding in critical_high:
                    style = _SEVERITY_STYLES.get(finding.severity, "red")
                    title = f"[{style}]{finding.severity.value.upper()}[/{style}] {finding.title} ({finding.id[:10]})"

                    detail_parts: list[str] = []
                    detail_parts.append(f"[bold]File:[/bold] {finding.file_location}")
                    detail_parts.append(f"[bold]Class:[/bold] {finding.vuln_class.value}")

                    if finding.description:
                        detail_parts.append(f"\n[bold]Description:[/bold]\n{finding.description}")
                    if finding.attack_scenario:
                        detail_parts.append(f"\n[bold]Attack Scenario:[/bold]\n{finding.attack_scenario}")
                    if finding.remediation:
                        detail_parts.append(f"\n[bold]Remediation:[/bold]\n{finding.remediation}")

                    console.print(Panel(
                        "\n".join(detail_parts),
                        title=title,
                        border_style=style,
                        expand=True,
                        padding=(1, 2),
                    ))

            # Summary panel
            self._print_summary(result, console)

    def _print_summary(self, result: ScanResult, console: Console) -> None:
        """Print a summary panel with severity counts and scan metadata."""
        parts: list[str] = []

        # Severity counts
        counts = result.counts_by_severity
        if counts:
            count_parts: list[str] = []
            for sev in Severity:
                count = counts.get(sev.value, 0)
                if count > 0:
                    style = _SEVERITY_STYLES.get(sev, "")
                    count_parts.append(f"[{style}]{sev.value.upper()}: {count}[/{style}]")
            parts.append("  ".join(count_parts))
        else:
            parts.append("[green]No findings[/green]")

        # Metadata
        meta: list[str] = []
        meta.append(f"Files scanned: {result.scanned_files}")
        if result.scanned_classes:
            meta.append(f"Classes: {len(result.scanned_classes)}")
        if result.provider:
            meta.append(f"Provider: {result.provider}")
        if result.model:
            meta.append(f"Model: {result.model}")
        if result.total_tokens > 0:
            meta.append(f"Tokens: {result.total_tokens:,}")
        if result.total_cost_usd > 0:
            meta.append(f"Cost: ${result.total_cost_usd:.2f}")
        if result.duration_seconds > 0:
            mins, secs = divmod(result.duration_seconds, 60)
            if mins > 0:
                meta.append(f"Duration: {int(mins)}m {secs:.1f}s")
            else:
                meta.append(f"Duration: {secs:.1f}s")

        parts.append("  ".join(meta))

        console.print()
        console.print(Panel(
            "\n".join(parts),
            title="[bold]Scan Summary[/bold]",
            border_style="dim",
            padding=(0, 2),
        ))
