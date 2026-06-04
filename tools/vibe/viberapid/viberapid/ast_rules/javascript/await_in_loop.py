"""Detect await expressions inside loops in JavaScript/TypeScript files."""

from __future__ import annotations

import re

from viberapid.models import Category, Effort, Finding, Severity

TOOL_NAME = "ast-analyser"
RULE_ID = "js-await-in-loop"
RULE_NAME = "Await in Loop"
FIX_HINT = "Use Promise.all() for parallel execution"

# ── Loop-start patterns ─────────────────────────────────────────────────────
# Only true iteration constructs — for/while/do.
# Array higher-order methods (.forEach, .map, etc.) are handled separately
# because their callbacks create a new function scope.
LOOP_START_PATTERNS = [
    re.compile(r"^\s*for\s*\("),           # for (
    re.compile(r"^\s*for\s+"),             # for ...of, for ...in
    re.compile(r"^\s*while\s*\("),         # while (
    re.compile(r"^\s*do\s*\{"),            # do {
]

# Array iteration methods whose async callbacks are a perf concern.
# Only .forEach() is flagged — it discards return values, so async callbacks
# with await are genuine fire-and-forget problems.
# .map(), .flatMap(), .filter(), .reduce(), .some(), .every(), .find(),
# .findIndex() all return values and are the correct Promise.all() pattern.
ARRAY_ITER_PATTERN = re.compile(
    r"\.\s*forEach\s*\("
)

# ── Keyword/token patterns ──────────────────────────────────────────────────
AWAIT_PATTERN = re.compile(r"\bawait\s+")

# Detects the opening of a new function scope (function decl, arrow, method).
FUNCTION_SCOPE_PATTERNS = [
    re.compile(r"\basync\s+function\b"),
    re.compile(r"\bfunction\s*[\w$]*\s*\("),
    re.compile(r"\basync\s+(?:\([^)]*\)|[\w$]+)\s*=>\s*\{"),
    re.compile(r"(?:\([^)]*\)|[\w$]+)\s*=>\s*\{"),
]

# Patterns for single-line comments and strings to skip
SINGLE_LINE_COMMENT = re.compile(r"//.*$")
BLOCK_COMMENT_OPEN = re.compile(r"/\*")
BLOCK_COMMENT_CLOSE = re.compile(r"\*/")

# Suppression comment: lines containing "// sequential:" are intentionally sequential
SEQUENTIAL_SUPPRESS = re.compile(r"//\s*sequential:", re.IGNORECASE)


def _strip_strings_and_comments(line: str) -> str:
    """Remove string literals and single-line comments from a line for analysis."""
    line = SINGLE_LINE_COMMENT.sub("", line)

    result: list[str] = []
    i = 0
    in_str: str | None = None
    while i < len(line):
        ch = line[i]
        if in_str:
            if ch == in_str and (i == 0 or line[i - 1] != "\\"):
                in_str = None
            i += 1
            continue
        if ch in ("'", '"', "`"):
            in_str = ch
            i += 1
            continue
        result.append(ch)
        i += 1

    return "".join(result)


def _is_loop_start(stripped: str) -> bool:
    """Check if a stripped line starts a true loop construct (for/while/do)."""
    for pattern in LOOP_START_PATTERNS:
        if pattern.search(stripped):
            return True
    return False


def _is_array_iter(stripped: str) -> bool:
    """Check if the line contains an array iteration method call."""
    return bool(ARRAY_ITER_PATTERN.search(stripped))


def _has_function_scope_opening(stripped: str) -> bool:
    """Check if the line opens a new function scope with a brace."""
    for pattern in FUNCTION_SCOPE_PATTERNS:
        if pattern.search(stripped):
            return True
    return False


# Scope-entry kinds ──────────────────────────────────────────────────────────
_LOOP = "loop"
_FUNC = "func"       # nested function scope — shields await from outer loop
_ARRAY_ITER = "arr"  # .forEach / .map etc. — treated as loop-like scope


