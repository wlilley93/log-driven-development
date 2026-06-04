"""Detect blocking/synchronous calls inside async functions."""

from __future__ import annotations

import ast

from viberapid.models import Category, Effort, Finding, Severity

TOOL_NAME = "ast-analyser"

# Mapping of (module, function) -> (rule_id, description, fix_hint)
BLOCKING_CALLS: dict[tuple[str, str], tuple[str, str, str]] = {
    ("time", "sleep"): (
        "py-sync-in-async",
        "time.sleep() blocks the event loop in async function",
        "Use asyncio.sleep() instead",
    ),
    ("requests", "get"): (
        "py-sync-in-async",
        "requests.get() blocks the event loop in async function",
        "Use aiohttp or httpx.AsyncClient instead",
    ),
    ("requests", "post"): (
        "py-sync-in-async",
        "requests.post() blocks the event loop in async function",
        "Use aiohttp or httpx.AsyncClient instead",
    ),
    ("requests", "put"): (
        "py-sync-in-async",
        "requests.put() blocks the event loop in async function",
        "Use aiohttp or httpx.AsyncClient instead",
    ),
    ("requests", "delete"): (
        "py-sync-in-async",
        "requests.delete() blocks the event loop in async function",
        "Use aiohttp or httpx.AsyncClient instead",
    ),
    ("requests", "patch"): (
        "py-sync-in-async",
        "requests.patch() blocks the event loop in async function",
        "Use aiohttp or httpx.AsyncClient instead",
    ),
    ("requests", "head"): (
        "py-sync-in-async",
        "requests.head() blocks the event loop in async function",
        "Use aiohttp or httpx.AsyncClient instead",
    ),
    ("requests", "options"): (
        "py-sync-in-async",
        "requests.options() blocks the event loop in async function",
        "Use aiohttp or httpx.AsyncClient instead",
    ),
    ("requests", "request"): (
        "py-sync-in-async",
        "requests.request() blocks the event loop in async function",
        "Use aiohttp or httpx.AsyncClient instead",
    ),
    ("os", "system"): (
        "py-sync-in-async",
        "os.system() blocks the event loop in async function",
        "Use asyncio.create_subprocess_shell() instead",
    ),
    ("subprocess", "run"): (
        "py-sync-in-async",
        "subprocess.run() blocks the event loop in async function",
        "Use asyncio.create_subprocess_exec() instead",
    ),
    ("subprocess", "call"): (
        "py-sync-in-async",
        "subprocess.call() blocks the event loop in async function",
        "Use asyncio.create_subprocess_exec() instead",
    ),
}


def _extract_call_parts(node: ast.Call) -> tuple[str | None, str | None]:
    """Extract (module, method) from a call node like `time.sleep(...)`."""
    func = node.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return func.value.id, func.attr
    return None, None


def _walk_for_blocking_calls(
    body: list[ast.stmt],
) -> list[tuple[int, str, str, str]]:
    """Walk AST body for blocking calls. Returns list of (line, rule_id, message, fix_hint)."""
    hits: list[tuple[int, str, str, str]] = []
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.Call):
            module, method = _extract_call_parts(node)
            if module and method:
                key = (module, method)
                if key in BLOCKING_CALLS:
                    rule_id, message, fix_hint = BLOCKING_CALLS[key]
                    hits.append((getattr(node, "lineno", 0), rule_id, message, fix_hint))
    return hits


def check(filepath: str, source: str) -> list[Finding]:
    """Check for blocking calls inside async functions."""
    findings: list[Finding] = []

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return findings

    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            hits = _walk_for_blocking_calls(node.body)
            for line, rule_id, message, fix_hint in hits:
                findings.append(
                    Finding(
                        tool=TOOL_NAME,
                        severity=Severity.HIGH,
                        category=Category.CODE,
                        file=filepath,
                        rule_id=rule_id,
                        rule_name="Blocking Call in Async Function",
                        message=f"{message} `{node.name}()`",
                        line=line,
                        fix_hint=fix_hint,
                        effort=Effort.MEDIUM,
                    )
                )

    return findings
