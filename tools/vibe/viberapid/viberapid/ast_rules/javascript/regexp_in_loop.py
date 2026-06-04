"""Detect new RegExp() creation inside loops."""

from __future__ import annotations

import re

from viberapid.models import Category, Effort, Finding, Severity

TOOL_NAME = "ast-analyser"
RULE_ID = "js-regexp-in-loop"
RULE_NAME = "RegExp Creation in Loop"
FIX_HINT = "Hoist RegExp creation outside the loop"

# Loop start patterns
LOOP_PATTERNS = [
    re.compile(r"^\s*for\s*\("),
    re.compile(r"^\s*for\s+"),
    re.compile(r"^\s*while\s*\("),
    re.compile(r"^\s*do\s*\{"),
    re.compile(r"\.\s*forEach\s*\("),
    re.compile(r"\.\s*map\s*\("),
    re.compile(r"\.\s*filter\s*\("),
    re.compile(r"\.\s*reduce\s*\("),
    re.compile(r"\.\s*some\s*\("),
    re.compile(r"\.\s*every\s*\("),
    re.compile(r"\.\s*find\s*\("),
    re.compile(r"\.\s*findIndex\s*\("),
    re.compile(r"\.\s*flatMap\s*\("),
]

# Pattern for new RegExp(
NEW_REGEXP_PATTERN = re.compile(r"\bnew\s+RegExp\s*\(")

# Comment patterns
COMMENT_RE = re.compile(r"//.*$")
BLOCK_COMMENT_OPEN = re.compile(r"/\*")
BLOCK_COMMENT_CLOSE = re.compile(r"\*/")


def _strip_strings_and_comments(line: str) -> str:
    """Remove string literals and single-line comments for analysis."""
    line = COMMENT_RE.sub("", line)

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
    """Check if a stripped line starts a loop construct."""
    for pattern in LOOP_PATTERNS:
        if pattern.search(stripped):
            return True
    return False


def check(filepath: str, source: str) -> list[Finding]:
    """Detect new RegExp() inside loop bodies."""
    findings: list[Finding] = []
    lines = source.split("\n")

    in_block_comment = False
    brace_depth = 0
    loop_stack: list[tuple[int, int]] = []  # (start_line, brace_depth_at_start)

    for line_idx, raw_line in enumerate(lines):
        line_num = line_idx + 1

        # Handle block comments
        working = raw_line
        if in_block_comment:
            if BLOCK_COMMENT_CLOSE.search(working):
                in_block_comment = False
            continue
        if BLOCK_COMMENT_OPEN.search(working) and not BLOCK_COMMENT_CLOSE.search(working):
            in_block_comment = True
            working = working[:BLOCK_COMMENT_OPEN.search(working).start()]  # type: ignore[union-attr]

        stripped = _strip_strings_and_comments(working)

        # Track brace depth
        opens = stripped.count("{")
        closes = stripped.count("}")

        # Detect loop start
        if _is_loop_start(stripped):
            loop_stack.append((line_num, brace_depth + opens))

        brace_depth += opens - closes

        # Pop loops that have closed
        while loop_stack and brace_depth < loop_stack[-1][1]:
            loop_stack.pop()

        # Check for new RegExp( inside a loop
        if loop_stack and NEW_REGEXP_PATTERN.search(stripped):
            findings.append(
                Finding(
                    tool=TOOL_NAME,
                    severity=Severity.MEDIUM,
                    category=Category.CODE,
                    file=filepath,
                    rule_id=RULE_ID,
                    rule_name=RULE_NAME,
                    message=(
                        f"`new RegExp()` created inside a loop "
                        f"(loop at line {loop_stack[-1][0]}) — "
                        f"compiled on every iteration"
                    ),
                    line=line_num,
                    fix_hint=FIX_HINT,
                    effort=Effort.LOW,
                )
            )

    return findings
