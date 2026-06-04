"""Detect json.loads(json.dumps(x)) deep copy anti-pattern."""

from __future__ import annotations

import ast

from viberapid.models import Category, Effort, Finding, Severity

TOOL_NAME = "ast-analyser"
RULE_ID = "py-json-deepcopy"
RULE_NAME = "JSON Deep Copy Anti-pattern"
FIX_HINT = "Use copy.deepcopy() instead of json.loads(json.dumps())"


def _is_json_call(node: ast.Call, module: str, method: str) -> bool:
    """Check if a Call node is `json.<method>(...)`."""
    func = node.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return func.value.id == module and func.attr == method
    return False


def check(filepath: str, source: str) -> list[Finding]:
    """Detect json.loads(json.dumps(x)) anti-pattern for deep copying."""
    findings: list[Finding] = []

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return findings

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        # Look for json.loads(<inner>)
        if not _is_json_call(node, "json", "loads"):
            continue

        # Check if the single positional argument is json.dumps(...)
        if not node.args:
            continue

        inner = node.args[0]
        if isinstance(inner, ast.Call) and _is_json_call(inner, "json", "dumps"):
            findings.append(
                Finding(
                    tool=TOOL_NAME,
                    severity=Severity.MEDIUM,
                    category=Category.CODE,
                    file=filepath,
                    rule_id=RULE_ID,
                    rule_name=RULE_NAME,
                    message=(
                        "json.loads(json.dumps(x)) used for deep copying — "
                        "this is slow, loses non-JSON types, and has edge cases"
                    ),
                    line=getattr(node, "lineno", 0),
                    fix_hint=FIX_HINT,
                    effort=Effort.LOW,
                )
            )

    return findings
