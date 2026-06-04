"""Self-contained HTML reporter — single file with embedded CSS and JS."""

from __future__ import annotations

from rich.console import Console
from jinja2 import Template

from viberapid.config import Config
from viberapid.models import Finding, ScanResult, Severity
from viberapid.reporters.base import BaseReporter


# ---------------------------------------------------------------------------
# HTML template (Jinja2)
# ---------------------------------------------------------------------------
_HTML_TEMPLATE = Template(r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>viberapid report — {{ target }}</title>
<style>
  :root {
    --bg: #0d1117;
    --bg-card: #161b22;
    --fg: #e6edf3;
    --fg-secondary: #8b949e;
    --border: #30363d;
    --accent: #58a6ff;
    --accent-hover: #79c0ff;
    --critical: #f85149;
    --critical-bg: rgba(248,81,73,0.12);
    --high: #da3633;
    --high-bg: rgba(218,54,51,0.10);
    --medium: #d29922;
    --medium-bg: rgba(210,153,34,0.10);
    --low: #58a6ff;
    --low-bg: rgba(88,166,255,0.08);
    --info: #3fb950;
    --info-bg: rgba(63,185,80,0.08);
    --pass: #3fb950;
    --fail: #f85149;
    --radius: 8px;
    --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    --mono: "SF Mono", "Cascadia Code", "Fira Code", Consolas, monospace;
  }

  @media (prefers-color-scheme: light) {
    :root {
      --bg: #ffffff;
      --bg-card: #f6f8fa;
      --fg: #1f2328;
      --fg-secondary: #656d76;
      --border: #d0d7de;
      --accent: #0969da;
      --accent-hover: #0550ae;
      --critical: #cf222e;
      --critical-bg: rgba(207,34,46,0.08);
      --high: #cf222e;
      --high-bg: rgba(207,34,46,0.06);
      --medium: #9a6700;
      --medium-bg: rgba(154,103,0,0.08);
      --low: #0969da;
      --low-bg: rgba(9,105,218,0.06);
      --info: #1a7f37;
      --info-bg: rgba(26,127,55,0.06);
      --pass: #1a7f37;
      --fail: #cf222e;
    }
  }

  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: var(--font);
    background: var(--bg);
    color: var(--fg);
    line-height: 1.5;
    padding: 2rem;
    max-width: 1200px;
    margin: 0 auto;
  }

  h1 { font-size: 1.5rem; margin-bottom: 0.25rem; }
  h2 { font-size: 1.1rem; margin-bottom: 0.75rem; color: var(--fg); border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }
  h3 { font-size: 0.95rem; margin-bottom: 0.5rem; color: var(--fg-secondary); }

  .header { margin-bottom: 2rem; }
  .header .meta { color: var(--fg-secondary); font-size: 0.85rem; }

  .cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 0.75rem; margin-bottom: 2rem; }
  .card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1rem;
    text-align: center;
  }
  .card .count { font-size: 2rem; font-weight: 700; }
  .card .label { font-size: 0.75rem; text-transform: uppercase; color: var(--fg-secondary); letter-spacing: 0.05em; }
  .card.critical .count { color: var(--critical); }
  .card.high .count { color: var(--high); }
  .card.medium .count { color: var(--medium); }
  .card.low .count { color: var(--low); }
  .card.info .count { color: var(--info); }
  .card.total .count { color: var(--accent); }

  section { margin-bottom: 2rem; }

  .cwv-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 0.75rem; }
  .cwv-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1rem;
  }
  .cwv-card .metric-name { font-size: 0.75rem; text-transform: uppercase; color: var(--fg-secondary); }
  .cwv-card .metric-value { font-size: 1.5rem; font-weight: 700; }
  .cwv-card .metric-target { font-size: 0.75rem; color: var(--fg-secondary); }
  .cwv-card.pass .metric-value { color: var(--pass); }
  .cwv-card.fail .metric-value { color: var(--fail); }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
  }
  thead { background: var(--bg); }
  th {
    text-align: left;
    padding: 0.6rem 0.75rem;
    border-bottom: 1px solid var(--border);
    font-weight: 600;
    font-size: 0.75rem;
    text-transform: uppercase;
    color: var(--fg-secondary);
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
  }
  th:hover { color: var(--accent); }
  td { padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border); vertical-align: top; }
  tr:last-child td { border-bottom: none; }

  .sev-badge {
    display: inline-block;
    padding: 0.1rem 0.5rem;
    border-radius: 4px;
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }
  .sev-CRITICAL { background: var(--critical-bg); color: var(--critical); }
  .sev-HIGH { background: var(--high-bg); color: var(--high); }
  .sev-MEDIUM { background: var(--medium-bg); color: var(--medium); }
  .sev-LOW { background: var(--low-bg); color: var(--low); }
  .sev-INFO { background: var(--info-bg); color: var(--info); }

  .effort-LOW { color: var(--pass); }
  .effort-MEDIUM { color: var(--medium); }
  .effort-HIGH { color: var(--fail); }

  .pass-badge { color: var(--pass); font-weight: 700; }
  .fail-badge { color: var(--fail); font-weight: 700; }

  .qw-panel {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1rem;
  }
  .qw-item {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 0.5rem 0;
    border-bottom: 1px solid var(--border);
  }
  .qw-item:last-child { border-bottom: none; }
  .qw-rank { font-weight: 700; color: var(--accent); min-width: 1.5rem; }
  .qw-content { flex: 1; }
  .qw-meta { font-size: 0.75rem; color: var(--fg-secondary); margin-top: 0.25rem; }

  .roadmap-item {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.75rem 1rem;
    margin-bottom: 0.5rem;
  }
  .roadmap-priority { font-size: 0.7rem; font-weight: 700; text-transform: uppercase; }

  .gains-list { list-style: none; padding: 0; }
  .gains-list li { padding: 0.25rem 0; }
  .gains-list .category { font-weight: 600; color: var(--accent); }

  .empty { color: var(--fg-secondary); font-style: italic; padding: 1rem; }

  .footer { margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--border); color: var(--fg-secondary); font-size: 0.75rem; text-align: center; }
