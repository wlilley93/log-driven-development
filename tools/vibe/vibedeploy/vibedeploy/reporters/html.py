"""Self-contained HTML reporter with deploy readiness dashboard."""

from __future__ import annotations

from rich.console import Console

from vibedeploy.models import Finding, Severity
from vibedeploy.reporters.base import BaseReporter

_SEVERITY_COLORS = {
    "CRITICAL": "#dc2626",
    "HIGH": "#f59e0b",
    "MEDIUM": "#6b7280",
    "LOW": "#9ca3af",
    "INFO": "#d1d5db",
}


class HtmlReporter(BaseReporter):
    """Self-contained HTML report with deploy readiness score."""

    def render(self, console: Console) -> None:
        console.print(self.render_to_string())

    def render_to_string(self) -> str:
        result = self.result
        score = result.readiness_score
        blockers = result.deploy_blockers
        counts = result.severity_counts

        # Score color
        if score >= 90:
            score_color = "#22c55e"
            status = "READY TO DEPLOY"
        elif score >= 70:
            score_color = "#f59e0b"
            status = "CAUTION"
        else:
            score_color = "#dc2626"
            status = "NOT READY"

        # Build severity cards
        sev_cards = ""
        for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
            count = counts.get(sev, 0)
            color = _SEVERITY_COLORS[sev]
            sev_cards += f"""
            <div class="card" style="border-left: 4px solid {color}">
                <div class="card-count" style="color: {color}">{count}</div>
                <div class="card-label">{sev}</div>
            </div>"""

        # Build blocker rows
        blocker_rows = ""
        for f in blockers:
            loc = f.file
            if f.line:
                loc += f":{f.line}"
            fix = f.fix_hint or ""
            blocker_rows += f"""
            <tr>
                <td><span class="badge" style="background: {_SEVERITY_COLORS.get(f.severity.value, '#666')}">{f.severity.value}</span></td>
                <td>{f.tool}</td>
                <td><code>{_esc(loc)}</code></td>
                <td>{_esc(f.message)}</td>
                <td>{_esc(fix)}</td>
            </tr>"""

        # Build finding rows (non-blocker)
        finding_rows = ""
        non_blockers = [f for f in result.deduplicated_findings if not f.blocks_deploy][:30]
        for f in non_blockers:
            loc = f.file
            if f.line:
                loc += f":{f.line}"
            finding_rows += f"""
            <tr>
                <td><span class="badge" style="background: {_SEVERITY_COLORS.get(f.severity.value, '#666')}">{f.severity.value}</span></td>
                <td>{f.tool}</td>
                <td><code>{_esc(loc)}</code></td>
                <td>{_esc(f.message[:120])}</td>
            </tr>"""

        # Build tool rows
        tool_rows = ""
        for tr in result.tool_results:
            icon = "\u2713" if tr.status.value in ("success", "partial") else "\u2717"
            status_class = "success" if tr.status.value in ("success", "partial") else "failed"
            tool_rows += f"""
            <tr>
                <td>{tr.tool}</td>
                <td class="{status_class}">{icon} {tr.status.value}</td>
                <td>{len(tr.findings)}</td>
                <td>{tr.duration_seconds:.1f}s</td>
            </tr>"""

        # Stack info
        stack_tags = ""
        if result.stack_info.get("tags"):
            tags = " ".join(f'<span class="tag">{t}</span>' for t in result.stack_info["tags"])
            stack_tags = f'<div class="stack-info">Stack: {tags}</div>'

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>vibedeploy Report — {_esc(result.target)}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0a0a0a; color: #e5e5e5; padding: 2rem; }}
.container {{ max-width: 1200px; margin: 0 auto; }}
h1 {{ font-size: 1.5rem; margin-bottom: 0.5rem; }}
h2 {{ font-size: 1.2rem; margin: 2rem 0 1rem; border-bottom: 1px solid #333; padding-bottom: 0.5rem; }}
.header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; }}
.score {{ font-size: 3rem; font-weight: bold; color: {score_color}; }}
.score-label {{ font-size: 0.9rem; color: #999; }}
.status {{ font-size: 1.2rem; font-weight: bold; color: {score_color}; }}
.meta {{ color: #999; font-size: 0.85rem; margin-top: 0.5rem; }}
.cards {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 1rem; margin: 1.5rem 0; }}
.card {{ background: #1a1a1a; padding: 1rem; border-radius: 8px; }}
.card-count {{ font-size: 2rem; font-weight: bold; }}
.card-label {{ font-size: 0.8rem; color: #999; text-transform: uppercase; }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
th {{ text-align: left; padding: 0.75rem; border-bottom: 2px solid #333; color: #999; font-weight: 600; }}
td {{ padding: 0.75rem; border-bottom: 1px solid #222; }}
tr:hover {{ background: #1a1a1a; }}
.badge {{ padding: 2px 8px; border-radius: 4px; color: white; font-size: 0.75rem; font-weight: 600; }}
code {{ background: #222; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; }}
.success {{ color: #22c55e; }}
.failed {{ color: #dc2626; }}
.tag {{ display: inline-block; background: #333; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; margin: 2px; }}
.stack-info {{ margin-top: 0.5rem; }}
@media (prefers-color-scheme: light) {{
  body {{ background: #fff; color: #1a1a1a; }}
  .card {{ background: #f5f5f5; }}
  th {{ border-bottom-color: #ddd; }}
  td {{ border-bottom-color: #eee; }}
  tr:hover {{ background: #f9f9f9; }}
  code {{ background: #f0f0f0; }}
  .tag {{ background: #e5e5e5; }}
}}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div>
      <h1>vibedeploy</h1>
      <div class="meta">{_esc(result.target)} &mdash; {result.timestamp}</div>
      {stack_tags}
    </div>
    <div style="text-align: right">
      <div class="score">{score}</div>
      <div class="score-label">/ 100</div>
      <div class="status">{status}</div>
    </div>
  </div>

  <div class="cards">{sev_cards}
  </div>

  {"<h2>Deploy Blockers (" + str(len(blockers)) + ")</h2>" if blockers else ""}
  {"<table><thead><tr><th>Severity</th><th>Tool</th><th>Location</th><th>Message</th><th>Fix</th></tr></thead><tbody>" + blocker_rows + "</tbody></table>" if blockers else ""}

  <h2>Findings</h2>
  <table>
    <thead><tr><th>Severity</th><th>Tool</th><th>Location</th><th>Message</th></tr></thead>
    <tbody>{finding_rows}</tbody>
  </table>

  <h2>Tool Coverage</h2>
  <table>
    <thead><tr><th>Tool</th><th>Status</th><th>Findings</th><th>Duration</th></tr></thead>
    <tbody>{tool_rows}</tbody>
  </table>

  <div class="meta" style="margin-top: 2rem; text-align: center">
    Generated by vibedeploy &mdash; {result.duration_seconds:.1f}s
  </div>
</div>
</body>
</html>"""


def _esc(text: str) -> str:
    """HTML-escape text."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
