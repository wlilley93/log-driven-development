# Contributing to vibescan

## Adding a New Security Tool

vibescan is designed so that adding a new tool requires changes to exactly 4 files, plus a test fixture and test additions. No other files need to change.

### Step 1: Create the runner

Create `vibescan/runners/newtool.py` implementing `AsyncToolRunner`:

```python
"""NewTool runner — brief description of what it scans."""

from __future__ import annotations

import json
import logging
import shutil
import time
from typing import Any

from vibescan.models import Finding, ToolResult, ToolStatus
from vibescan.normalisers.newtool import NewToolNormaliser
from vibescan.runners.base import AsyncToolRunner

logger = logging.getLogger(__name__)


class NewToolRunner(AsyncToolRunner):
    name = "newtool"
    # Set these if applicable:
    # deep_only = True          # Only run with --deep flag
    # is_secret_scanner = True  # Skipped with --no-secrets

    def should_run(self) -> bool:
        """Pre-flight check: is the tool installed and applicable?"""
        if not shutil.which(self.bin_path):
            self.skip_reason = "newtool binary not found"
            return False
        # Optional: check for required files
        # if not self._file_exists("somefile.json"):
        #     self.skip_reason = "no somefile.json found"
        #     return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        start = time.monotonic()

        cmd = [self.bin_path, "scan", self.target, "--format", "json"]

        if self.config.verbose:
            logger.info("newtool command: %s", " ".join(cmd))

        try:
            result = self._exec(cmd)
        except FileNotFoundError:
            return self._make_error_result("newtool binary not found")
        except Exception as exc:
            return self._make_error_result(f"newtool error: {exc}")

        duration = time.monotonic() - start

        # Parse output
        raw_data: dict[str, Any] | None = None
        if result.stdout.strip():
            try:
                raw_data = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                return ToolResult(
                    tool=self.name,
                    status=ToolStatus.FAILED,
                    error=f"Failed to parse JSON: {exc}",
                    duration_seconds=duration,
                )

        if result.returncode not in (0, 1) and not raw_data:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.FAILED,
                error=f"Exit code {result.returncode}: {result.stderr.strip()[:500]}",
                duration_seconds=duration,
            )

        # Normalise
        findings: list[Finding] = []
        if raw_data:
            normaliser = NewToolNormaliser()
            findings = normaliser.normalise(raw_data)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            duration_seconds=duration,
        )
```

Key points:
- `name` must be unique and match the installer registry name.
- `should_run()` returns `False` (with `self.skip_reason`) if the tool cannot run.
- `run()` calls the tool, parses output, and returns a `ToolResult`.
- Use `self._exec(cmd)` for subprocess execution (handles cwd, timeout, env).
- Use `self._exec_json(cmd)` if you only need parsed JSON output.

### Step 2: Create the normaliser

Create `vibescan/normalisers/newtool.py` implementing `BaseNormaliser`:

```python
"""Normaliser for NewTool output."""

from __future__ import annotations

from typing import Any

from vibescan.models import Category, Finding, Severity
from vibescan.normalisers.base import BaseNormaliser


class NewToolNormaliser(BaseNormaliser):
    """Transform NewTool JSON output into normalised Findings."""

    tool_name = "newtool"

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        results = raw_data.get("results", [])
        if not isinstance(results, list):
            return []

        findings: list[Finding] = []
        for entry in results:
            if not isinstance(entry, dict):
                continue

            findings.append(
                Finding(
                    tool=self.tool_name,
                    severity=self.text_severity(entry.get("severity", "MEDIUM")),
                    category=Category.CODE,  # Choose: SECRET, VULNERABILITY, CODE, IAC, LICENCE
                    file=entry.get("file", "unknown"),
                    rule_id=entry.get("rule_id", "unknown"),
                    rule_name=entry.get("rule_name", "unknown"),
                    message=entry.get("message", ""),
                    line=entry.get("line"),
                    col=entry.get("col"),
                    # For dependency tools:
                    # cve=entry.get("cve"),
                    # cvss=entry.get("cvss"),
                    # fix_hint=entry.get("fix"),
                    # For secret tools:
                    # secret_verified=entry.get("verified"),
                    raw=entry,
                )
            )

        return findings
```

