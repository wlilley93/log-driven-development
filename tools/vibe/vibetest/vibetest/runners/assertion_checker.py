"""Assertion checker — AST-based analysis of test assertion quality."""

from __future__ import annotations

import ast
import time
from pathlib import Path

from vibetest.models import Category, Finding, RunnerResult, RunnerStatus, Severity
from vibetest.runners.base import BaseRunner

# Assertion method names from unittest and pytest
_ASSERT_METHODS = {
    "assert", "assertEqual", "assertNotEqual", "assertTrue", "assertFalse",
    "assertIs", "assertIsNot", "assertIsNone", "assertIsNotNone",
    "assertIn", "assertNotIn", "assertRaises", "assertWarns",
    "assertAlmostEqual", "assertGreater", "assertLess",
    "assertRegex", "assertCountEqual", "assertDictEqual",
    "assertListEqual", "assertSetEqual", "assertTupleEqual",
    "assert_called", "assert_called_once", "assert_called_with",
    "assert_called_once_with", "assert_any_call", "assert_not_called",
}

# Weak assertion patterns — asserting almost nothing
_WEAK_PATTERNS = {"assertTrue", "assertFalse", "assertIsNotNone", "assertIsNone"}

# Mock-only assertion methods
_MOCK_ASSERT_METHODS = {
    "assert_called", "assert_called_once", "assert_called_with",
    "assert_called_once_with", "assert_any_call", "assert_not_called",
}


class AssertionCheckerRunner(BaseRunner):
    name = "assertion_checker"

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

            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if not node.name.startswith("test_"):
                    continue

                findings.extend(self._check_function(node, rel_path))

        return RunnerResult(
            runner=self.name,
            status=RunnerStatus.SUCCESS,
            findings=findings,
            duration_seconds=time.monotonic() - start,
        )

    def _check_function(self, func: ast.FunctionDef, file_path: str) -> list[Finding]:
        findings: list[Finding] = []
        assertions = self._collect_assertions(func)

        # No assertions at all
        if not assertions:
            findings.append(Finding(
                runner=self.name,
                severity=Severity.HIGH,
                category=Category.QUALITY,
                file=file_path,
                rule_id="no-assertions",
                message=f"Test `{func.name}` has no assertions — it only verifies code doesn't crash",
                line=func.lineno,
                fix_hint="Add explicit assertions that verify expected behavior",
            ))
            return findings

        # All assertions are weak (assertTrue, assertIsNotNone, etc.)
        assert_names = {a["name"] for a in assertions}
        bare_asserts = {a["name"] for a in assertions if a["name"] == "assert"}

        if assert_names <= _WEAK_PATTERNS | {"assert"}:
            # Check if bare asserts are just `assert True` or `assert x is not None`
            weak_count = sum(1 for a in assertions if self._is_weak_assert(a))
            if weak_count == len(assertions):
                findings.append(Finding(
                    runner=self.name,
                    severity=Severity.MEDIUM,
                    category=Category.QUALITY,
                    file=file_path,
                    rule_id="weak-assertions",
                    message=f"Test `{func.name}` only uses weak assertions (assertTrue/assertIsNotNone)",
                    line=func.lineno,
                    fix_hint="Use specific assertions like assertEqual, assertIn, assertRaises",
                ))

        # All assertions are mock-only
        if assert_names and assert_names <= _MOCK_ASSERT_METHODS:
            findings.append(Finding(
                runner=self.name,
                severity=Severity.MEDIUM,
                category=Category.QUALITY,
                file=file_path,
                rule_id="mock-only-assertions",
                message=f"Test `{func.name}` only asserts on mock calls — tests nothing real",
                line=func.lineno,
                fix_hint="Add assertions on actual return values or state changes",
            ))

        return findings

    def _collect_assertions(self, func: ast.FunctionDef) -> list[dict]:
        """Walk the function body and collect all assertion calls."""
        assertions = []

        for node in ast.walk(func):
            # Bare assert statement
            if isinstance(node, ast.Assert):
                assertions.append({
                    "name": "assert",
                    "node": node,
                    "line": node.lineno,
                })
                continue

            # Method calls: self.assertEqual(...), mock.assert_called(...)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                method_name = node.func.attr
                if method_name in _ASSERT_METHODS:
                    assertions.append({
                        "name": method_name,
                        "node": node,
                        "line": node.lineno,
                    })
                    continue

            # Pytest-style: plain assert handled above via ast.Assert

        return assertions

    def _is_weak_assert(self, assertion: dict) -> bool:
        """Check if an assertion is trivially weak."""
        node = assertion["node"]
        name = assertion["name"]

        if name in _WEAK_PATTERNS:
            return True

        # Bare `assert True` or `assert x is not None`
        if isinstance(node, ast.Assert):
            test = node.test
            # assert True / assert False
            if isinstance(test, ast.Constant) and isinstance(test.value, bool):
                return True
            # assert x is not None
            if isinstance(test, ast.Compare):
                if len(test.ops) == 1 and isinstance(test.ops[0], (ast.IsNot, ast.Is)):
                    if len(test.comparators) == 1:
                        comp = test.comparators[0]
                        if isinstance(comp, ast.Constant) and comp.value is None:
                            return True

        return False
