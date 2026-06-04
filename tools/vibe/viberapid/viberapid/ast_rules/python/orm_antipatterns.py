"""Detect ORM anti-patterns: SELECT * in raw SQL, .all().filter() chains."""

from __future__ import annotations

import ast
import re

from viberapid.models import Category, Effort, Finding, Severity

TOOL_NAME = "ast-analyser"

# Pattern to match SELECT * in SQL strings (case-insensitive)
SELECT_STAR_RE = re.compile(r"\bSELECT\s+\*\s+FROM\b", re.IGNORECASE)


def _check_select_star(tree: ast.Module, filepath: str) -> list[Finding]:
    """Find string literals containing SELECT * FROM."""
    findings: list[Finding] = []

    for node in ast.walk(tree):
        # Check regular string constants
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if SELECT_STAR_RE.search(node.value):
                findings.append(
                    Finding(
                        tool=TOOL_NAME,
                        severity=Severity.HIGH,
                        category=Category.DATABASE,
                        file=filepath,
                        rule_id="py-select-star",
                        rule_name="SELECT * in Raw SQL",
                        message=(
                            "Raw SQL contains `SELECT *` — fetches all columns "
                            "even when only a subset is needed"
                        ),
                        line=getattr(node, "lineno", 0),
                        fix_hint="Specify only the columns you need: SELECT col1, col2 FROM ...",
                        effort=Effort.LOW,
                    )
                )

        # Check f-strings (JoinedStr)
        if isinstance(node, ast.JoinedStr):
            # Reconstruct partial string from constant parts
            parts: list[str] = []
            for value in node.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    parts.append(value.value)
                else:
                    parts.append("?")  # placeholder for expressions

            joined = "".join(parts)
            if SELECT_STAR_RE.search(joined):
                findings.append(
                    Finding(
                        tool=TOOL_NAME,
                        severity=Severity.HIGH,
                        category=Category.DATABASE,
                        file=filepath,
                        rule_id="py-select-star",
                        rule_name="SELECT * in Raw SQL",
                        message=(
                            "f-string contains `SELECT *` — fetches all columns "
                            "even when only a subset is needed"
                        ),
                        line=getattr(node, "lineno", 0),
                        fix_hint="Specify only the columns you need: SELECT col1, col2 FROM ...",
                        effort=Effort.LOW,
                    )
                )

    return findings


def _check_all_before_filter(tree: ast.Module, filepath: str) -> list[Finding]:
    """Detect .all().filter() chains — loads everything then filters in Python."""
    findings: list[Finding] = []

    for node in ast.walk(tree):
        # Look for call chains: something.all().filter(...)
        # In the AST this is:
        #   Call(func=Attribute(value=Call(func=Attribute(attr='all')), attr='filter'))
        if not isinstance(node, ast.Call):
            continue

        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "filter":
            continue

        # The value of .filter should be a Call to .all()
        inner_call = func.value
        if not isinstance(inner_call, ast.Call):
            continue

        inner_func = inner_call.func
        if isinstance(inner_func, ast.Attribute) and inner_func.attr == "all":
            findings.append(
                Finding(
                    tool=TOOL_NAME,
                    severity=Severity.MEDIUM,
                    category=Category.DATABASE,
                    file=filepath,
                    rule_id="py-all-before-filter",
                    rule_name=".all().filter() Chain",
                    message=(
                        "`.all().filter()` loads all records then filters — "
                        "use `.filter()` directly for database-level filtering"
                    ),
                    line=getattr(node, "lineno", 0),
                    fix_hint="Use .filter() directly instead of .all().filter()",
                    effort=Effort.LOW,
                )
            )

    return findings


def check(filepath: str, source: str) -> list[Finding]:
    """Check for ORM anti-patterns in Python source."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    findings: list[Finding] = []
    findings.extend(_check_select_star(tree, filepath))
    findings.extend(_check_all_before_filter(tree, filepath))
    return findings
