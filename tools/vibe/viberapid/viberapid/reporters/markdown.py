"""Markdown reporter — GitHub PR comment format."""

from __future__ import annotations

from io import StringIO

from rich.console import Console

from viberapid.config import Config
from viberapid.models import Finding, ScanResult, Severity
from viberapid.reporters.base import BaseReporter


class MarkdownReporter(BaseReporter):
    """Markdown output suitable for GitHub PR comments."""

    def render(self, console: Console) -> None:
        """Print markdown to the console."""
        md = self.render_to_string()
        console.print(md, highlight=False)

    def render_to_string(self) -> str:
        """Build the full markdown report string."""
        lines: list[str] = []
        result = self.result
        config = self.config
        counts = result.severity_counts
        total = sum(counts.values())

        # -- Title --
        lines.append("## viberapid Performance Report")
        lines.append("")
        lines.append(
            f"**Target:** `{result.target}` | "
            f"**Stack:** {result.stack} | "
            f"**Duration:** {result.duration_seconds:.1f}s | "
            f"**Exit:** {result.exit_code}"
        )
        lines.append("")

        # -- Summary table --
        lines.append("### Summary")
        lines.append("")
        lines.append("| Severity | Count |")
        lines.append("|----------|------:|")
        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
            count = counts.get(sev, 0)
            icon = _severity_icon(sev)
            lines.append(f"| {icon} {sev} | {count} |")
        lines.append(f"| **Total** | **{total}** |")
        lines.append("")

        # -- Core Web Vitals delta --
        all_metrics = self._collect_metrics()
        cwv_names = ["LCP", "FID", "INP", "CLS", "TTI", "TBT"]
        cwv_data = {n: all_metrics[n] for n in cwv_names if n in all_metrics}

        if cwv_data:
            lines.append("### Core Web Vitals")
            lines.append("")
            cwv_targets = {
                "LCP": 2500, "FID": 100, "INP": 200, "CLS": 0.1,
                "TTI": 3800, "TBT": 200,
            }
            cwv_units = {
                "LCP": "ms", "FID": "ms", "INP": "ms", "CLS": "",
                "TTI": "ms", "TBT": "ms",
            }

            lines.append("| Metric | Value | Target | Status |")
            lines.append("|--------|------:|-------:|--------|")
            for name, value in cwv_data.items():
                target = cwv_targets.get(name, "-")
                unit = cwv_units.get(name, "")
                if isinstance(target, (int, float)):
                    if name == "CLS":
                        passed = value <= target
                    else:
                        passed = value <= target
                    status = "PASS" if passed else "FAIL"
                    status_icon = _status_icon(passed)
                else:
                    status_icon = ""
                    status = "-"

                val_str = f"{value:.2f}" if isinstance(value, float) and name == "CLS" else f"{value:.0f}"
                target_str = f"{target}" if target != "-" else "-"
                lines.append(f"| {name} | {val_str}{unit} | {target_str}{unit} | {status_icon} {status} |")
            lines.append("")

        # -- Load test summary --
        load_keys = ["rps_at_50_vus", "rps", "p50_latency_ms", "p95_latency_ms", "p99_latency_ms", "error_rate_pct"]
        load_data = {k: all_metrics[k] for k in load_keys if k in all_metrics}

        if load_data:
            lines.append("### Load Test Results")
            lines.append("")
            lines.append("| Metric | Value |")
            lines.append("|--------|------:|")
            labels = {
                "rps_at_50_vus": "RPS (50 VUs)",
                "rps": "Requests/sec",
                "p50_latency_ms": "p50 Latency (ms)",
                "p95_latency_ms": "p95 Latency (ms)",
                "p99_latency_ms": "p99 Latency (ms)",
                "error_rate_pct": "Error Rate (%)",
            }
            for k, v in load_data.items():
                label = labels.get(k, k)
                val_str = f"{v:.1f}" if isinstance(v, float) else str(v)
                lines.append(f"| {label} | {val_str} |")
            lines.append("")

        # -- Quick wins --
        if result.quick_wins:
            lines.append("### Quick Wins")
            lines.append("")
            for i, qw in enumerate(result.quick_wins[:5], 1):
                icon = _severity_icon(qw.severity.value)
                saving = f" -- saving: {qw.saving_estimate}" if qw.saving_estimate else ""
                lines.append(
                    f"{i}. {icon} **{qw.tool}**: {qw.message} "
                    f"(effort: {qw.effort.value}{saving})"
                )
            lines.append("")

        # -- Budget status --
        if result.budget_results:
            lines.append("### Budget Status")
            lines.append("")
            lines.append("| Metric | Current | Target | Unit | Status |")
            lines.append("|--------|--------:|-------:|------|--------|")
            for b in result.budget_results:
                status_icon = _status_icon(b.passed)
                status = "PASS" if b.passed else "FAIL"
                blocking = " (blocking)" if b.fail_on_exceed and not b.passed else ""
                lines.append(
                    f"| {b.metric} | {b.current} | {b.target} | {b.unit} | {status_icon} {status}{blocking} |"
                )
            lines.append("")

        # -- Estimated gains --
        gains = result.estimated_gains
        if gains:
            lines.append("### Estimated Gains")
            lines.append("")
            for category, saving in gains.items():
                lines.append(f"- **{category}**: {saving}")
            lines.append("")

        # -- Full findings table --
        if result.deduplicated_findings:
            lines.append("### Findings")
            lines.append("")

            use_details = len(result.deduplicated_findings) > 10

            if use_details:
                lines.append(f"<details><summary>{total} findings (click to expand)</summary>")
                lines.append("")

            lines.append("| Sev | Tool | File | Line | Rule | Message |")
            lines.append("|-----|------|------|-----:|------|---------|")

            for f in result.deduplicated_findings:
                icon = _severity_icon(f.severity.value)
                tools = ", ".join(f.tools) if f.tools else f.tool
                line_str = str(f.line) if f.line else "-"
                # Escape pipe characters in message
                msg = f.message.replace("|", "\\|")[:80]
                lines.append(
                    f"| {icon} {f.severity.value} | {tools} | `{f.file}` | {line_str} | {f.rule_id} | {msg} |"
                )

            if use_details:
                lines.append("")
                lines.append("</details>")

            lines.append("")

        # -- Footer --
        lines.append("---")
        lines.append(
            "*Generated by [viberapid](https://github.com/viberapid/viberapid) "
            "-- the definitive performance analyser for AI-generated codebases*"
        )
        lines.append("")

        return "\n".join(lines)

    def _collect_metrics(self) -> dict[str, float]:
        """Gather all numeric metrics from tool results and findings."""
        metrics: dict[str, float] = {}
        for tr in self.result.tool_results:
            for k, v in tr.metrics.items():
                if isinstance(v, (int, float)):
                    metrics[k] = float(v)
        for f in self.result.deduplicated_findings:
            if f.metric and f.current_value is not None:
                metrics[f.metric] = f.current_value
        return metrics


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _severity_icon(sev: str) -> str:
    """Return an emoji icon for severity level."""
    return {
        "CRITICAL": "\U0001f534",  # red circle
        "HIGH": "\U0001f7e0",      # orange circle
        "MEDIUM": "\U0001f7e1",    # yellow circle
        "LOW": "\U0001f535",       # blue circle
        "INFO": "\u2139\ufe0f",    # info
    }.get(sev, "\u2022")


def _status_icon(passed: bool) -> str:
    """Return a checkmark or cross icon."""
    return "\u2705" if passed else "\u274c"
