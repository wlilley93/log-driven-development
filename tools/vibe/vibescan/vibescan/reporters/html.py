"""Self-contained single-file HTML reporter."""

from __future__ import annotations

from rich.console import Console
from jinja2 import Template

from vibescan.config import Config
from vibescan.models import Finding, ScanResult, Severity, ToolStatus
from vibescan.reporters.base import BaseReporter

_SEVERITY_ORDER = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]

_SEVERITY_COLORS = {
    "CRITICAL": "#dc2626",
    "HIGH": "#ea580c",
    "MEDIUM": "#ca8a04",
    "LOW": "#2563eb",
    "INFO": "#6b7280",
}

_STATUS_LABELS = {
    ToolStatus.SUCCESS: ("Success", "#16a34a"),
    ToolStatus.PARTIAL: ("Partial", "#ca8a04"),
    ToolStatus.FAILED: ("Failed", "#dc2626"),
    ToolStatus.SKIPPED: ("Skipped", "#6b7280"),
    ToolStatus.TIMEOUT: ("Timeout", "#dc2626"),
}

# ship-safe-ignore: jinja2 template with inline styles, not user-facing secret
_HTML_TEMPLATE = Template('''\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>vibescan report &mdash; {{ target }}</title>
<style>
  :root {
    --bg: #ffffff; --bg-alt: #f8fafc; --fg: #1e293b; --fg-dim: #64748b;
    --border: #e2e8f0; --accent: #3b82f6;
    --critical: #dc2626; --high: #ea580c; --medium: #ca8a04;
    --low: #2563eb; --info: #6b7280;
    --radius: 8px; --shadow: 0 1px 3px rgba(0,0,0,.08);
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #0f172a; --bg-alt: #1e293b; --fg: #e2e8f0; --fg-dim: #94a3b8;
      --border: #334155; --accent: #60a5fa;
      --shadow: 0 1px 3px rgba(0,0,0,.3);
    }
  }
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, sans-serif;
    background: var(--bg); color: var(--fg); line-height: 1.6;
    padding: 2rem; max-width: 1200px; margin: 0 auto;
  }
  h1 { font-size: 1.5rem; font-weight: 700; margin-bottom: .25rem; }
  h2 { font-size: 1.15rem; font-weight: 600; margin: 2rem 0 .75rem; color: var(--fg); }
  .subtitle { color: var(--fg-dim); font-size: .875rem; margin-bottom: 1.5rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: .75rem; margin-bottom: 1.5rem; }
  .card {
    background: var(--bg-alt); border: 1px solid var(--border); border-radius: var(--radius);
    padding: 1rem; text-align: center; box-shadow: var(--shadow);
  }
  .card .count { font-size: 2rem; font-weight: 700; line-height: 1.2; }
  .card .label { font-size: .75rem; text-transform: uppercase; letter-spacing: .05em; color: var(--fg-dim); }
  .sev-critical .count { color: var(--critical); }
  .sev-high .count { color: var(--high); }
  .sev-medium .count { color: var(--medium); }
  .sev-low .count { color: var(--low); }
  .sev-info .count { color: var(--info); }
  table { width: 100%; border-collapse: collapse; font-size: .875rem; margin-bottom: 1rem; }
  th, td { padding: .5rem .75rem; text-align: left; border-bottom: 1px solid var(--border); }
  th { background: var(--bg-alt); font-weight: 600; position: sticky; top: 0; cursor: pointer; user-select: none; white-space: nowrap; }
  th:hover { color: var(--accent); }
  th .arrow { font-size: .7rem; margin-left: .25rem; opacity: .4; }
  th .arrow.active { opacity: 1; }
  tr:hover td { background: var(--bg-alt); }
  .badge {
    display: inline-block; padding: .125rem .5rem; border-radius: 999px;
    font-size: .75rem; font-weight: 600; color: #fff;
  }
  .badge-critical { background: var(--critical); }
  .badge-high { background: var(--high); }
  .badge-medium { background: var(--medium); }
  .badge-low { background: var(--low); }
  .badge-info { background: var(--info); }
  .status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: .375rem; vertical-align: middle; }
  .mono { font-family: "SF Mono", "Cascadia Code", "Fira Code", Consolas, monospace; font-size: .8125rem; }
  .hint { color: var(--fg-dim); font-size: .8125rem; margin-top: .25rem; font-style: italic; }
  .cve-link { color: var(--accent); text-decoration: none; }
  .cve-link:hover { text-decoration: underline; }
  .exit-pass { color: #16a34a; font-weight: 700; }
  .exit-fail { color: var(--critical); font-weight: 700; }
  footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--border); color: var(--fg-dim); font-size: .75rem; text-align: center; }
  .section { margin-bottom: 2rem; }
  .detail-row td { padding: .75rem; }
  .finding-meta { display: flex; gap: 1rem; flex-wrap: wrap; margin-top: .25rem; }
  .finding-meta span { color: var(--fg-dim); font-size: .8125rem; }
  .empty { text-align: center; padding: 2rem; color: var(--fg-dim); }
</style>
</head>
<body>

<h1>vibescan report</h1>
<p class="subtitle">{{ target }} &mdash; {{ timestamp }} &mdash; {{ duration }}s total</p>

<!-- Severity summary cards -->
<div class="grid">
{% for sev in severities %}
  <div class="card sev-{{ sev.lower }}">
    <div class="count">{{ counts[sev.name] }}</div>
    <div class="label">{{ sev.name }}</div>
  </div>
{% endfor %}
  <div class="card">
    <div class="count" style="color: var(--accent)">{{ total_findings }}</div>
    <div class="label">Total</div>
  </div>
</div>

<!-- Tool coverage -->
<h2>Tool Coverage</h2>
<div class="section">
<table>
  <thead><tr><th>Tool</th><th>Status</th><th>Findings</th><th>Duration</th></tr></thead>
  <tbody>
  {% for tr in tool_results %}
    <tr>
      <td class="mono">{{ tr.tool }}</td>
      <td><span class="status-dot" style="background:{{ tr.status_color }}"></span>{{ tr.status_label }}</td>
      <td>{{ tr.finding_count }}</td>
      <td>{{ tr.duration }}s</td>
    </tr>
  {% endfor %}
  </tbody>
</table>
</div>

<!-- Findings table -->
<h2>Findings ({{ total_findings }})</h2>
<div class="section">
{% if findings %}
<table id="findings-table">
  <thead>
    <tr>
      <th onclick="sortTable(0)">Severity <span class="arrow" id="arrow-0">&#x25B2;</span></th>
      <th onclick="sortTable(1)">Tool <span class="arrow" id="arrow-1">&#x25B2;</span></th>
      <th onclick="sortTable(2)">File <span class="arrow" id="arrow-2">&#x25B2;</span></th>
      <th onclick="sortTable(3)">Rule <span class="arrow" id="arrow-3">&#x25B2;</span></th>
      <th>Message</th>
    </tr>
  </thead>
  <tbody>
  {% for f in findings %}
    <tr>
      <td><span class="badge badge-{{ f.severity_lower }}">{{ f.severity }}</span></td>
      <td class="mono">{{ f.tool }}</td>
      <td class="mono">{{ f.location }}</td>
      <td class="mono">{{ f.rule_id }}</td>
      <td>
        {{ f.message }}
        {% if f.cve %}<br><a class="cve-link" href="https://nvd.nist.gov/vuln/detail/{{ f.cve }}" target="_blank" rel="noopener">{{ f.cve }}</a>{% if f.cvss %} (CVSS {{ f.cvss }}){% endif %}{% endif %}
        {% if f.fix_hint %}<div class="hint">Fix: {{ f.fix_hint }}</div>{% endif %}
        <div class="finding-meta">
          {% if f.category %}<span>{{ f.category }}</span>{% endif %}
          {% if f.tools_list %}<span>Also found by: {{ f.tools_list }}</span>{% endif %}
        </div>
      </td>
    </tr>
  {% endfor %}
  </tbody>
</table>
{% else %}
<div class="empty">No findings detected.</div>
{% endif %}
</div>

<!-- Licence inventory -->
{% if licence_findings %}
<h2>Licence Inventory</h2>
<div class="section">
<table>
  <thead><tr><th>File / Package</th><th>Licence</th><th>Severity</th><th>Message</th></tr></thead>
  <tbody>
  {% for f in licence_findings %}
    <tr>
      <td class="mono">{{ f.file }}</td>
      <td>{{ f.licence or "Unknown" }}</td>
      <td><span class="badge badge-{{ f.severity_lower }}">{{ f.severity }}</span></td>
      <td>{{ f.message }}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>
</div>
{% endif %}

<!-- Remediation priority -->
{% if priority_findings %}
<h2>Remediation Priority (Top 10)</h2>
<div class="section">
<table>
  <thead><tr><th>#</th><th>Severity</th><th>File</th><th>Rule</th><th>Message</th><th>Fix</th></tr></thead>
  <tbody>
  {% for i, f in priority_findings %}
    <tr>
      <td>{{ i }}</td>
      <td><span class="badge badge-{{ f.severity_lower }}">{{ f.severity }}</span></td>
      <td class="mono">{{ f.location }}</td>
      <td class="mono">{{ f.rule_id }}</td>
      <td>{{ f.message }}</td>
      <td>{{ f.fix_hint or "&mdash;" }}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>
</div>
{% endif %}

<footer>
  Exit code: <span class="{{ 'exit-pass' if exit_code == 0 else 'exit-fail' }}">{{ exit_code }}</span>
  &mdash; Generated by <strong>vibescan</strong>
</footer>

<script>
(function(){
  var sortState = {};
  var sevOrder = {CRITICAL:4,HIGH:3,MEDIUM:2,LOW:1,INFO:0};
  window.sortTable = function(col) {
    var table = document.getElementById("findings-table");
    if (!table) return;
    var tbody = table.querySelector("tbody");
    var rows = Array.from(tbody.querySelectorAll("tr"));
    var dir = sortState[col] === "asc" ? "desc" : "asc";
    sortState[col] = dir;
    rows.sort(function(a, b) {
      var at = a.cells[col].textContent.trim();
      var bt = b.cells[col].textContent.trim();
      if (col === 0) { at = sevOrder[at]||0; bt = sevOrder[bt]||0; return dir==="asc"?at-bt:bt-at; }
      return dir==="asc" ? at.localeCompare(bt) : bt.localeCompare(at);
    });
    rows.forEach(function(r){ tbody.appendChild(r); });
    document.querySelectorAll(".arrow").forEach(function(a){ a.classList.remove("active"); });
    var arrow = document.getElementById("arrow-"+col);
    if(arrow){ arrow.classList.add("active"); arrow.innerHTML = dir==="asc"?"&#x25B2;":"&#x25BC;"; }
  };
})();
</script>
</body>
</html>
''', autoescape=True)


