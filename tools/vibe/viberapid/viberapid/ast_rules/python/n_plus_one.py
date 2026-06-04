"""Detect N+1 query patterns — ORM calls inside loops."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from viberapid.models import Category, Effort, Finding, Severity

if TYPE_CHECKING:
    pass

TOOL_NAME = "ast-analyser"
RULE_ID = "py-n-plus-one"
RULE_NAME = "N+1 Query in Loop"
FIX_HINT = "Move query outside loop or use prefetch_related/select_related"

# Methods that are ONLY used on ORM querysets / DB cursors — not generic Python
# We exclude common dict/list/set methods like .get(), .count(), .update(), .delete()
# to avoid false positives on dict.get(), str.count(), set.update(), etc.
ORM_ONLY_METHODS = frozenset({
    "filter",
    "exclude",
    "annotate",
    "aggregate",
    "values_list",
    "prefetch_related",
    "select_related",
    "bulk_create",
    "bulk_update",
    "executemany",
    "fetchone",
    "fetchall",
    "fetchmany",
    "find_one",
    "find_many",
    "insert_one",
    "insert_many",
    "update_one",
    "update_many",
    "delete_one",
    "delete_many",
})

# Methods that are ambiguous — only flag if the receiver looks like a queryset
# (i.e., chained after another ORM method, or receiver name contains 'qs', 'queryset',
# 'objects', 'cursor', 'db', 'session', 'collection')
AMBIGUOUS_METHODS = frozenset({
    "all",
    "get",
    "create",
    "save",
    "first",
    "last",
    "count",
    "exists",
    "execute",
    "query",
    "find",
    "insert",
    "update",
    "delete",
    "values",
})

# Receiver names that suggest an ORM/DB context
ORM_RECEIVER_HINTS = frozenset({
    "objects", "qs", "queryset", "cursor", "db", "session",
    "collection", "conn", "connection", "table", "model",
})


def _get_receiver_name(node: ast.Call) -> str | None:
    """Get the name of the object the method is called on (e.g., 'qs' in qs.filter())."""
    if isinstance(node.func, ast.Attribute):
        value = node.func.value
        if isinstance(value, ast.Name):
            return value.id
        if isinstance(value, ast.Attribute):
            return value.attr
        if isinstance(value, ast.Call):
            # Chained call like Model.objects.filter().get()
            return _get_call_method(value)
    return None


def _get_call_method(node: ast.Call) -> str | None:
    """Get the method name from a call node."""
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    if isinstance(node.func, ast.Name):
        return node.func.id
    return None


def _is_orm_context(node: ast.Call, method_name: str) -> bool:
    """Determine if a method call is likely an ORM/DB call vs a regular Python method."""
    if method_name in ORM_ONLY_METHODS:
        return True

    if method_name not in AMBIGUOUS_METHODS:
        return False

    # Check if receiver name hints at ORM
    receiver = _get_receiver_name(node)
    if receiver and receiver.lower() in ORM_RECEIVER_HINTS:
        return True

    # Check if this is chained after a definitive ORM method (e.g., Model.objects.all().get())
    # Only flag if chained after ORM_ONLY methods — chaining after ambiguous methods
    # like .get().get() is likely dict access, not ORM
    if isinstance(node.func, ast.Attribute):
        value = node.func.value
        if isinstance(value, ast.Call):
            parent_method = _get_call_method(value)
            if parent_method and parent_method in ORM_ONLY_METHODS:
                return True

    # Check for .objects accessor (Model.objects.get())
    if isinstance(node.func, ast.Attribute):
        value = node.func.value
        if isinstance(value, ast.Attribute) and value.attr == "objects":
            return True

    return False


def _has_strong_orm_context(node: ast.Call) -> bool:
    """Return True if the call has a strong ORM context indicator.

    Strong indicators: receiver name is in ORM_RECEIVER_HINTS, or the call
    uses the .objects accessor (Model.objects.get()).  These make it very
    likely the call is a real DB query, not a dict/list operation.
    """
    receiver = _get_receiver_name(node)
    if receiver and receiver.lower() in ORM_RECEIVER_HINTS:
        return True
    # Check .objects accessor
    if isinstance(node.func, ast.Attribute):
        value = node.func.value
        if isinstance(value, ast.Attribute) and value.attr == "objects":
            return True
    # Chained after ORM_ONLY method
    if isinstance(node.func, ast.Attribute):
        value = node.func.value
        if isinstance(value, ast.Call):
            parent_method = _get_call_method(value)
            if parent_method and parent_method in ORM_ONLY_METHODS:
                return True
    return False


def _find_orm_calls_in_body(body: list[ast.stmt]) -> list[tuple[int, str]]:
    """Walk a list of statements and find ORM-like calls. Returns (line, method_name).

    To reduce false positives on structural iteration (processing already-
    fetched rows), ambiguous methods (get, count, values, etc.) without
    strong ORM context are only reported when the loop body also contains
    a definitive ORM/DB call.  This prevents flagging patterns like
    ``row.get("name")`` or ``item.values()`` on already-fetched dict-like
    row objects.

    ORM-only methods (filter, select_related, fetchall, etc.) and ambiguous
    methods with strong ORM context (e.g. ``objects.get()``,
    ``session.execute()``) are always reported.
    """
    all_calls: list[tuple[int, str, bool]] = []  # (line, method, is_definitive)
    has_definitive = False

    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.Call):
            method = _get_call_method(node)
            if not method:
                continue
            if method in ORM_ONLY_METHODS:
                has_definitive = True
                all_calls.append((getattr(node, "lineno", 0), method, True))
            elif _is_orm_context(node, method):
                # Ambiguous method — definitive if it has strong ORM context
                strong = _has_strong_orm_context(node)
                if strong:
                    has_definitive = True
                all_calls.append((getattr(node, "lineno", 0), method, strong))

    hits: list[tuple[int, str]] = []
    for line, method, is_definitive in all_calls:
        if is_definitive or has_definitive:
            hits.append((line, method))
    return hits


def check(filepath: str, source: str) -> list[Finding]:
    """Check for ORM queries inside for-loops (N+1 pattern)."""
    findings: list[Finding] = []

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return findings

    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            loop_body = node.body + getattr(node, "orelse", [])
            orm_hits = _find_orm_calls_in_body(loop_body)

            for line, method_name in orm_hits:
                findings.append(
                    Finding(
                        tool=TOOL_NAME,
                        severity=Severity.CRITICAL,
                        category=Category.DATABASE,
                        file=filepath,
                        rule_id=RULE_ID,
                        rule_name=RULE_NAME,
                        message=(
                            f"ORM method `.{method_name}()` called inside a loop "
                            f"(potential N+1 query)"
                        ),
                        line=line,
                        fix_hint=FIX_HINT,
                        effort=Effort.MEDIUM,
                    )
                )

    return findings