</style>
</head>
<body>

<!-- Header -->
<div class="header">
  <h1>viberapid</h1>
  <div class="meta">{{ target }} &mdash; {{ timestamp }} &mdash; Stack: {{ stack }} &mdash; {{ duration }}s &mdash; Exit {{ exit_code }}</div>
</div>

<!-- Executive Summary -->
<section>
  <h2>Executive Summary</h2>
  <div class="cards">
    <div class="card total"><div class="count">{{ total_findings }}</div><div class="label">Total</div></div>
    <div class="card critical"><div class="count">{{ counts.CRITICAL }}</div><div class="label">Critical</div></div>
    <div class="card high"><div class="count">{{ counts.HIGH }}</div><div class="label">High</div></div>
    <div class="card medium"><div class="count">{{ counts.MEDIUM }}</div><div class="label">Medium</div></div>
    <div class="card low"><div class="count">{{ counts.LOW }}</div><div class="label">Low</div></div>
    <div class="card info"><div class="count">{{ counts.INFO }}</div><div class="label">Info</div></div>
  </div>
</section>

{% if cwv_metrics %}
<!-- Core Web Vitals -->
<section>
  <h2>Core Web Vitals</h2>
  <div class="cwv-grid">
    {% for m in cwv_metrics %}
    <div class="cwv-card {{ 'pass' if m.passed else 'fail' }}">
      <div class="metric-name">{{ m.name }}</div>
      <div class="metric-value">{{ m.value }}{{ m.unit }}</div>
      {% if m.target %}<div class="metric-target">Target: {{ m.target }}{{ m.unit }}</div>{% endif %}
    </div>
    {% endfor %}
  </div>
</section>
{% endif %}

