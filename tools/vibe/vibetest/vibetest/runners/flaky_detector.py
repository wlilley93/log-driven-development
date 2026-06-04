"""Flaky test detector — finds indicators of test flakiness via AST analysis."""

from __future__ import annotations

import ast
import time
from pathlib import Path

from vibetest.models import Category, Finding, RunnerResult, RunnerStatus, Severity
from vibetest.runners.base import BaseRunner

# Network libraries that should be mocked in tests
_NETWORK_MODULES = {"requests", "urllib", "httpx", "aiohttp", "urllib3", "http"}
_NETWORK_FUNCTIONS = {
    "get", "post", "put", "patch", "delete", "head", "options",
    "request", "urlopen", "fetch",
}

# Non-deterministic functions that need mocking
_NONDETERMINISTIC = {
    ("random", "random"), ("random", "randint"), ("random", "choice"),
    ("random", "shuffle"), ("random", "sample"), ("random", "uniform"),
    ("uuid", "uuid4"), ("uuid", "uuid1"),
    ("datetime", "now"), ("datetime", "utcnow"),
    ("time", "time"),
}

# Temp directory fixtures/functions that indicate proper isolation
_TEMP_PATTERNS = {"tmp_path", "tmpdir", "tempfile", "TemporaryDirectory", "mkdtemp", "mkstemp"}


class FlakyDetectorRunner(BaseRunner):
    name = "flaky_detector"

    def should_run(self) -> bool:
        if not self._find_test_files():
            self.skip_reason = "no test files found"
            return False
        return True

    def run(self) -> RunnerResult:
        start = time.monotonic()
        findings: list[Finding] = []

        for test_file in self._find_test_files():
            tree = self._parse_ast(test_file)
            if tree is None:
                continue

            rel_path = str(test_file.relative_to(Path(self.target)))
            source = test_file.read_text(encoding="utf-8", errors="replace")

            # Check if file uses temp directory patterns (file-level check)
            uses_temp = any(p in source for p in _TEMP_PATTERNS)

            # Collect all imports to understand what's available
            imports = self._collect_imports(tree)

            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if not node.name.startswith("test_"):
                    continue

                findings.extend(
                    self._check_test_function(node, rel_path, imports, uses_temp)
                )

        return RunnerResult(
            runner=self.name,
            status=RunnerStatus.SUCCESS,
            findings=findings,
            duration_seconds=time.monotonic() - start,
        )

    def _check_test_function(
        self,
        func: ast.FunctionDef,
        file_path: str,
        imports: set[str],
        file_uses_temp: bool,
    ) -> list[Finding]:
        findings: list[Finding] = []

        # Check if this specific function uses tmp_path as a parameter
        func_params = {arg.arg for arg in func.args.args}
        uses_temp = file_uses_temp or bool(func_params & _TEMP_PATTERNS)

        has_sleep = False
        has_network = False
        has_nondeterministic = False
        has_filesystem = False

        for child in ast.walk(func):
            if not isinstance(child, ast.Call):
                continue

            # time.sleep()
            if (isinstance(child.func, ast.Attribute)
                    and child.func.attr == "sleep"
                    and not has_sleep):
                has_sleep = True
                findings.append(Finding(
                    runner=self.name,
                    severity=Severity.MEDIUM,
                    category=Category.FLAKY,
                    file=file_path,
                    rule_id="sleep-in-test",
                    message=f"Test `{func.name}` uses sleep() — causes slow and flaky tests",
                    line=child.lineno,
                    fix_hint="Use polling, mock time, or async wait patterns",
                ))

            # Network calls without mocking
            if isinstance(child.func, ast.Attribute):
                attr = child.func.attr
                # Check for module.get(), requests.post(), etc.
                if attr in _NETWORK_FUNCTIONS and not has_network:
                    if isinstance(child.func.value, ast.Name):
                        module = child.func.value.id
                        if module in _NETWORK_MODULES or module in imports & _NETWORK_MODULES:
                            has_network = True
                            findings.append(Finding(
                                runner=self.name,
                                severity=Severity.HIGH,
                                category=Category.FLAKY,
                                file=file_path,
                                rule_id="unmocked-network",
                                message=f"Test `{func.name}` makes real network call via `{module}.{attr}()`",
                                line=child.lineno,
                                fix_hint="Mock network calls with unittest.mock or responses/httpx-mock",
                            ))

            # Non-deterministic calls
            if isinstance(child.func, ast.Attribute) and not has_nondeterministic:
                attr = child.func.attr
                if isinstance(child.func.value, ast.Name):
                    module = child.func.value.id
                    if (module, attr) in _NONDETERMINISTIC:
                        has_nondeterministic = True
                        findings.append(Finding(
                            runner=self.name,
                            severity=Severity.MEDIUM,
                            category=Category.FLAKY,
                            file=file_path,
                            rule_id="nondeterministic",
                            message=f"Test `{func.name}` calls `{module}.{attr}()` without mocking",
                            line=child.lineno,
                            fix_hint=f"Mock `{module}.{attr}` to return deterministic values",
                        ))

            # File system operations without tmp dirs
            if not uses_temp and not has_filesystem:
                if isinstance(child.func, ast.Name) and child.func.id == "open":
                    has_filesystem = True
                    findings.append(Finding(
                        runner=self.name,
                        severity=Severity.LOW,
                        category=Category.FLAKY,
                        file=file_path,
                        rule_id="filesystem-no-tmp",
                        message=f"Test `{func.name}` uses open() without tmp_path fixture",
                        line=child.lineno,
                        fix_hint="Use pytest's tmp_path fixture for file operations",
                    ))
                elif (isinstance(child.func, ast.Attribute)
                      and child.func.attr in ("write_text", "write_bytes", "mkdir", "touch")
                      and not has_filesystem):
                    has_filesystem = True
                    findings.append(Finding(
                        runner=self.name,
                        severity=Severity.LOW,
                        category=Category.FLAKY,
                        file=file_path,
                        rule_id="filesystem-no-tmp",
                        message=f"Test `{func.name}` does filesystem writes without tmp_path",
                        line=child.lineno,
                        fix_hint="Use pytest's tmp_path fixture for file operations",
                    ))

        return findings

    def _collect_imports(self, tree: ast.Module) -> set[str]:
        """Collect all imported module names."""
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split(".")[0])
        return imports