def check(filepath: str, source: str) -> list[Finding]:
    """Detect await inside loop constructs in JS/TS files.

    Improvements over the original approach:

    1. Properly tracks **function scope boundaries**.  When a nested function
       or arrow function opens inside a loop, any ``await`` inside that
       function body is **not** attributed to the enclosing loop.

    2. Array iteration methods (``.forEach``, ``.map``, ...) are treated as a
       loop-like scope, but only the **direct** body of the async callback is
       considered -- nested functions inside the callback are shielded.

    3. One-liner callbacks (arrow functions without ``{}``) no longer leave
       phantom "open loop" entries on the stack.

    4. Handles loop headers split across lines (``for (...)`` on one line,
       ``{`` on the next).
    """
    findings: list[Finding] = []
    lines = source.split("\n")

    in_block_comment = False
    brace_depth = 0

    # Stack of [kind, start_line, close_depth].
    # ``close_depth`` is the brace depth at which the scope *closes* (i.e.,
    # the depth just before the opening ``{``).  The scope is active when
    # ``brace_depth > close_depth``.
    scope_stack: list[list] = []  # mutable entries: [kind, start_line, close_depth]

    # Pending loop/array-iter entries waiting for their opening ``{``.
    # Each entry is [kind, start_line].  When the next ``{`` is seen, we
    # convert it into a scope_stack entry with the correct close_depth.
    pending_scopes: list[list] = []

    for line_num_0, raw_line in enumerate(lines):
        line_num = line_num_0 + 1

        # Handle block comments
        working = raw_line
        if in_block_comment:
            close_match = BLOCK_COMMENT_CLOSE.search(working)
            if close_match:
                working = working[close_match.end():]
                in_block_comment = False
            else:
                continue

        # Remove any block comment openings on this line
        while True:
            open_match = BLOCK_COMMENT_OPEN.search(working)
            if not open_match:
                break
            close_match = BLOCK_COMMENT_CLOSE.search(working, open_match.end())
            if close_match:
                working = working[:open_match.start()] + working[close_match.end():]
            else:
                working = working[:open_match.start()]
                in_block_comment = True
                break

        stripped = _strip_strings_and_comments(working)

        opens = stripped.count("{")
        closes = stripped.count("}")

        # ── Detect scope entries BEFORE updating brace_depth ─────────────

        is_loop = _is_loop_start(stripped)
        is_arr = _is_array_iter(stripped)
        has_func = _has_function_scope_opening(stripped)

        # Activate any pending scopes if this line has opening braces.
        # Each pending scope consumes one opening brace for its activation.
        if pending_scopes and opens > 0:
            activated = 0
            for ps in pending_scopes:
                if activated >= opens:
                    break
                # The close_depth is the depth just before this brace opens.
                close_depth = brace_depth + activated
                scope_stack.append([ps[0], ps[1], close_depth])
                activated += 1
            pending_scopes.clear()
        elif pending_scopes and opens == 0:
            # Still waiting — keep pending (loop header may span multiple lines
            # e.g., for (\n  const x of items\n) {\n).
            pass

        if is_arr:
            if opens > 0:
                # The callback has a block body.
                # close_depth = current depth (before this line's braces).
                scope_stack.append([_ARRAY_ITER, line_num, brace_depth])
                # If there's also a nested function scope on the same line
                if has_func and opens >= 2:
                    scope_stack.append([_FUNC, line_num, brace_depth + 1])
            # else: one-liner callback (expression body) — no scope to track.

        elif is_loop:
            if opens > 0:
                scope_stack.append([_LOOP, line_num, brace_depth])
                if has_func and opens >= 2:
                    scope_stack.append([_FUNC, line_num, brace_depth + 1])
            else:
                # Loop header without ``{`` — defer until we see the brace.
                pending_scopes.append([_LOOP, line_num])

        elif has_func:
            # Function scope that is NOT on a loop/array-iter line.
            if opens > 0 and _inside_loop(scope_stack):
                scope_stack.append([_FUNC, line_num, brace_depth])

        # ── Update brace depth ───────────────────────────────────────────
        brace_depth += opens - closes

        # ── Pop scopes that have closed ──────────────────────────────────
        # A scope closes when brace_depth drops to (or below) its close_depth.
        while scope_stack and brace_depth <= scope_stack[-1][2]:
            scope_stack.pop()

        # Also discard any pending scopes if brace depth went down (meaning
        # the loop-like construct never got a body).
        if pending_scopes and closes > opens:
            pending_scopes.clear()

        # ── Check for await inside a loop ────────────────────────────────
        if AWAIT_PATTERN.search(stripped) and _directly_in_loop(scope_stack):
            loop_line = _innermost_loop_line(scope_stack)
            # Suppress if the await line, the loop-opening line, or the line
            # immediately above the loop-opening line has a "// sequential:"
            # comment (case-insensitive).
            await_suppressed = SEQUENTIAL_SUPPRESS.search(raw_line)
            loop_suppressed = SEQUENTIAL_SUPPRESS.search(lines[loop_line - 1]) if loop_line > 0 else None
            line_above_loop_suppressed = (
                SEQUENTIAL_SUPPRESS.search(lines[loop_line - 2])
                if loop_line >= 2
                else None
            )
            if not await_suppressed and not loop_suppressed and not line_above_loop_suppressed:
                findings.append(
                    Finding(
                        tool=TOOL_NAME,
                        severity=Severity.HIGH,
                        category=Category.CODE,
                        file=filepath,
                        rule_id=RULE_ID,
                        rule_name=RULE_NAME,
                        message=(
                            f"Sequential `await` inside a loop (loop started at line "
                            f"{loop_line}) — each iteration waits for the "
                            f"previous to complete"
                        ),
                        line=line_num,
                        fix_hint=FIX_HINT,
                        effort=Effort.MEDIUM,
                    )
                )

    return findings


def _inside_loop(scope_stack: list[list]) -> bool:
    """Return True if there is any loop or array-iter scope on the stack."""
    return any(entry[0] in (_LOOP, _ARRAY_ITER) for entry in scope_stack)


def _directly_in_loop(scope_stack: list[list]) -> bool:
    """Return True if the current position is directly inside a loop body.

    "Directly" means the innermost scope on the stack is a loop (or
    array-iter), **not** a nested function scope.  If the innermost scope is
    _FUNC, the await is inside a callback/nested function and should NOT be
    attributed to the enclosing loop.
    """
    if not scope_stack:
        return False

    for entry in reversed(scope_stack):
        kind = entry[0]
        if kind == _FUNC:
            return False
        if kind in (_LOOP, _ARRAY_ITER):
            return True

    return False


def _innermost_loop_line(scope_stack: list[list]) -> int:
    """Return the start line of the innermost loop scope."""
    for entry in reversed(scope_stack):
        if entry[0] in (_LOOP, _ARRAY_ITER):
            return entry[1]
    return 0