{% if load_results %}
<!-- Load Test Results -->
<section>
  <h2>Load Test Results</h2>
  <div class="cwv-grid">
    {% for m in load_results %}
    <div class="cwv-card {{ 'pass' if m.passed else 'fail' }}">
      <div class="metric-name">{{ m.name }}</div>
      <div class="metric-value">{{ m.value }}</div>
      <div class="metric-target">{{ m.label }}</div>
    </div>
    {% endfor %}
  </div>
</section>
{% endif %}

{% if quick_wins %}
<!-- Quick Wins -->
<section>
  <h2>Quick Wins</h2>
  <div class="qw-panel">
    {% for qw in quick_wins %}
    <div class="qw-item">
      <div class="qw-rank">{{ loop.index }}</div>
      <div class="qw-content">
        <span class="sev-badge sev-{{ qw.severity }}">{{ qw.severity }}</span>
        <strong>{{ qw.tool }}</strong>: {{ qw.message }}
        <div class="qw-meta">
          Effort: <span class="effort-{{ qw.effort }}">{{ qw.effort }}</span>
          {% if qw.saving %} &mdash; Saving: {{ qw.saving }}{% endif %}
          &mdash; Score: {{ qw.score }}
        </div>
      </div>
    </div>
    {% endfor %}
  </div>
</section>
{% endif %}

{% if bundle_findings %}
<!-- Bundle Composition -->
<section>
  <h2>Bundle Composition</h2>
  <table>
    <thead><tr><th>Package</th><th>Size</th><th>Tool</th><th>Message</th></tr></thead>
    <tbody>
    {% for f in bundle_findings %}
    <tr>
      <td>{{ f.file }}</td>
      <td>{% if f.metric %}{{ f.current_value }} {{ f.metric }}{% else %}-{% endif %}</td>
      <td>{{ f.tool }}</td>
      <td>{{ f.message }}</td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
</section>
{% endif %}

{% if css_findings %}
<!-- CSS Coverage -->
<section>
  <h2>CSS Coverage</h2>
  <table>
    <thead><tr><th>File</th><th>Tool</th><th>Message</th><th>Saving</th></tr></thead>
    <tbody>
    {% for f in css_findings %}
    <tr>
      <td>{{ f.file }}</td>
      <td>{{ f.tool }}</td>
      <td>{{ f.message }}</td>
      <td>{{ f.saving or '-' }}</td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
</section>
{% endif %}

{% if font_findings %}
<!-- Font Analysis -->
<section>
  <h2>Font Analysis</h2>
  <table>
    <thead><tr><th>File</th><th>Tool</th><th>Message</th><th>Saving</th></tr></thead>
    <tbody>
    {% for f in font_findings %}
    <tr>
      <td>{{ f.file }}</td>
      <td>{{ f.tool }}</td>
      <td>{{ f.message }}</td>
      <td>{{ f.saving or '-' }}</td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
</section>
{% endif %}

{% if compression_findings %}
<!-- Compression Headroom -->
<section>
  <h2>Compression Headroom</h2>
  <table>
    <thead><tr><th>File</th><th>Tool</th><th>Message</th><th>Saving</th></tr></thead>
    <tbody>
    {% for f in compression_findings %}
    <tr>
      <td>{{ f.file }}</td>
      <td>{{ f.tool }}</td>
      <td>{{ f.message }}</td>
      <td>{{ f.saving or '-' }}</td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
</section>
{% endif %}

{% if image_findings %}
<!-- Image Opportunities -->
<section>
  <h2>Image Opportunities</h2>
  <table>
    <thead><tr><th>File</th><th>Tool</th><th>Message</th><th>Saving</th></tr></thead>
    <tbody>
    {% for f in image_findings %}
    <tr>
      <td>{{ f.file }}</td>
      <td>{{ f.tool }}</td>
      <td>{{ f.message }}</td>
      <td>{{ f.saving or '-' }}</td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
</section>
{% endif %}

