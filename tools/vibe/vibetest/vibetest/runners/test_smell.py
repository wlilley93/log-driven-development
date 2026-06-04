"""Test smell detector — AST-based detection of common test anti-patterns."""

from __future__ import annotations

import ast
import hashlib
import re
import time
from pathlib import Path

from vibetest.models import Category, Finding, RunnerResult, RunnerStatus, Severity
from vibetest.runners.base import BaseRunner

_BAD_TEST_NAMES = re.compile(
    r"^test_?(\d+|it|this|that|foo|bar|baz|stuff|thing|works|ok|test)$",
    re.IGNORECASE,
)

_HARDCODED_PATH = re.compile(
    r"""['"](/(?:Users|home|tmp|var|etc|opt)/[^'"]+|[A-Z]:\\[^'"]+)['"]"""
)

_HARDCODED_URL = re.compile(
    r"""['"]https?://(?!example\.com|localhost|127\.0\.0\.1)[^'"]+['"]"""
)

# Assert methods to count
_ASSERT_NAMES = {
    "assert", "assertEqual", "assertNotEqual", "assertTrue", "assertFalse",
    "assertIs", "assertIsNot", "assertIsNone", "assertIsNotNone",
    "assertIn", "assertNotIn", "assertRaises", "assertWarns",
    "assertAlmostEqual", "assertGreater", "assertLess",
}


class TestSmellRunner(BaseRunner):
    name = "test_smell"

    def should_run(self) -> bool:
        if not self._find_test_files():
            self.skip_reason = "no test files found"
            return False
        return True

    def run(self) -> RunnerResult:
        start = time.monotonic()
        tc = self.runner_config
        god_test_lines = tc.get("god_test_lines", 50)
        max_assertions = tc.get("max_assertions", 10)

        findings: list[Finding] = []
        body_hashes: dict[str, list[tuple[str, str, int]]] = {}  # hash -> [(file, name, line)]

        test_files = self._find_test_files()

        for test_file in test_files:
            tree = self._parse_ast(test_file)
            if tree is None:
                continue

            rel_path = str(test_file.relative_to(Path(self.target)))
            source_lines = test_file.read_text(encoding="utf-8", errors="replace").splitlines()

            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if not node.name.startswith("test_"):
                    continue

                # God test (too many lines)
                end_line = getattr(node, "end_lineno", node.lineno)
                test_length = end_line - node.lineno + 1
                if test_length > god_test_lines:
                    findings.append(Finding(
                        runner=self.name,
                        severity=Severity.LOW,
                        category=Category.SMELL,
                        file=rel_path,
                        rule_id="god-test",
                        message=f"Test `{node.name}` is {test_length} lines (>{god_test_lines})",
                        line=node.lineno,
                        fix_hint="Break into smaller, focused test functions",
                    ))

                # Too many assertions
                assertion_count = self._count_assertions(node)
                if assertion_count > max_assertions:
                    findings.append(Finding(
                        runner=self.name,
                        severity=Severity.LOW,
                        category=Category.SMELL,
                        file=rel_path,
                        rule_id="too-many-assertions",
                        message=f"Test `{node.name}` has {assertion_count} assertions (>{max_assertions})",
                        line=node.lineno,
                        fix_hint="Split into separate tests, each verifying one behavior",
                    ))

                # Bad test name
                if _BAD_TEST_NAMES.match(node.name):
                    findings.append(Finding(
                        runner=self.name,
                        severity=Severity.LOW,
                        category=Category.SMELL,
                        file=rel_path,
                        rule_id="bad-test-name",
                        message=f"Test `{node.name}` doesn't describe the behavior being tested",
                        line=node.lineno,
                        fix_hint="Use descriptive names like test_login_rejects_invalid_password",
                    ))

                # Sleep calls
                for child in ast.walk(node):
                    if (isinstance(child, ast.Call)
                            and isinstance(child.func, ast.Attribute)
                            and child.func.attr == "sleep"):
                        findings.append(Finding(
                            runner=self.name,
                            severity=Severity.MEDIUM,
                            category=Category.SMELL,
                            file=rel_path,
                            rule_id="sleep-in-test",
                            message=f"Test `{node.name}` uses sleep() — makes tests slow and brittle",
                            line=child.lineno,
                            fix_hint="Use polling, events, or mock time instead of sleep",
                        ))
                        break  # One finding per test

                # Hardcoded paths/URLs in source lines
                if hasattr(node, "end_lineno"):
                    test_source = "\n".join(source_lines[node.lineno - 1:node.end_lineno])
                    if _HARDCODED_PATH.search(test_source):
                        findings.append(Finding(
                            runner=self.name,
                            severity=Severity.LOW,
                            category=Category.SMELL,
                            file=rel_path,
                            rule_id="hardcoded-path",
                            message=f"Test `{node.name}` contains hardcoded file paths",
                            line=node.lineno,
                            fix_hint="Use tmp_path fixture or os.path.join with relative paths",
                        ))
                    if _HARDCODED_URL.search(test_source):
                        findings.append(Finding(
                            runner=self.name,
                            severity=Severity.LOW,
                            category=Category.SMELL,
                            file=rel_path,
                            rule_id="hardcoded-url",
                            message=f"Test `{node.name}` contains hardcoded URLs",
                            line=node.lineno,
                            fix_hint="Use constants or fixtures for test URLs",
                        ))

                # Track body hash for copy-paste detection
                body_hash = self._hash_body(node)
                body_hashes.setdefault(body_hash, []).append((rel_path, node.name, node.lineno))

        # Copy-paste tests (identical bodies)
        for body_hash, locations in body_hashes.items():
            if len(locations) > 1:
                names = ", ".join(f"`{name}`" for _, name, _ in locations)
                for file_path, name, line in locations:
                    findings.append(Finding(
                        runner=self.name,
                        severity=Severity.MEDIUM,
                        category=Category.SMELL,
                        file=file_path,
                        rule_id="copy-paste-test",
                        message=f"Test `{name}` has identical body to {len(locations)-1} other test(s): {names}",
                        line=line,
                        fix_hint="Use parametrize or extract shared logic into a helper",
                    ))

        return RunnerResult(
            runner=self.name,
            status=RunnerStatus.SUCCESS,
            findings=findings,
            duration_seconds=time.monotonic() - start,
        )

    def _count_assertions(self, func: ast.FunctionDef) -> int:
        count = 0
        for node in ast.walk(func):
            if isinstance(node, ast.Assert):
                count += 1
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in _ASSERT_NAMES:
                    count += 1
        return count

    def _hash_body(self, func: ast.FunctionDef) -> str:
        """Hash the AST dump of a function body for copy-paste detection."""
        body_dump = ast.dump(ast.Module(body=func.body, type_ignores=[]))
        return hashlib.md5(body_dump.encode()).hexdigest()
