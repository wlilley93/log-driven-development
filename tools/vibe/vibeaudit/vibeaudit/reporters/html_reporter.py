"""HTML reporter — renders a self-contained HTML report using Jinja2."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from rich.console import Console

from vibeaudit.models import ScanResult, Severity
from vibeaudit.reporters.base import Reporter

_TEMPLATES_DIR = Path(__file__).parent / "templates"


class HtmlReporter(Reporter):
    """Renders a self-contained HTML report from a Jinja2 template."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def report(self, result: ScanResult, console: Console, output_path: Path | None = None) -> None:
        template = self._env.get_template("report.html.j2")

        # Pre-compute grouped findings by severity for the template
        grouped: dict[str, list] = {}
        for sev in Severity:
            sev_findings = [f for f in result.findings if f.severity == sev]
            if sev_findings:
                grouped[sev.value] = sev_findings

        # Compute severity counts including zeros
        severity_counts: list[dict] = []
        for sev in Severity:
            count = result.counts_by_severity.get(sev.value, 0)
            severity_counts.append({
                "name": sev.value.upper(),
                "count": count,
                "key": sev.value,
            })
        total_findings = len(result.findings)

        # Max count for bar chart scaling
        max_count = max((s["count"] for s in severity_counts), default=1) or 1

        # Format duration
        duration_str = ""
        if result.duration_seconds > 0:
            mins, secs = divmod(result.duration_seconds, 60)
            if mins > 0:
                duration_str = f"{int(mins)}m {secs:.1f}s"
            else:
                duration_str = f"{secs:.1f}s"

        html = template.render(
            result=result,
            grouped=grouped,
            severity_counts=severity_counts,
            total_findings=total_findings,
            max_count=max_count,
            duration_str=duration_str,
            timestamp_str=result.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
            severities=Severity,
        )

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(html, encoding="utf-8")
            console.print(f"[green]HTML report written to {output_path}[/green]")
        else:
            # Write to default filename when no output specified
            default_path = Path("vibeaudit-report.html")
            default_path.write_text(html, encoding="utf-8")
            console.print(f"[green]HTML report written to {default_path}[/green]")