{% if db_findings %}
<!-- Database Findings -->
<section>
  <h2>Database Findings</h2>
  <table>
    <thead><tr><th>Sev</th><th>File</th><th>Line</th><th>Rule</th><th>Message</th></tr></thead>
    <tbody>
    {% for f in db_findings %}
    <tr>
      <td><span class="sev-badge sev-{{ f.severity }}">{{ f.severity }}</span></td>
      <td>{{ f.file }}</td>
      <td>{{ f.line or '-' }}</td>
      <td>{{ f.rule_id }}</td>
      <td>{{ f.message }}</td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
</section>
{% endif %}

{% if gains %}
<!-- Estimated Gains -->
<section>
  <h2>Estimated Gains from CRITICAL + HIGH Fixes</h2>
  <ul class="gains-list">
    {% for category, saving in gains.items() %}
    <li><span class="category">{{ category }}:</span> {{ saving }}</li>
    {% endfor %}
  </ul>
</section>
{% endif %}

<!-- Full Findings Table -->
<section>
  <h2>All Findings ({{ findings|length }})</h2>
  {% if findings %}
  <table id="findings-table">
    <thead>
      <tr>
        <th onclick="sortTable(0)">Sev</th>
        <th onclick="sortTable(1)">Tool</th>
        <th onclick="sortTable(2)">File</th>
        <th onclick="sortTable(3)">Line</th>
        <th onclick="sortTable(4)">Rule</th>
        <th onclick="sortTable(5)">Message</th>
        <th onclick="sortTable(6)">Metric</th>
        <th onclick="sortTable(7)">Effort</th>
        {% if show_fix %}<th>Fix</th>{% endif %}
      </tr>
    </thead>
    <tbody>
    {% for f in findings %}
    <tr>
      <td data-sort="{{ f.sev_rank }}"><span class="sev-badge sev-{{ f.severity }}">{{ f.severity }}</span></td>
      <td>{{ f.tools }}</td>
      <td>{{ f.file }}</td>
      <td>{{ f.line or '-' }}</td>
      <td>{{ f.rule_id }}</td>
      <td>{{ f.message }}</td>
      <td>{% if f.metric %}{{ f.metric }}{% if f.current_value is not none %}={{ f.current_value }}{% endif %}{% else %}-{% endif %}</td>
      <td><span class="effort-{{ f.effort }}">{{ f.effort }}</span></td>
      {% if show_fix %}<td>{{ f.fix_hint or '-' }}</td>{% endif %}
    </tr>
    {% endfor %}
    </tbody>
  </table>
  {% else %}
  <div class="empty">No findings.</div>
  {% endif %}
</section>

{% if budget_results %}
<!-- Budget Results -->
<section>
  <h2>Budget Results</h2>
  <table>
    <thead><tr><th>Metric</th><th>Current</th><th>Target</th><th>Unit</th><th>Status</th><th>Blocking</th></tr></thead>
    <tbody>
    {% for b in budget_results %}
    <tr>
      <td>{{ b.metric }}</td>
      <td>{{ b.current }}</td>
      <td>{{ b.target }}</td>
      <td>{{ b.unit }}</td>
      <td><span class="{{ 'pass-badge' if b.passed else 'fail-badge' }}">{{ 'PASS' if b.passed else 'FAIL' }}</span></td>
      <td>{{ 'yes' if b.fail_on_exceed else 'no' }}</td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
</section>
{% endif %}

{% if roadmap %}
<!-- Remediation Roadmap -->
<section>
  <h2>Remediation Roadmap</h2>
  {% for item in roadmap %}
  <div class="roadmap-item">
    <span class="roadmap-priority sev-badge sev-{{ item.severity }}">{{ item.severity }}</span>
    <strong>{{ item.tool }}</strong>: {{ item.message }}
    {% if item.fix_hint %}<div style="color: var(--fg-secondary); font-size: 0.8rem; margin-top: 0.25rem;">{{ item.fix_hint }}</div>{% endif %}
  </div>
  {% endfor %}
