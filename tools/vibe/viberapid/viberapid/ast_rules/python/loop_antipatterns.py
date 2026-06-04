"""Detect loop anti-patterns: await-in-loop and nested comprehensions."""

from __future__ import annotations

import ast

from viberapid.models import Category, Effort, Finding, Severity

TOOL_NAME = "ast-analyser"


def _contains_await(body: list[ast.stmt]) -> list[int]:
    """Find lines with `await` expressions inside a body of statements."""
    lines: list[int] = []
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.Await):
            lines.append(getattr(node, "lineno", 0))
    return lines


def _contains_listcomp(body: list[ast.stmt]) -> list[int]:
    """Find lines with list comprehensions inside a body of statements."""
    lines: list[int] = []
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.ListComp):
            lines.append(getattr(node, "lineno", 0))
    return lines


def _check_await_in_loop(
    tree: ast.Module, filepath: str
) -> list[Finding]:
    """Detect `await` expressions inside for/while loops."""
    findings: list[Finding] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            loop_body = node.body + getattr(node, "orelse", [])
            await_lines = _contains_await(loop_body)

            for line in await_lines:
                # Skip if we're inside an AsyncFor — await is expected there
                # in some patterns, but we flag it for asyncio.gather consideration
                findings.append(
                    Finding(
                        tool=TOOL_NAME,
                        severity=Severity.HIGH,
                        category=Category.CODE,
                        file=filepath,
                        rule_id="py-await-in-loop",
                        rule_name="Await in Loop",
                        message=(
                            "Sequential `await` inside a loop — consider "
                            "asyncio.gather() for parallel execution"
                        ),
                        line=line,
                        fix_hint="Collect coroutines and use asyncio.gather() for parallel execution",
                        effort=Effort.MEDIUM,
                    )
                )

    return findings


def _check_nested_comprehension(
    tree: ast.Module, filepath: str
) -> list[Finding]:
    """Detect list comprehensions nested inside for-loops (potential O(n^2))."""
    findings: list[Finding] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            loop_body = node.body + getattr(node, "orelse", [])
            comp_lines = _contains_listcomp(loop_body)

            for line in comp_lines:
                findings.append(
                    Finding(
                        tool=TOOL_NAME,
                        severity=Severity.MEDIUM,
                        category=Category.CODE,
                        file=filepath,
                        rule_id="py-nested-comprehension",
                        rule_name="Nested Comprehension in Loop",
                        message=(
                            "List comprehension inside a loop — "
                            "potential O(n^2) complexity"
                        ),
                        line=line,
                        fix_hint="Restructure to avoid nested iteration or precompute the inner list",
                        effort=Effort.MEDIUM,
                    )
                )

    return findings


def check(filepath: str, source: str) -> list[Finding]:
    """Check for await-in-loop and nested comprehension anti-patterns."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    findings: list[Finding] = []
    findings.extend(_check_await_in_loop(tree, filepath))
    findings.extend(_check_nested_comprehension(tree, filepath))
    return findings