class _FindingView:
    """Template-friendly finding wrapper."""

    __slots__ = (
        "severity", "severity_lower", "tool", "file", "location",
        "rule_id", "rule_name", "message", "fix_hint", "cve", "cvss",
        "category", "licence", "tools_list",
    )

    def __init__(self, f: Finding):
        self.severity = f.severity.value
        self.severity_lower = f.severity.value.lower()
        self.tool = f.tool
        self.file = f.file
        self.location = f.file + (f":{f.line}" if f.line else "")
        self.rule_id = f.rule_id
        self.rule_name = f.rule_name
        self.message = f.message
        self.fix_hint = f.fix_hint
        self.cve = f.cve
        self.cvss = f.cvss
        self.category = f.category.value if f.category else None
        self.licence = f.licence
        self.tools_list = ", ".join(f.tools) if f.tools else None


class _SeverityInfo:
    __slots__ = ("name", "lower")

    def __init__(self, sev: Severity):
        self.name = sev.value
        self.lower = sev.value.lower()


class HtmlReporter(BaseReporter):
    """Self-contained single-file HTML report."""

    def __init__(self, result: ScanResult, config: Config):
        super().__init__(result, config)

    def render(self, console: Console) -> None:
        html = self.render_to_string()
        console.print(html, highlight=False, markup=False)

    def render_to_string(self) -> str:
        findings = sorted(
            self.result.deduplicated_findings,
            key=lambda f: f.severity.rank,
            reverse=True,
        )
        finding_views = [_FindingView(f) for f in findings]

        licence_findings = [
            _FindingView(f) for f in findings
            if f.category and f.category.value == "LICENCE"
        ]

        priority = findings[:10]
        priority_views = [(i + 1, _FindingView(f)) for i, f in enumerate(priority)]

        tool_results = []
        for tr in self.result.tool_results:
            label, color = _STATUS_LABELS.get(tr.status, ("Unknown", "#6b7280"))
            tool_results.append({
                "tool": tr.tool,
                "status_label": label,
                "status_color": color,
                "finding_count": len(tr.findings),
                "duration": f"{tr.duration_seconds:.1f}",
            })

        counts = self.result.severity_counts

        return _HTML_TEMPLATE.render(
            target=self.result.target,
            timestamp=self.result.timestamp,
            duration=f"{self.result.duration_seconds:.1f}",
            severities=[_SeverityInfo(s) for s in _SEVERITY_ORDER],
            counts=counts,
            total_findings=len(findings),
            tool_results=tool_results,
            findings=finding_views,
            licence_findings=licence_findings,
            priority_findings=priority_views,
            exit_code=self.result.exit_code,
        )