</section>
{% endif %}

<div class="footer">
  Generated by <strong>viberapid</strong> &mdash; the definitive performance analyser for AI-generated codebases
</div>

<!-- Sortable table JS -->
<script>
var sortDir = {};
function sortTable(col) {
  var table = document.getElementById("findings-table");
  if (!table) return;
  var tbody = table.querySelector("tbody");
  var rows = Array.from(tbody.querySelectorAll("tr"));
  var dir = sortDir[col] === "asc" ? "desc" : "asc";
  sortDir[col] = dir;

  rows.sort(function(a, b) {
    var cellA = a.cells[col];
    var cellB = b.cells[col];
    var valA = cellA.getAttribute("data-sort") || cellA.textContent.trim();
    var valB = cellB.getAttribute("data-sort") || cellB.textContent.trim();

    var numA = parseFloat(valA);
    var numB = parseFloat(valB);
    if (!isNaN(numA) && !isNaN(numB)) {
      return dir === "asc" ? numA - numB : numB - numA;
    }
    return dir === "asc" ? valA.localeCompare(valB) : valB.localeCompare(valA);
  });

  rows.forEach(function(row) { tbody.appendChild(row); });
}
</script>

</body>
</html>""")


# ---------------------------------------------------------------------------
# HTML Reporter
# ---------------------------------------------------------------------------
class HtmlReporter(BaseReporter):
    """Self-contained single-file HTML report."""

    def render(self, console: Console) -> None:
        """Render HTML and print a summary note to the console."""
        html = self.render_to_string()
        console.print(f"[dim]HTML report generated ({len(html)} bytes)[/dim]")

    def render_to_string(self) -> str:
        """Build the full HTML report string."""
        result = self.result
        config = self.config
        counts = result.severity_counts

        # -- Core Web Vitals --
        cwv_names = {"LCP", "FID", "INP", "CLS", "TTI", "TBT", "FCP", "TTFB", "SI"}
        cwv_targets = {
            "LCP": 2500, "FID": 100, "INP": 200, "CLS": 0.1,
            "TTI": 3800, "TBT": 200, "FCP": 1800, "TTFB": 800, "SI": 3400,
        }
        cwv_units = {
            "LCP": "ms", "FID": "ms", "INP": "ms", "CLS": "",
            "TTI": "ms", "TBT": "ms", "FCP": "ms", "TTFB": "ms", "SI": "ms",
        }

        cwv_metrics = []
        all_metrics = self._collect_metrics()
        for name in ["LCP", "FID", "INP", "CLS", "TTI", "TBT", "FCP", "TTFB", "SI"]:
            if name in all_metrics:
                val = all_metrics[name]
                target = cwv_targets.get(name)
                unit = cwv_units.get(name, "")
                if name == "CLS":
                    passed = val <= (target or 0.1)
                else:
                    passed = val <= (target or 99999)
                cwv_metrics.append({
                    "name": name,
                    "value": f"{val:.1f}" if isinstance(val, float) and val != int(val) else str(int(val)) if isinstance(val, float) else str(val),
                    "unit": unit,
                    "target": target,
                    "passed": passed,
                })

        # -- Load test results --
        load_names = {"rps", "rps_at_50_vus", "p50_latency_ms", "p95_latency_ms", "p99_latency_ms", "error_rate_pct"}
        load_results = []
        for name in ["rps_at_50_vus", "rps", "p50_latency_ms", "p95_latency_ms", "p99_latency_ms", "error_rate_pct"]:
            if name in all_metrics:
                val = all_metrics[name]
                labels = {
                    "rps_at_50_vus": "Requests/sec at 50 VUs",
                    "rps": "Requests/sec",
                    "p50_latency_ms": "p50 Latency",
                    "p95_latency_ms": "p95 Latency",
                    "p99_latency_ms": "p99 Latency",
                    "error_rate_pct": "Error Rate",
                }
                # For throughput higher is better; for latency/error lower is better
                if name in ("rps", "rps_at_50_vus"):
                    passed = val >= 100  # reasonable default
                elif name == "error_rate_pct":
                    passed = val <= 1.0
                else:
                    passed = val <= 500

                load_results.append({
                    "name": name,
                    "value": f"{val:.1f}" if isinstance(val, float) else str(val),
                    "label": labels.get(name, name),
                    "passed": passed,
                })

        # -- Quick wins --
        quick_wins = []
        for qw in result.quick_wins[:5]:
            quick_wins.append({
                "severity": qw.severity.value,
                "tool": qw.tool,
                "message": qw.message,
                "effort": qw.effort.value,
                "saving": qw.saving_estimate,
                "score": f"{qw.quick_win_score:.1f}",
            })

        # -- Category-specific findings --
        def _findings_for_category(cat_value: str) -> list[dict]:
            return [
                {
                    "file": f.file,
                    "tool": f.tool,
                    "message": f.message,
                    "metric": f.metric,
                    "current_value": f.current_value,
                    "saving": f.saving_estimate,
                    "severity": f.severity.value,
                    "line": f.line,
                    "rule_id": f.rule_id,
                }
                for f in result.deduplicated_findings
                if f.category.value == cat_value
            ]

        bundle_findings = _findings_for_category("BUNDLE")
        css_findings = _findings_for_category("CSS")
        font_findings = _findings_for_category("FONT")
        compression_findings = _findings_for_category("COMPRESSION")
        image_findings = _findings_for_category("ASSET")
        db_findings = _findings_for_category("DATABASE")

        # -- All findings --
        sev_rank = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "INFO": 0}
        findings = []
        for f in result.deduplicated_findings:
            findings.append({
                "severity": f.severity.value,
                "sev_rank": sev_rank.get(f.severity.value, 0),
                "tools": ", ".join(f.tools) if f.tools else f.tool,
                "file": f.file,
                "line": f.line,
                "rule_id": f.rule_id,
                "message": f.message,
                "metric": f.metric,
                "current_value": f.current_value,
                "effort": f.effort.value,
                "fix_hint": f.fix_hint,
            })

        # -- Budget results --
        budget_results = []
        for b in result.budget_results:
            budget_results.append({
                "metric": b.metric,
                "current": b.current,
                "target": b.target,
                "unit": b.unit,
                "passed": b.passed,
                "fail_on_exceed": b.fail_on_exceed,
            })

        # -- Estimated gains --
        gains = result.estimated_gains

        # -- Remediation roadmap (priority queue of CRITICAL/HIGH with fix hints) --
        roadmap = []
        for f in result.deduplicated_findings:
            if f.severity >= Severity.HIGH and f.fix_hint:
                roadmap.append({
                    "severity": f.severity.value,
                    "tool": f.tool,
                    "message": f.message,
                    "fix_hint": f.fix_hint,
                    "effort": f.effort.value,
                })

        return _HTML_TEMPLATE.render(
            target=result.target,
            timestamp=result.timestamp[:19].replace("T", " "),
            stack=result.stack,
            duration=f"{result.duration_seconds:.1f}",
            exit_code=result.exit_code,
            total_findings=sum(counts.values()),
            counts={
                "CRITICAL": counts.get("CRITICAL", 0),
                "HIGH": counts.get("HIGH", 0),
                "MEDIUM": counts.get("MEDIUM", 0),
                "LOW": counts.get("LOW", 0),
                "INFO": counts.get("INFO", 0),
            },
            cwv_metrics=cwv_metrics,
            load_results=load_results,
            quick_wins=quick_wins,
            bundle_findings=bundle_findings,
            css_findings=css_findings,
            font_findings=font_findings,
            compression_findings=compression_findings,
            image_findings=image_findings,
            db_findings=db_findings,
            gains=gains,
            findings=findings,
            budget_results=budget_results,
            roadmap=roadmap,
            show_fix=config.fix,
        )

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
