# viberapid

**The definitive performance analyser for AI-generated codebases.**

[![PyPI](https://img.shields.io/pypi/v/viberapid?color=blue)](https://pypi.org/project/viberapid/)
[![Python](https://img.shields.io/pypi/pyversions/viberapid)](https://pypi.org/project/viberapid/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

viberapid orchestrates **65 open-source performance tools** across 13 categories, normalises their output into a unified Finding schema, deduplicates cross-tool overlap, computes quick wins, checks performance budgets, and outputs results via 4 formatters.

```
$ viberapid .

  viberapid scan — 42 tools ran in 18.3s

  Severity   Count
  CRITICAL       2
  HIGH           7
  MEDIUM        14
  LOW           23

  Top 5 Quick Wins:
  1. [HIGH]  js-large-import  lodash full import adds ~72 kB    src/utils.ts:3     effort: LOW
  2. [HIGH]  purgecss         1,240 unused CSS selectors         app/globals.css    effort: LOW
  3. [CRIT]  lighthouse       LCP 4.2s (target: 2.5s)           —                  effort: MED
  4. [MED]   gzip-size        main.js: 380 kB uncompressed       dist/main.js       effort: LOW
  5. [HIGH]  depcheck         3 unused dependencies              package.json       effort: LOW

  Budget: 6/8 passed, 2 exceeded (LCP, total_js)
  Exit code: 1
```

---

## Why viberapid?

- **AI-generated ("vibe-coded") projects ship fast but skip performance.** Copilot, Cursor, and ChatGPT produce working code that often bundles too much, skips caching, and creates N+1 queries — all invisible until production.
- **60+ performance tools exist, but no unified runner.** Each has its own install, config, output format, and severity scale. Running them manually on every PR is impractical.
- **Manual triage is slow.** When multiple tools flag the same file or pattern, you waste time on duplicates. viberapid deduplicates findings across tools and ranks them by impact-to-effort ratio so you fix what matters first.
- **CI gates need numbers, not opinions.** viberapid checks measured metrics against a performance budget and exits non-zero when thresholds are exceeded — no subjective judgment required.

---

## Quickstart

```bash
# Install viberapid
pip install viberapid

# Install all underlying performance tools
viberapid install

# Scan the current directory
viberapid .

# Re-render the last scan as HTML
viberapid report --last --output html
```

Requires **Python 3.11+**. Node.js 18+ is needed for JS/CSS tools; viberapid can manage a local Node environment automatically via `nodeenv`.

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `viberapid [TARGET_DIR]` | Run a full performance scan on a directory (defaults to `.`) |
| `viberapid install` | Install or update all underlying tools (`--check` to show status only) |
| `viberapid report` | Re-render last scan or show trend data (`--last`, `--trend`) |
| `viberapid budget` | View or scaffold a performance budget file (`--create`) |
| `viberapid diff <git-ref>` | Compare current scan against a previous baseline, showing regressions and improvements |
| `viberapid load --url <URL>` | Run load tests only against a target URL |

---

## Key Options

| Flag | Description | Default |
|------|-------------|---------|
| `--tools <list>` | Comma-separated list of tools to run | all applicable |
| `--skip <list>` | Comma-separated list of tools to skip | none |
| `--fail-on <severity>` | Exit non-zero if findings at or above this severity | `high` |
| `--output <format>` | Output format: `table`, `json`, `html`, `md` | `table` |
| `--output-file <path>` | Write report to a file instead of stdout | stdout |
| `--ship-fast` | Strict CI mode — minimal one-line output | off |
| `--url <URL>` | Target URL for Lighthouse, load tests, network tools | none |
| `--since <git-ref>` | Only scan files changed since this git ref | none |
| `--threads <n>` | Number of parallel tool threads | CPU count |
| `--timeout <secs>` | Per-tool timeout in seconds | `120` |
| `--budget <path>` | Path to a performance budget JSON file | `.viberapid-budget.json` |
| `--stack <type>` | Project stack: `auto`, `node`, `python`, `fullstack` | `auto` |
| `--fix` | Include remediation hints in output | off |
| `--quiet` | Suppress progress output | off |
| `--verbose` | Verbose output with tool-level detail | off |

---

## Tool Coverage

viberapid ships with **65 tool runners** across **13 categories**. Tools are selected automatically based on your detected stack. Each tool normalises its output into a unified `Finding` schema with severity, category, effort estimate, and optional fix hints.

### Bundle & JS (14 tools)

| Tool | What it checks | Install via |
|------|---------------|-------------|
| depcheck | Unused and missing npm dependencies | npm |
| knip | Unused files, exports, and dependencies | npm |
| jscpd | Copy/paste (duplicated code) detection | npm |
| bundlephobia | npm package bundle sizes (min + gzip) | npm |
| cost-of-modules | Disk cost of node_modules | npm |
| size-limit | Bundle size budget enforcement | npm |
| bundle-analyzer | Webpack stats analysis for large chunks | npm |
| source-map-explorer | Bundle composition via source maps | npm |
| bundlewatch | Bundle size limit checking | npm |
| esbuild-bench | Dist size compared to esbuild baseline | npm |
| webpack-deadcode | Unused files and exports in webpack builds | npm |
| npm-check | Outdated, unused, and mismatched packages | npm |
| npm-check-updates | Outdated npm dependency versions | npm |
| duplicate-packages | Packages at multiple versions in lockfile | npm |

### CSS (6 tools)

| Tool | What it checks | Install via |
|------|---------------|-------------|
| purgecss | Unused CSS selectors | npm |
| cssnano | CSS minification headroom (dry-run) | npm |
| parker | CSS specificity and complexity metrics | npm |
| stylestats | CSS complexity and quality statistics | npm |
| uncss | Unused CSS rules by rendering pages | npm |
| stylelint-perf | Performance-focused CSS linting rules | npm |

### Fonts (2 tools)

| Tool | What it checks | Install via |
|------|---------------|-------------|
| glyphhanger | Font usage analysis and subsetting opportunities | npm |
| fonttools | Font file analysis (size, glyph count, format) | pip |

### Images (3 tools)

| Tool | What it checks | Install via |
|------|---------------|-------------|
| svgo | SVG optimisation opportunities | npm |
| imagemin | Image file size analysis | npm |
| sharp-check | Oversized image metadata and dimension analysis | npm |

### Compression (3 tools)

| Tool | What it checks | Install via |
|------|---------------|-------------|
| gzip-size | Gzip compression ratios for JS/CSS files | npm |
| brotli-size | Brotli compression headroom over gzip | npm/pip |
| zopfli | Compression headroom vs standard gzip | binary |

### HTTP & Network (7 tools)

| Tool | What it checks | Install via |
|------|---------------|-------------|
| lighthouse | Core Web Vitals, performance, best practices | npm |
| webhint | Web best practices, security headers, compatibility | npm |
| sitespeed | Web performance metrics and budget checking | npm |
| psi | PageSpeed Insights CrUX field data and lab metrics | npm |
| h2spec | HTTP/2 protocol compliance validation | binary |
| yellowlab | DOM complexity, CSS weight, JS execution audit | npm |
| hstspreload | HSTS header validation for preload list eligibility | npm |

### Load Testing (8 tools)

| Tool | What it checks | Install via |
|------|---------------|-------------|
| k6 | Scriptable load testing (Grafana Labs) | binary |
| artillery | Cloud-scale load testing with scenarios | npm |
| autocannon | Fast HTTP benchmarking for Node.js | npm |
| wrk | Modern HTTP benchmarking with Lua scripting | binary |
| vegeta | Constant-rate HTTP load testing | binary |
| bombardier | Fast cross-platform HTTP benchmarking | binary |
| hyperfine | Command-line benchmarking (startup time, etc.) | binary |
| locust | Python-based load testing with user scenarios | pip |

### Database (6 tools)

| Tool | What it checks | Install via |
|------|---------------|-------------|
| sqlfluff | SQL file linting for anti-patterns and style | pip |
| pghero | PostgreSQL performance diagnostics (missing indexes, slow queries) | pip |
| pgbadger | PostgreSQL log analysis for slow query patterns | binary |
| pt_query_digest | MySQL slow query log analysis (Percona Toolkit) | binary |
| django_check | Django deployment and configuration checks | pip |
| prisma_inspector | N+1 patterns in Prisma ORM schemas | built-in |

### Python Runtime (7 tools)

| Tool | What it checks | Install via |
|------|---------------|-------------|
| scalene | CPU and memory profiling | pip |
| pyinstrument | Statistical profiling with call trees | pip |
| py-spy | Sampling profiler with flamegraphs | pip |
| memray | Memory allocation hotspots and peak usage | pip |
| fil | Peak memory spike detection | pip |
| austin | Frame stack sampling with near-zero overhead | binary |
| speedscope | Flamegraph viewer from profiler outputs | npm |

### Node Runtime (3 tools)

| Tool | What it checks | Install via |
|------|---------------|-------------|
| clinic | Node.js event loop, CPU, memory diagnostics | npm |
| 0x | Single-command flamegraph profiling | npm |
| node-prof | V8 built-in profiler with tick processor | built-in |

### React (3 tools)

| Tool | What it checks | Install via |
|------|---------------|-------------|
| million-lint | Static analysis of React rendering performance | npm |
| react-scan | Automatic detection of unnecessary re-renders | npm |
| why-did-you-render | React re-render logging and analysis | npm |

### Dependencies (2 tools)

| Tool | What it checks | Install via |
|------|---------------|-------------|
| pipdeptree | Python dependency tree analysis | pip |
| deptry | Unused, missing, and transitive Python dependencies | pip |

### Custom AST (1 tool)

| Tool | What it checks | Install via |
|------|---------------|-------------|
| ast-analyser | 12 custom performance rules for Python and JS/TS | built-in |

---

## Performance Budget

viberapid supports performance budgets — numeric thresholds for key metrics that can fail your CI pipeline when exceeded.

### Create a budget file

```bash
viberapid budget --create
```

This scaffolds `.viberapid-budget.json` with sensible defaults:

```json
{
  "metrics": {
    "LCP": { "target": 2500, "unit": "ms", "fail_on_exceed": true },
    "FID": { "target": 100, "unit": "ms", "fail_on_exceed": true },
    "CLS": { "target": 0.1, "unit": "score", "fail_on_exceed": true },
    "TTI": { "target": 3800, "unit": "ms", "fail_on_exceed": true },
    "TBT": { "target": 200, "unit": "ms", "fail_on_exceed": true },
    "p99_latency_ms": { "target": 500, "unit": "ms", "fail_on_exceed": true },
    "error_rate_pct": { "target": 1.0, "unit": "%", "fail_on_exceed": true },
    "rps_at_50_vus": { "target": 100, "unit": "req/s", "fail_on_exceed": false }
  },
  "bundles": {
    "total_js": { "target": 300, "unit": "kB", "fail_on_exceed": true },
    "total_css": { "target": 50, "unit": "kB", "fail_on_exceed": true },
    "largest_image": { "target": 200, "unit": "kB", "fail_on_exceed": false },
    "largest_font": { "target": 100, "unit": "kB", "fail_on_exceed": false }
  }
}
```

### How it works

1. Tools emit metrics as part of their findings (e.g., Lighthouse reports LCP, load testers report p99 latency).
2. After all tools run, viberapid compares measured values against your budget thresholds.
3. Metrics with `"fail_on_exceed": true` that exceed their target cause a non-zero exit code.
4. For throughput metrics like `rps_at_50_vus`, falling **below** the target triggers a failure (higher is better).

### Run with a budget

```bash
# Uses .viberapid-budget.json in the target directory by default
viberapid .

# Or specify a custom budget file
viberapid . --budget path/to/budget.json
```

---

## CI Integration

### GitHub Actions

```yaml
name: Performance Check
on: [pull_request]

jobs:
  viberapid:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: Install viberapid
        run: pip install viberapid && viberapid install

      - name: Run performance scan
        run: viberapid . --ship-fast --fail-on high --output json --output-file viberapid-report.json

      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: viberapid-report
          path: viberapid-report.json
```

### PR Comment (Markdown output)

```yaml
      - name: Run scan with markdown output
        run: viberapid . --output md --output-file viberapid-comment.md

      - name: Comment on PR
        if: github.event_name == 'pull_request'
        uses: marocchino/sticky-pull-request-comment@v2
        with:
          path: viberapid-comment.md
```

### Incremental scans

Only scan files changed in the PR:

```yaml
      - name: Incremental scan
        run: viberapid . --since origin/main --fail-on high
```

---

## Configuration

Create a `.viberapid.yml` in your project root for persistent configuration:

```yaml
# Fail CI if findings at or above this severity
fail_on: high

# Target URL for Lighthouse, load tests, and network tools
url: https://staging.example.com

# Project stack (auto | node | python | fullstack)
stack: auto

# Per-tool configuration
tools:
  lighthouse:
    enabled: true
    categories: [performance, best-practices]
  k6:
    enabled: true
    vus: 25
    duration: "15s"
  purgecss:
    enabled: true
    safelist: ["active", "show", "fade"]
  ast-analyser:
    python: true
    javascript: true
    typescript: true

# Suppress specific rules
ignore_rules:
  - "depcheck:missing-dep"
  - "stylelint-perf:selector-max-specificity"

# Suppress specific findings by ID
ignore_findings:
  - id: "a1b2c3d4e5f67890"

# Performance budget file
budget: .viberapid-budget.json

# History retention (days)
findings_retention: 30
```

---

## AST Analyser

viberapid includes a built-in AST analyser with **12 custom performance rules** that require no external tools. It uses Python's `ast` module for Python files and regex-based pattern matching for JS/TS files.

### Python Rules (5)

| Rule ID | What it detects |
|---------|----------------|
| `py-sync-in-async` | Blocking I/O calls inside async functions (e.g., `time.sleep`, `open()`, `requests.get`) |
| `py-await-in-loop` | `await` expressions inside `for`/`while` loops (sequential where concurrent is possible) |
| `py-nested-comprehension` | Deeply nested list/dict comprehensions that harm readability and performance |
| `py-json-deepcopy` | `json.loads(json.dumps(obj))` anti-pattern instead of `copy.deepcopy()` |
| `py-n-plus-one` | N+1 query patterns — ORM calls inside loops |

### JS/TS Rules (7)

| Rule ID | What it detects |
|---------|----------------|
| `js-await-in-loop` | Sequential `await` inside `for`/`while` loops |
| `js-inline-jsx-object` | Inline object/array literals in JSX props causing unnecessary re-renders |
| `js-missing-memo` | Exported React components without `React.memo` wrapper |
| `js-large-import` | Full-library imports of large packages (lodash, moment, etc.) |
| `js-unthrottled-listener` | Event listeners (`scroll`, `resize`, `mousemove`) without throttle/debounce |
| `js-regexp-in-loop` | `new RegExp()` creation inside loops (compile once, reuse) |
| `js-deep-spread` | Deeply nested object spread operations |

The AST analyser also includes ORM-specific sub-rules (`py-select-star`, `py-all-before-filter`) that fire within the `orm_antipatterns` module.

---

## Output Formats

| Format | Flag | Description |
|--------|------|-------------|
| Rich table | `--output table` | Coloured terminal table with severity badges, quick wins, and budget summary (default) |
| HTML | `--output html` | Self-contained HTML file with dark/light mode toggle, sortable tables, and charts |
| Markdown | `--output md` | Structured Markdown suitable for PR comments, with collapsible sections |
| JSON | `--output json` | Machine-readable JSON with all findings, metrics, budget results, and tool overlap data |

All formats support `--output-file <path>` to write to a file instead of stdout.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Clean — no findings above the `--fail-on` threshold |
| `1` | Findings above the `--fail-on` severity threshold |
| `2` | One or more tools encountered errors |
| `3` | Required tools are missing (run `viberapid install`) |
| `4` | All critical budget metrics exceeded |

---

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing guidelines, and how to add a new tool runner.

---

## License

[MIT](LICENSE)
