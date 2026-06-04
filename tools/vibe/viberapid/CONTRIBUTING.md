# Contributing to viberapid

Thank you for considering a contribution to viberapid. This guide walks through the project architecture, explains how to add a new tool, and covers the standards your code should meet.

---

## Table of Contents

- [Getting Started](#getting-started)
- [Adding a New Tool](#adding-a-new-tool)
  - [Step 1: Create the Runner](#step-1-create-the-runner)
  - [Step 2: Create the Normaliser](#step-2-create-the-normaliser)
  - [Step 3: Register in the Scanner](#step-3-register-in-the-scanner)
  - [Step 4: Register in the Installer](#step-4-register-in-the-installer)
  - [Step 5: Add Tests](#step-5-add-tests)
- [Runner Anatomy](#runner-anatomy)
- [Normaliser Anatomy](#normaliser-anatomy)
- [Severity Calibration](#severity-calibration)
- [Testing](#testing)
- [Code Style](#code-style)
- [Pull Requests](#pull-requests)

---

## Getting Started

```bash
# Clone the repository
git clone https://github.com/<owner>/viberapid.git
cd viberapid

# Create a virtual environment (Python 3.11+)
python -m venv .venv
source .venv/bin/activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Run the test suite
pytest
```

If all tests pass you are ready to contribute.

---

## Adding a New Tool

Every external tool that viberapid orchestrates needs four pieces:

1. A **runner** that executes the tool and collects raw output.
2. A **normaliser** that converts the raw output into `Finding` objects.
3. A registration entry in `viberapid/scanner.py` so the orchestrator knows about it.
4. A registration entry in `viberapid/installer.py` so the installer can provision it.

Below is a step-by-step walkthrough using an imaginary tool called `fastcheck`.

### Step 1: Create the Runner

Create `viberapid/runners/fastcheck.py`:

```python
"""Runner for fastcheck — detects slow API endpoints."""

from __future__ import annotations

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.fastcheck import FastcheckNormaliser
from viberapid.runners.base import AsyncToolRunner


class FastcheckRunner(AsyncToolRunner):
    """Run fastcheck to analyse API response times."""

    name = "fastcheck"
    requires_url = True       # Set True if the tool needs a live URL
    requires_node = False     # Set True if the tool is an npm package
    requires_python = False   # Set True if the tool is a pip package
    is_load_tester = False    # Set True to use the extended load_timeout

    def should_run(self) -> bool:
        # Add any pre-flight checks here.
        # Call super().should_run() to inherit the requires_url check.
        if not super().should_run():
            return False
        if not self._tool_exists():
            self.skip_reason = "fastcheck binary not found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        cmd = [self.bin_path, "--json", self.config.url]
        data, stderr = self._exec_json(cmd)

        if data is None:
            return self._make_error_result(
                f"fastcheck produced no JSON output. stderr: {stderr[:500]}"
            )

        normaliser = FastcheckNormaliser()
        findings = normaliser.normalise(data)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "endpoints_scanned": data.get("total", 0),
                "slow_endpoints": len(findings),
            },
        )
```

**Key points:**

- Subclass `AsyncToolRunner` from `viberapid/runners/base.py`.
- Set the `name` class attribute to match the tool's identifier everywhere.
- Use `self._exec()` or `self._exec_json()` to run subprocesses. These handle timeouts, working directory, and environment variables.
- Use `self._make_error_result()` when the tool fails to produce usable output.
- Use `self._tool_exists()` to check whether the binary is available.
- Use `self._file_exists()` and `self._glob_files()` to check for prerequisite files in the target directory.

### Step 2: Create the Normaliser

Create `viberapid/normalisers/fastcheck.py`:

```python
"""Normaliser for fastcheck output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser


class FastcheckNormaliser(BaseNormaliser):
    """Convert fastcheck JSON output to Finding objects.

    Expected JSON shape:
    {
      "endpoints": [
        {"path": "/api/users", "p99_ms": 3200, "method": "GET"},
        ...
      ]
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        findings: list[Finding] = []

        for endpoint in raw_data.get("endpoints", []):
            p99 = endpoint.get("p99_ms", 0)
            path = endpoint.get("path", "unknown")
            method = endpoint.get("method", "GET")

            if p99 > 2000:
                severity = Severity.CRITICAL
            elif p99 > 1000:
                severity = Severity.HIGH
            elif p99 > 500:
                severity = Severity.MEDIUM
            else:
                continue  # Good performance, no finding needed

            findings.append(Finding(
                tool="fastcheck",
                severity=severity,
                category=Category.NETWORK,
                file=path,
                rule_id="slow-endpoint",
                rule_name="Slow API endpoint",
                message=f"{method} {path} has p99 latency of {p99}ms.",
                metric="p99_ms",
                current_value=float(p99),
                target_value=500,
                fix_hint=f"Profile the {method} {path} handler. Check for N+1 queries, missing indexes, or blocking I/O.",
                saving_estimate=f"Reduce p99 from {p99}ms to <500ms on {method} {path}.",
                effort=Effort.MEDIUM,
                raw=endpoint,
            ))

        return findings
```

**Key points:**

- Subclass `BaseNormaliser` from `viberapid/normalisers/base.py`.
- Implement `normalise(self, raw_data: Any) -> list[Finding]`.
- Always guard against unexpected input types at the top of the method. Return `[]` for `None`, wrong types, or empty data.
- Set appropriate `severity` using threshold-based logic (see [Severity Calibration](#severity-calibration)).
- Populate `metric`, `current_value`, and `target_value` whenever the finding is quantitative.
- Always provide a `fix_hint` with actionable guidance.
- Optionally set `saving_estimate` to describe the expected improvement.
- Set `effort` to `LOW`, `MEDIUM`, or `HIGH` based on how hard the fix is.

### Step 3: Register in the Scanner

Open `viberapid/scanner.py` and add your runner to the `_RUNNER_SPECS` list. Place it in the appropriate category section:

```python
_RUNNER_SPECS: list[tuple[str, str]] = [
    # Bundle & JS
    ("viberapid.runners.depcheck", "DepcheckRunner"),
    # ...

    # HTTP & Network
    ("viberapid.runners.lighthouse", "LighthouseRunner"),
    ("viberapid.runners.fastcheck", "FastcheckRunner"),   # <-- add here
    # ...
]
```

The tuple is `(module_path, class_name)`. The orchestrator imports these dynamically and gracefully skips any that fail to import.

### Step 4: Register in the Installer

Open `viberapid/installer.py` and add a `ToolSpec` to the `TOOLS` list:

```python
TOOLS: list[ToolSpec] = [
    # ...
    ToolSpec(
        name="fastcheck",
        kind="binary",                    # "binary", "pip", "npm", "npx", or "native"
        binary_name="fastcheck",          # Name of the executable
        github_repo="org/fastcheck",      # For binary downloads from GitHub releases
        version_cmd=["fastcheck", "--version"],
        required=False,                   # True = viberapid fails if missing
        stack=None,                       # "node", "python", or None for universal
    ),
    # ...
]
```

The `kind` field determines how the tool is installed:

| Kind | Description | Key fields |
|------|-------------|------------|
| `binary` | Downloaded from GitHub releases | `github_repo`, `asset_pattern`, `extract_binary` |
| `pip` | Installed via pip | `pip_package` |
| `npm` | Installed via npm (global to viberapid) | `npm_package` |
| `npx` | Run via npx (not installed) | `npm_package` |
| `native` | Expected to be on the system PATH | `binary_name` |

### Step 5: Add Tests

Add tests in `tests/test_normalisers.py` (or a new file under `tests/`). At minimum, cover:

1. **Happy path** with realistic tool output.
2. **Severity thresholds** at each boundary.
3. **Edge cases**: `None`, empty dict/list, wrong type, empty arrays.
4. **Field correctness**: `tool`, `rule_id`, `category`, `severity`, `fix_hint`, `metric`, `current_value`, `target_value`.

```python
class TestFastcheckNormaliser:
    """Tests for fastcheck normaliser."""

    @pytest.fixture
    def norm(self):
        from viberapid.normalisers.fastcheck import FastcheckNormaliser
        return FastcheckNormaliser()

    def test_critical_p99(self, norm):
        """p99 > 2000ms should produce CRITICAL finding."""
        data = {"endpoints": [{"path": "/api/users", "p99_ms": 3200, "method": "GET"}]}
        findings = norm.normalise(data)
        assert len(findings) == 1
        f = findings[0]
        assert f.severity == Severity.CRITICAL
        assert f.category == Category.NETWORK
        assert f.tool == "fastcheck"
        assert f.rule_id == "slow-endpoint"
        assert f.current_value == 3200.0
        assert f.target_value == 500
        assert f.fix_hint is not None

    def test_high_p99(self, norm):
        """p99 between 1000-2000ms should produce HIGH finding."""
        data = {"endpoints": [{"path": "/api/items", "p99_ms": 1500, "method": "POST"}]}
        findings = norm.normalise(data)
        assert len(findings) == 1
        assert findings[0].severity == Severity.HIGH

    def test_medium_p99(self, norm):
        """p99 between 500-1000ms should produce MEDIUM finding."""
        data = {"endpoints": [{"path": "/api/health", "p99_ms": 750, "method": "GET"}]}
        findings = norm.normalise(data)
        assert len(findings) == 1
        assert findings[0].severity == Severity.MEDIUM

    def test_good_p99(self, norm):
        """p99 <= 500ms should produce no finding."""
        data = {"endpoints": [{"path": "/api/ping", "p99_ms": 200, "method": "GET"}]}
        findings = norm.normalise(data)
        assert len(findings) == 0

    @pytest.mark.parametrize("bad_input", [None, "", 42, [], True])
    def test_invalid_input_returns_empty(self, norm, bad_input):
        """Non-dict input should return empty list."""
        assert norm.normalise(bad_input) == []

    def test_empty_dict_returns_empty(self, norm):
        assert norm.normalise({}) == []

    def test_empty_endpoints(self, norm):
        assert norm.normalise({"endpoints": []}) == []
```

---

## Runner Anatomy

Every runner subclasses `AsyncToolRunner` (defined in `viberapid/runners/base.py`). Here is the complete class contract:

```python
class AsyncToolRunner(ABC):
    # --- Class attributes (override in subclass) ---
    name: str = ""               # Tool identifier (must match ToolSpec.name)
    requires_url: bool = False   # True if the tool needs --url
    requires_node: bool = False  # True if the tool is an npm/npx package
    requires_python: bool = False  # True if the tool is a pip package
    is_load_tester: bool = False # True to use config.load_timeout instead of config.timeout

    def __init__(self, target: str, config: Config):
        self.target = target           # Project directory path
        self.config = config           # Scan configuration
        self.skip_reason: str | None   # Set this if should_run() returns False

    # --- Properties ---
    @property
    def bin_path(self) -> str: ...       # Path to the tool binary
    @property
    def tool_config(self) -> dict: ...   # Per-tool config from viberapid.yaml

    # --- Methods to override ---
    def should_run(self) -> bool: ...    # Pre-flight check; set self.skip_reason if False
    def run(self, changed_files: list[str] | None = None) -> ToolResult: ...  # Execute the tool

    # --- Helpers available to subclasses ---
    def _exec(self, cmd, cwd=None, timeout=None, env=None, input_data=None) -> CompletedProcess
    def _exec_json(self, cmd, cwd=None, timeout=None, env=None) -> tuple[Any | None, str]
    def _make_error_result(self, error: str) -> ToolResult
    def _tool_exists(self) -> bool
    def _file_exists(self, *names: str) -> bool
    def _glob_files(self, *patterns: str) -> list[Path]
    def _npx_path(self) -> str
```

### should_run()

Called before `run()`. Return `False` and set `self.skip_reason` to a human-readable string if the tool should not execute. Common reasons:

- Required file missing (e.g., `package.json` for Node tools).
- Binary not installed.
- No URL provided for URL-based tools.

The base class implementation already checks `requires_url`. Call `super().should_run()` if you want to keep that check.

### run()

Execute the tool, parse the output, pass it through the normaliser, and return a `ToolResult`. Always handle subprocess failures gracefully by returning `self._make_error_result(...)`.

---

## Normaliser Anatomy

Every normaliser subclasses `BaseNormaliser` (defined in `viberapid/normalisers/base.py`):

```python
class BaseNormaliser(ABC):
    @abstractmethod
    def normalise(self, raw_data: Any) -> list[Finding]:
        """Convert raw tool output to normalised findings."""
        ...
```

### The normalise() method

The method receives the parsed tool output (usually a `dict` or `list` from JSON parsing) and returns a list of `Finding` objects.

**Required pattern at the top of every normalise() implementation:**

```python
def normalise(self, raw_data: Any) -> list[Finding]:
    if not isinstance(raw_data, dict):  # or list, depending on the tool
        return []
    # ... rest of normalisation logic
```

This guard ensures the normaliser never crashes on unexpected input.

### Creating Finding objects

The `Finding` dataclass (from `viberapid/models.py`) has these fields:

```python
@dataclass
class Finding:
    tool: str                          # Tool name (must match runner name)
    severity: Severity                 # CRITICAL, HIGH, MEDIUM, LOW, INFO
    category: Category                 # BUNDLE, ASSET, NETWORK, DATABASE, RUNTIME,
                                       # CACHE, DEPENDENCY, CSS, FONT, RENDER,
                                       # COMPRESSION, LOAD, CODE
    file: str                          # File path or resource identifier
    rule_id: str                       # Machine-readable rule ID (kebab-case)
    rule_name: str                     # Human-readable rule name
    message: str                       # Description of what was found
    line: int | None = None            # Line number (if applicable)
    col: int | None = None             # Column number (if applicable)
    fix_hint: str | None = None        # Actionable fix suggestion
    metric: str | None = None          # Metric name (e.g., "lcp", "p99_ms")
    current_value: float | None = None # Measured value
    target_value: float | None = None  # Ideal/target value
    saving_estimate: str | None = None # Human-readable savings description
    effort: Effort = Effort.MEDIUM     # LOW, MEDIUM, HIGH
    raw: dict = field(default_factory=dict)  # Original raw data for debugging
```

**Guidelines for populating fields:**

- `rule_id`: Use kebab-case. Prefix with the tool name if there could be collisions across tools (e.g., `sqlfluff/ST09`).
- `message`: Describe what was found. Include specific values (e.g., "LCP is 4.2s, exceeding the 2.5s threshold").
- `fix_hint`: Always provide one. Be specific and actionable (e.g., "Run `npm uninstall lodash`" rather than "Remove unused packages").
- `metric` + `current_value` + `target_value`: Set all three whenever the finding is based on a quantitative measurement. This enables budget checks and trend tracking.
- `saving_estimate`: Describe the concrete improvement the user can expect.
- `effort`: `LOW` = minutes to fix or auto-fixable, `MEDIUM` = hours, `HIGH` = days or requires architectural changes.

---

## Severity Calibration

Consistent severity assignment is critical for useful reports. Use these guidelines when setting thresholds in your normaliser:

### CRITICAL

Blocking performance issues that directly degrade user experience or cause outages.

- LCP > 4s
- TBT > 600ms
- TTI > 7.3s
- JavaScript bundle > 500KB (gzipped)
- N+1 query pattern detected
- Memory leak detected
- Error rate > 1% under load
- p99 latency > 2s

### HIGH

Significant issues that noticeably impact performance and should be prioritised.

- LCP 2.5-4s
- TBT 300-600ms
- JavaScript bundle 250-500KB (gzipped)
- Unused heavy dependencies (e.g., moment, lodash when only one function is used)
- Missing dependency (imported but not in package.json)
- Error rate 0.5-1%
- p99 latency 1-2s
- SELECT * in production queries
- Cartesian product in SQL joins
- CLS > 0.25
- More than 10 uncached static assets

### MEDIUM

Issues worth fixing that have a measurable but non-critical impact.

- Accessibility issues (missing alt text, poor contrast)
- Suboptimal image formats (JPEG where WebP would save >30%)
- Missing compression headers
- Unused production dependencies
- Code duplication > 5%
- Render-blocking resources
- p99 latency 500ms-1s
- Error rate 0.1-0.5%

### LOW

Minor improvements. Good to fix but low urgency.

- Code style issues in SQL
- Small optimisation opportunities (<10% improvement)
- Unused dev dependencies
- Unused file detected
- Unused exports
- Code duplication <= 5%
- SVG optimisation opportunities 15-30%

### INFO

Purely informational. No action required but useful context.

- SVG optimisation < 15%
- Well-compressed files (just reporting stats)
- Minimal unused CSS (<10%)

**When in doubt, go one level lower.** Users can always filter by severity; false CRITICAL findings erode trust.

---

## Testing

Tests live in `tests/` and use **pytest**.

### Test file conventions

| What you are testing | Where to put it |
|----------------------|-----------------|
| Normaliser logic | `tests/test_normalisers.py` (add a new class) |
| Model behaviour | `tests/test_models.py` |
| Runner integration | A new file, e.g., `tests/test_runner_fastcheck.py` |
| Deduplication | `tests/test_deduplicator.py` |
| Budget checking | `tests/test_budget.py` |

### Writing normaliser tests

Follow this pattern (mirroring the existing tests in `tests/test_normalisers.py`):

```python
import pytest
from viberapid.models import Category, Effort, Finding, Severity


def _find_by_rule(findings: list[Finding], rule_id: str) -> Finding | None:
    """Return the first Finding matching a rule_id, or None."""
    for f in findings:
        if f.rule_id == rule_id:
            return f
    return None


class TestMyToolNormaliser:

    @pytest.fixture
    def norm(self):
        from viberapid.normalisers.my_tool import MyToolNormaliser
        return MyToolNormaliser()

    def test_happy_path(self, norm):
        """Realistic input produces expected findings."""
        data = { ... }
        findings = norm.normalise(data)
        assert len(findings) >= 1
        f = findings[0]
        assert f.tool == "my-tool"
        assert f.severity == Severity.HIGH
        assert f.category == Category.NETWORK
        assert f.fix_hint is not None

    def test_severity_boundary(self, norm):
        """Verify the exact threshold between HIGH and MEDIUM."""
        # Test at the boundary value
        ...

    @pytest.mark.parametrize("bad_input", [None, "", 42, [], True])
    def test_invalid_input_returns_empty(self, norm, bad_input):
        """Non-dict input should return empty list."""
        assert norm.normalise(bad_input) == []

    def test_empty_dict_returns_empty(self, norm):
        assert norm.normalise({}) == []
```

### What to test

At minimum, every normaliser needs:

1. **Happy path**: Realistic tool output produces the correct number and kind of findings.
2. **Each severity level**: One test per threshold boundary (e.g., test that 2001ms is CRITICAL and 2000ms is HIGH).
3. **Field correctness**: Verify `tool`, `rule_id`, `category`, `severity`, `fix_hint`, `current_value`, `target_value`, and `effort` on at least one finding.
4. **Invalid input**: Parametrised test with `None`, `""`, `42`, `[]`, `True`.
5. **Empty valid input**: Empty dict or empty list (depending on what the tool returns).
6. **Empty inner collections**: e.g., `{"endpoints": []}` produces no findings.

### Running tests

```bash
# Run all tests
pytest

# Run a specific test file
pytest tests/test_normalisers.py

# Run a specific test class
pytest tests/test_normalisers.py::TestDepcheckNormaliser

# Run a single test
pytest tests/test_normalisers.py::TestDepcheckNormaliser::test_unused_dependencies

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=viberapid --cov-report=term-missing
```

---

## Code Style

### Python version

- Target **Python 3.11+**. Use modern syntax: `X | Y` union types, `list[str]` lowercase generics.

### Imports

- Every file starts with `from __future__ import annotations`.
- Import order: stdlib, third-party, viberapid internals.

### Type hints

- All function signatures must have type hints for parameters and return values.
- Use `Any` from `typing` sparingly and only for genuinely dynamic data (e.g., raw JSON input to normalisers).

### Docstrings

- Every module has a one-line docstring at the top (e.g., `"""Runner for fastcheck — detects slow API endpoints."""`).
- Every class has a docstring describing its purpose.
- Public methods have docstrings. Private helpers can omit them if the name is self-explanatory.

### Naming conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Modules | snake_case | `viberapid/runners/gzip_size.py` |
| Classes | PascalCase | `GzipSizeRunner`, `GzipSizeNormaliser` |
| Functions | snake_case | `normalise()`, `should_run()` |
| Constants | SCREAMING_SNAKE_CASE | `_RUNNER_SPECS`, `TOOLS` |
| rule_id | kebab-case | `unused-dependency`, `slow-endpoint` |

### Formatting

- Keep lines under 120 characters.
- Use trailing commas in multi-line collections.
- No unused imports.

---

## Pull Requests

### Before submitting

1. Run the full test suite: `pytest`
2. Verify no lint errors if a linter is configured.
3. Confirm all new code has type hints and docstrings.
4. Test edge cases in your normaliser (see [Testing](#testing)).

### PR checklist

- [ ] Runner created at `viberapid/runners/<tool_name>.py`
- [ ] Normaliser created at `viberapid/normalisers/<tool_name>.py`
- [ ] Runner registered in `_RUNNER_SPECS` in `viberapid/scanner.py`
- [ ] ToolSpec registered in `TOOLS` in `viberapid/installer.py`
- [ ] Tests added covering happy path, all severity boundaries, and edge cases
- [ ] Invalid input returns `[]` (not an exception)
- [ ] `fix_hint` is populated on every finding
- [ ] Severity levels follow the [calibration guidelines](#severity-calibration)
- [ ] `from __future__ import annotations` at the top of every new file

### PR guidelines

- **One tool per PR.** It is easier to review a runner + normaliser + tests for a single tool than a batch.
- **Title format**: `feat: add <tool-name> runner and normaliser` (e.g., `feat: add fastcheck runner and normaliser`).
- **Description**: Include a brief summary of what the tool detects, a link to the tool's homepage, and an example of its output format.
- **Keep normalisers pure.** Normalisers should never run subprocesses, read files, or make network calls. They receive parsed data and return `Finding` objects. All I/O belongs in the runner.
- **Backward compatibility.** Do not change the `Finding` dataclass fields or the `BaseNormaliser` / `AsyncToolRunner` interfaces without discussion in an issue first.
