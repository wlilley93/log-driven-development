"""Missing test detector — finds source modules and functions without tests."""

from __future__ import annotations

import ast
import time
from pathlib import Path

from vibetest.models import Category, Finding, RunnerResult, RunnerStatus, Severity
from vibetest.runners.base import BaseRunner


class MissingTestRunner(BaseRunner):
    name = "missing_tests"

    def should_run(self) -> bool:
        source_files = self._find_source_files()
        if not source_files:
            self.skip_reason = "no source files found"
            return False
        return True

    def run(self) -> RunnerResult:
        start = time.monotonic()
        findings: list[Finding] = []

        source_files = self._find_source_files()
        test_files = self._find_test_files()

        # Build a map of test file stems for matching
        test_stems = set()
        for tf in test_files:
            stem = tf.stem
            # test_foo.py -> foo, foo_test.py -> foo
            if stem.startswith("test_"):
                test_stems.add(stem[5:])
            elif stem.endswith("_test"):
                test_stems.add(stem[:-5])

        # Build a set of all names referenced in test files (for function coverage heuristic)
        test_contents = self._build_test_name_index(test_files)

        for source_file in source_files:
            rel_path = str(source_file.relative_to(Path(self.target)))
            stem = source_file.stem

            # Skip __init__.py and setup files
            if stem in ("__init__", "setup", "conftest", "__main__"):
                continue

            # Check if a corresponding test file exists
            if stem not in test_stems:
                findings.append(Finding(
                    runner=self.name,
                    severity=Severity.HIGH,
                    category=Category.MISSING,
                    file=rel_path,
                    rule_id="no-test-file",
                    message=f"No test file found for `{source_file.name}`",
                    line=1,
                    fix_hint=f"Create `test_{stem}.py` with tests for this module",
                ))
                continue

            # Module has a test file — check for untested public functions/classes
            findings.extend(
                self._check_untested_symbols(source_file, rel_path, test_contents)
            )

        return RunnerResult(
            runner=self.name,
            status=RunnerStatus.SUCCESS,
            findings=findings,
            duration_seconds=time.monotonic() - start,
        )

    def _build_test_name_index(self, test_files: list[Path]) -> set[str]:
        """Build a set of all identifiers referenced in test files."""
        names: set[str] = set()
        for tf in test_files:
            try:
                content = tf.read_text(encoding="utf-8", errors="replace")
                # Simple heuristic: collect all word tokens from test files
                for line in content.splitlines():
                    # Skip comments
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    for token in stripped.split():
                        # Clean up punctuation
                        clean = token.strip("()[]{}:,.'\"=!<>@#")
                        if clean:
                            names.add(clean)
            except OSError:
                continue
        return names

    def _check_untested_symbols(
        self, source_file: Path, rel_path: str, test_contents: set[str]
    ) -> list[Finding]:
        """Check if public functions/classes in a source file appear in test content."""
        findings: list[Finding] = []
        tree = self._parse_ast(source_file)
        if tree is None:
            return findings

        for node in ast.iter_child_nodes(tree):
            # Only top-level functions and classes
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_"):
                    continue
                if node.name not in test_contents:
                    findings.append(Finding(
                        runner=self.name,
                        severity=Severity.MEDIUM,
                        category=Category.MISSING,
                        file=rel_path,
                        rule_id="untested-function",
                        message=f"Public function `{node.name}` has no apparent test coverage",
                        line=node.lineno,
                        fix_hint=f"Add a test that calls and verifies `{node.name}`",
                    ))

            elif isinstance(node, ast.ClassDef):
                if node.name.startswith("_"):
                    continue
                if node.name not in test_contents:
                    findings.append(Finding(
                        runner=self.name,
                        severity=Severity.MEDIUM,
                        category=Category.MISSING,
                        file=rel_path,
                        rule_id="untested-class",
                        message=f"Public class `{node.name}` has no apparent test coverage",
                        line=node.lineno,
                        fix_hint=f"Add tests for `{node.name}` and its public methods",
                    ))

        return findings
