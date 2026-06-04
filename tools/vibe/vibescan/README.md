# vibescan

The definitive security scanner for AI-generated codebases.

One command. Thirteen tools. Zero config needed.

vibescan orchestrates best-in-class open source security tools in parallel, deduplicates findings across overlapping scanners, and gives you a single pass/fail verdict suitable for CI gating.

```
pip install vibescan
vibescan install && vibescan .
```

## Why vibescan?

AI-generated code ships fast. vibescan makes sure it ships safely.

- **Secrets** leaked by chatty models get caught before they hit a remote.
- **Dependency CVEs** in AI-suggested packages are surfaced immediately.
- **SAST issues** like `exec()`, unsafe deserialization, and shell injection are flagged with fix hints.
- **IaC misconfigurations** in generated Dockerfiles and Terraform files are caught.
- **Licence compliance** is checked against your blocklist.

All findings are normalised to a common schema, deduplicated across tools, and ranked by severity. You get one exit code, one report.

## Install

```bash
# From PyPI
pip install vibescan

# Or with pipx (recommended for CLI tools)
pipx install vibescan

# Requires Python 3.11+
```

## Quickstart

```bash
# Download and configure all security tools (one-time)
vibescan install

# Scan the current directory
vibescan .

# Scan with JSON output
vibescan . --output json --output-file report.json

# Ship-safe mode for CI
vibescan . --ship-safe

# Scan only changed files
vibescan . --since main

# Skip secret scanners
vibescan . --no-secrets

# Use specific tools only
vibescan . --tools gitleaks,semgrep,trivy
```

## Tool Coverage

vibescan orchestrates 13 security tools across 5 categories:

| Tool | Category | Detects | Install Method |
|------|----------|---------|----------------|
| **gitleaks** | Secrets | API keys, tokens, passwords in code and git history | Binary (GitHub) |
| **trufflehog** | Secrets | Secrets with optional cloud verification (AWS, GCP, Stripe) | Binary (GitHub) |
| **detect-secrets** | Secrets | High-entropy strings, known secret patterns | pip |
| **semgrep** | SAST | Code vulnerabilities, injection flaws, insecure patterns | pip |
| **bandit** | SAST | Python-specific security issues (B101-B703) | pip |
| **codeql** | SAST | Deep semantic analysis (requires `--deep`, slow) | Native |
| **trivy** | Dependencies | CVEs in npm, pip, Go, Rust, Java, and OS packages | Binary (GitHub) |
| **grype** | Dependencies | CVEs with CVSS scoring, overlaps with trivy for dedup | Binary (GitHub) |
| **npm audit** | Dependencies | JavaScript/Node.js dependency vulnerabilities | Native (npm) |
| **pip-audit** | Dependencies | Python dependency vulnerabilities via PyPI advisory DB | pip |
| **snyk** | Dependencies | Commercial-grade CVE database (requires `SNYK_TOKEN`) | Binary (GitHub) |
| **kics** | IaC | Dockerfile, Terraform, Kubernetes YAML misconfigurations | Binary (GitHub) |
| **licence scanner** | Licence | GPL, AGPL, SSPL, and unknown licences in dependencies | npm + pip |

Tools run in parallel. If a tool is not installed or not applicable (e.g., no `package-lock.json` for npm audit), it is silently skipped.

## CLI Reference

### `vibescan [TARGET]`

Run a security scan on the target directory (default: `.`).

| Flag | Description | Default |
|------|-------------|---------|
| `--tools TOOLS` | Run only named tools (comma-separated) | All applicable |
| `--skip TOOLS` | Skip named tools (comma-separated) | None |
| `--fail-on LEVEL` | Exit 1 if any finding meets this severity | `high` |
| `--output FORMAT` | Report format: `table`, `json`, `html`, `sarif`, `md` | `table` |
| `--output-file PATH` | Write report to file instead of stdout | None |
| `--config PATH` | Path to config file | `.vibescan.yml` |
| `--fix` | Include remediation hints in output | Off |
| `--ship-safe` | Strict CI mode (see below) | Off |
| `--deep` | Include CodeQL (slow) | Off |
| `--no-secrets` | Skip all secret scanners | Off |
| `--since REF` | Scan only files changed since git ref | None |
| `--threads N` | Parallelism | CPU count |
| `--timeout N` | Per-tool timeout in seconds | 120 |
| `--json-pretty` | Pretty-print JSON output | Off |
| `--quiet` | Suppress progress, findings only | Off |
| `--verbose` | Debug output | Off |
| `--version` | Show version and exit | |

### `vibescan install`

Download and install all security tools into `~/.vibescan/`.

| Flag | Description |
|------|-------------|
| `--update` | Upgrade all tools to latest versions |
| `--check` | Show tool status table without installing |

### `vibescan report`

Re-render previous scan results without re-scanning.

