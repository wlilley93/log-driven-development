# vibetest

Test quality auditor for AI-generated codebases.

vibetest is **not** a test runner — it's a test **auditor**. It statically analyzes test files and reports on quality issues: missing tests, weak assertions, test smells, flakiness indicators, and coverage gaps.

## Install

```bash
pip install vibetest
```

## Usage

```bash
# Audit tests in current directory
vibetest

# Audit a specific project
vibetest scan /path/to/project

# Run specific runners only
vibetest scan --runners coverage_analyzer,assertion_checker

# Output as JSON
vibetest scan --output json

# Fail on medium or above (for CI)
vibetest scan --fail-on medium
```

## Runners

| Runner | What it checks |
|--------|---------------|
| `coverage_analyzer` | Parses coverage reports or runs pytest --cov. Flags uncovered modules. |
| `assertion_checker` | AST-based. Finds tests with no assertions, weak assertions, mock-only tests. |
| `test_smell` | Detects god tests, copy-paste tests, sleep calls, bad naming, hardcoded paths. |
| `missing_tests` | Compares source to test files. Finds modules and functions with no tests. |
| `flaky_detector` | Finds flakiness indicators: sleeps, unmocked network/random/datetime calls. |

## Configuration

Create a `.vibetest.yml` in your project root:

```yaml
fail_on: HIGH

runners:
  coverage_analyzer:
    threshold_low: 80
  test_smell:
    god_test_lines: 50
    max_assertions: 10

exclude:
  - .venv
  - node_modules
```

## Output Formats

- `table` (default) — Rich terminal output
- `json` — Machine-readable JSON
- `md` — Markdown for PR comments
