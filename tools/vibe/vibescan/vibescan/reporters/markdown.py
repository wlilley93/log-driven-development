"""Markdown reporter — PR comment format (GitHub-flavored markdown)."""

from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown

from vibescan.config import Config
from vibescan.models import Finding, ScanResult, Severity, ToolStatus
from vibescan.reporters.base import BaseReporter

_MAX_FINDINGS = 10

_SEVERITY_EMOJI: dict[Severity, str] = {
    Severity.CRITICAL: "\U0001f534",
    Severity.HIGH: "\U0001f7e0",
    Severity.MEDIUM: "\U0001f7e1",
    Severity.LOW: "\U0001f535",
    Severity.INFO: "\u26aa",
}

_STATUS_ICON: dict[ToolStatus, str] = {
    ToolStatus.SUCCESS: "\u2705",
    ToolStatus.PARTIAL: "\u26a0\ufe0f",
    ToolStatus.FAILED: "\u274c",
    ToolStatus.SKIPPED: "\u23ed\ufe0f",
    ToolStatus.TIMEOUT: "\u23f0",
}


def _location_link(f: Finding) -> str:
    """GitHub-relative file:line link."""
    loc = f.file
    if f.line is not None:
        loc += f":{f.line}"
    # Use backtick-wrapped path as a relative reference
    return f"`{loc}`"


class MarkdownReporter(BaseReporter):
    """Concise markdown report designed for PR comments via gh pr comment."""

    def __init__(self, result: ScanResult, config: Config):
        super().__init__(result, config)

    def render(self, console: Console) -> None:
        md_str = self.render_to_string()
        console.print(Markdown(md_str))

    def render_to_string(self) -> str:
        lines: list[str] = []

        self._write_header(lines)
        self._write_severity_table(lines)
        self._write_top_findings(lines)
        self._write_tool_status(lines)
        self._write_footer(lines)

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Sections
    # ------------------------------------------------------------------

    def _write_header(self, lines: list[str]) -> None:
        total = len(self.result.deduplicated_findings)
        status = "PASS" if self.result.exit_code == 0 else "FAIL"
        icon = "\u2705" if self.result.exit_code == 0 else "\u274c"

        lines.append(f"## {icon} vibescan: {status}")
        lines.append("")
        lines.append(
            f"> **{total}** finding{'s' if total != 1 else ''} "
            f"in **{self.result.duration_seconds:.1f}s** "
            f"| target: `{self.result.target}` "
            f"| exit: `{self.result.exit_code}`"
        )
        lines.append("")

    def _write_severity_table(self, lines: list[str]) -> None:
        counts = self.result.severity_counts

        lines.append("### Severity Summary")
        lines.append("")
        lines.append("| Severity | Count |")
        lines.append("|----------|------:|")

        for sev in (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO):
            count = counts.get(sev.value, 0)
            emoji = _SEVERITY_EMOJI[sev]
            lines.append(f"| {emoji} {sev.value} | {count} |")

        lines.append("")

    def _write_top_findings(self, lines: list[str]) -> None:
        findings = sorted(
            self.result.deduplicated_findings,
            key=lambda f: f.severity.rank,
            reverse=True,
        )[:_MAX_FINDINGS]

        if not findings:
            lines.append("*No findings detected.*")
            lines.append("")
            return

        total = len(self.result.deduplicated_findings)
        shown = len(findings)
        title = f"### Top {shown} Findings"
        if total > shown:
            title += f" (of {total})"
        lines.append(title)
        lines.append("")
        lines.append("| Severity | Tool | Location | Message |")
        lines.append("|----------|------|----------|---------|")

        for f in findings:
            emoji = _SEVERITY_EMOJI[f.severity]
            loc = _location_link(f)
            # Escape pipes in message to avoid breaking table
            msg = f.message.replace("|", "\\|")
            if len(msg) > 120:
                msg = msg[:117] + "..."
            lines.append(f"| {emoji} {f.severity.value} | {f.tool} | {loc} | {msg} |")

        lines.append("")

    def _write_tool_status(self, lines: list[str]) -> None:
        lines.append("<details>")
        lines.append("<summary><strong>Tool Status</strong></summary>")
        lines.append("")
        lines.append("| Tool | Status | Findings | Duration |")
        lines.append("|------|--------|----------|----------|")

        for tr in self.result.tool_results:
            icon = _STATUS_ICON.get(tr.status, "?")
            finding_count = len(tr.findings)
            duration = f"{tr.duration_seconds:.1f}s"
            error_note = f" ({tr.error})" if tr.error else ""
            lines.append(
                f"| `{tr.tool}` | {icon} {tr.status.value}{error_note} "
                f"| {finding_count} | {duration} |"
            )

        lines.append("")
        lines.append("</details>")
        lines.append("")

    def _write_footer(self, lines: list[str]) -> None:
        lines.append("---")
        lines.append(
            "*Generated by [vibescan](https://github.com/vibescan/vibescan)*"
        )
        lines.append("")