Key points:
- Extend `BaseNormaliser` and set `tool_name`.
- Use `self.text_severity(text)` for string-to-Severity mapping.
- Use `self.cvss_to_severity(score)` for CVSS-to-Severity mapping.
- Always guard against unexpected input types with `isinstance()` checks.
- Set `cve` and `cvss` for dependency/CVE tools (enables cross-tool CVE dedup).
- Set `secret_verified` for secret tools (enables exit code 4 in ship-safe mode).
- Store the original entry in `raw` for debugging.

### Step 3: Register in the installer and scanner

**In `vibescan/installer.py`**, add a `ToolSpec` to the `TOOLS` list:

```python
ToolSpec(
    name="newtool",
    kind="binary",              # or "pip", "npm", "native"
    binary_name="newtool",
    github_repo="org/newtool",  # for binary downloads
    version_cmd=["newtool", "--version"],
    asset_pattern="newtool_{version}_{os}_{arch}.tar.gz",
    extract_binary="newtool",
    # pip_package="newtool",    # for pip tools
    # required=False,           # for optional tools
    # env_var="NEWTOOL_TOKEN",  # skip if env var missing
    # deep_only=True,           # only run with --deep
),
```

**In `vibescan/scanner.py`**, add the import and registration:

```python
from vibescan.runners.newtool import NewToolRunner

ALL_RUNNERS = [
    # ... existing runners ...
    NewToolRunner,
]
```

### Step 4: Add test fixture

Create `tests/fixtures/newtool/output.json` with realistic sample output from the tool. This should include 2-3 findings of different severities to exercise the normaliser.

### Step 5: Add tests

Add a test class to `tests/test_normalisers.py`:

```python
class TestNewToolNormaliser:
    def setup_method(self):
        from vibescan.normalisers.newtool import NewToolNormaliser
        self.normaliser = NewToolNormaliser()
        self.raw = _load_fixture("newtool")

    def test_finding_count(self):
        findings = self.normaliser.normalise(self.raw)
        assert len(findings) == 3  # match your fixture

    def test_severity_mapping(self):
        findings = self.normaliser.normalise(self.raw)
        # Verify correct severity for each finding
        ...

    def test_category(self):
        findings = self.normaliser.normalise(self.raw)
        for f in findings:
            assert f.category == Category.CODE  # or whatever

    def test_key_fields_populated(self):
        findings = self.normaliser.normalise(self.raw)
        for f in findings:
            assert f.tool == "newtool"
            assert f.file != ""
            assert f.rule_id != ""
            assert f.message != ""

    def test_empty_input(self):
        assert self.normaliser.normalise({}) == []

    def test_non_dict_input(self):
        assert self.normaliser.normalise([]) == []
```

### Summary of files changed

| File | Change |
|------|--------|
| `vibescan/runners/newtool.py` | **New** - Runner implementation |
| `vibescan/normalisers/newtool.py` | **New** - Normaliser implementation |
| `vibescan/installer.py` | Add `ToolSpec` to `TOOLS` list |
| `vibescan/scanner.py` | Import runner, add to `ALL_RUNNERS` |
| `tests/fixtures/newtool/output.json` | **New** - Sample tool output |
| `tests/test_normalisers.py` | Add test class |

No other files need to change. The deduplicator, reporters, CLI, and config system all work generically with the `Finding` model.

## Running Tests

```bash
# All unit tests
pytest tests/

# With coverage
pytest --cov=vibescan --cov-report=term-missing tests/

# Integration tests (requires tools installed)
pytest -m integration tests/integration/

# Single test file
pytest tests/test_normalisers.py -v

# Single test class
pytest tests/test_normalisers.py::TestBanditNormaliser -v
```

## Code Style

- Python 3.11+ with `from __future__ import annotations`
- Type hints everywhere
- Guard against unexpected input types (`isinstance()` checks in normalisers)
- `snake_case` for functions and variables
- `PascalCase` for classes
- `SCREAMING_SNAKE_CASE` for module-level constants
- Sort imports: stdlib, third-party, local

## Architecture Notes

- **Runners** execute tools and delegate parsing to normalisers.
- **Normalisers** convert raw tool output to a list of `Finding` dataclasses.
- **Deduplicator** merges findings across tools (CVE dedup, exact match, near match).
- **Reporters** render the final `ScanResult` to the chosen output format.
- The **scanner** orchestrates runners in parallel, applies ignore rules, deduplicates, and computes exit codes.
- **Config** is loaded from `.vibescan.yml` with CLI overrides applied on top.