| Flag | Description |
|------|-------------|
| `--last` | Re-render the most recent scan |
| `--trend` | Show finding count trend over time |
| `--target PATH` | Project directory | `.` |
| `--output FORMAT` | Report format | `table` |
| `--output-file PATH` | Write to file |

### `vibescan baseline`

Manage detect-secrets baseline for suppressing known secrets.

| Flag | Description |
|------|-------------|
| `--create` | Create a new `.secrets.baseline` |
| `--update` | Update existing baseline |

## Configuration

Create a `.vibescan.yml` in your project root:

```yaml
# Severity threshold for non-zero exit
fail_on: HIGH

# Strict CI mode
ship_safe: false

# Scan history retention (days)
findings_retention: 30

# Per-tool configuration
tools:
  gitleaks:
    enabled: true
  semgrep:
    enabled: true
    rulesets:
      - p/owasp-top-ten
      - p/secrets
  bandit:
    enabled: true
  trivy:
    enabled: true
    severity: HIGH,CRITICAL
    ignore_unfixed: true
  snyk:
    enabled: false   # requires SNYK_TOKEN
  codeql:
    enabled: false   # slow, use --deep

  # Licence scanning
  licence:
    blocklist:
      - GPL-2.0
      - GPL-3.0
      - AGPL-3.0
      - SSPL
    allowlist:
      - MIT
      - Apache-2.0
      - BSD-2-Clause
      - BSD-3-Clause
      - ISC

# Suppress specific rules
ignore_rules:
  - "bandit:B101"      # assert usage is fine in tests
  - "semgrep:python.lang.best-practice.open-never-closed"

# Suppress specific findings by ID
ignore_findings:
  - id: "abc123def456"
```

CLI flags override config file values.

## Output Formats

| Format | Flag | Description |
|--------|------|-------------|
| **Table** | `--output table` | Rich terminal table with colour-coded severity (default) |
| **JSON** | `--output json` | Machine-readable JSON with all findings and metadata |
| **SARIF** | `--output sarif` | Static Analysis Results Interchange Format for GitHub Code Scanning |
| **HTML** | `--output html` | Standalone HTML report for sharing |
| **Markdown** | `--output md` | Markdown summary for PR comments |

## Ship-Safe Mode

Ship-safe mode (`--ship-safe`) is a strict CI gating mode designed for deployment pipelines:

- **Blocks** on any CRITICAL or HIGH severity finding
- **Blocks** on blocklisted licence (GPL, AGPL, SSPL, unknown)
- **Immediately blocks** (exit 4) on verified secrets (trufflehog cloud verification)
- Emits GitHub Actions `::error` annotations for blocking findings
- Produces a one-liner summary suitable for CI logs

```bash
# In your deployment pipeline
vibescan . --ship-safe --output json --output-file vibescan-report.json
```

## Exit Codes

| Code | Meaning |
|------|---------|
| **0** | Clean: no findings above threshold |
| **1** | Blocked: findings above `--fail-on` threshold (or HIGH in ship-safe mode) |
| **2** | Incomplete: one or more tools failed or timed out, but no blocking findings |
| **4** | Verified secret: a secret was cryptographically verified as live (ship-safe only) |

## CI Integration

### GitHub Actions

```yaml
name: Security Scan
on: [push, pull_request]

jobs:
  vibescan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install vibescan
        run: pip install vibescan

      - name: Install security tools
        run: vibescan install

      - name: Run security scan
        run: vibescan . --ship-safe --output sarif --output-file results.sarif

      - name: Upload SARIF to GitHub
        if: always()
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: results.sarif
```

### GitLab CI

```yaml
security-scan:
  image: python:3.12-slim
  script:
    - pip install vibescan
    - vibescan install
    - vibescan . --ship-safe --output json --output-file gl-vibescan-report.json
  artifacts:
    reports:
      codequality: gl-vibescan-report.json
    when: always
```

## Finding Schema

Every finding is normalised to a common schema:

```json
{
  "id": "a1b2c3d4e5f6g7h8",
  "tool": "trivy",
  "severity": "HIGH",
  "category": "VULNERABILITY",
  "file": "package-lock.json",
  "line": null,
  "rule_id": "CVE-2024-48930",
  "rule_name": "Express.js open redirect",
  "message": "Express.js versions before 4.18.3 are vulnerable...",
  "cve": "CVE-2024-48930",
  "cvss": 7.5,
  "fix_hint": "Upgrade express to 4.18.3",
  "tools": ["trivy", "grype"],
  "is_duplicate": true,
  "duplicate_group": "cve:CVE-2024-48930"
}
```

Categories: `SECRET`, `VULNERABILITY`, `CODE`, `IaC`, `LICENCE`.

Severities: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`.

## Adding a New Tool

See [CONTRIBUTING.md](CONTRIBUTING.md) for a step-by-step guide to adding a new security tool.

## Development

```bash
# Clone and install
git clone https://github.com/vibescan/vibescan.git
cd vibescan
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run with coverage
pytest --cov=vibescan --cov-report=term-missing tests/
```

## Licence

MIT
