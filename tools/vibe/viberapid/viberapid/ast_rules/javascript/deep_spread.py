"""Detect deeply nested object spreads that create unnecessary copies."""

from __future__ import annotations

import re

from viberapid.models import Category, Effort, Finding, Severity

TOOL_NAME = "ast-analyser"
RULE_ID = "js-deep-spread"
RULE_NAME = "Deeply Nested Object Spread"
FIX_HINT = "Use immer or structured clone for deep updates"

# Pattern to detect triple-nested spreads:
#   { ...obj, key: { ...obj.key, nested: { ...obj.key.nested, ... } } }
# We look for lines with 3+ spread operators on the same logical expression

# Individual spread: `...identifier` or `...expression`
SPREAD_PATTERN = re.compile(r"\.\.\.\s*\w+")

# Comment patterns
COMMENT_RE = re.compile(r"//.*$")
BLOCK_COMMENT_OPEN = re.compile(r"/\*")
BLOCK_COMMENT_CLOSE = re.compile(r"\*/")

# Minimum number of spreads on a single line/expression to flag
MIN_SPREADS = 3


def _strip_strings(line: str) -> str:
    """Remove string literals from a line for analysis."""
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


def _count_spread_depth(lines: list[str], start_idx: int) -> tuple[int, int]:
    """Count the nesting depth of spread operators starting from a line.

    Looks at the current line and accumulates over continuation lines
    (lines that are part of the same expression, tracked by brace depth).

    Returns (spread_count, span_lines).
    """
    spread_count = 0
    brace_depth = 0
    started = False

    for offset in range(min(20, len(lines) - start_idx)):
        line = _strip_strings(COMMENT_RE.sub("", lines[start_idx + offset]))

        # Count spreads on this line
        spread_count += len(SPREAD_PATTERN.findall(line))

        # Track brace nesting
        opens = line.count("{")
        closes = line.count("}")
        brace_depth += opens - closes

        if opens > 0:
            started = True

        # If we've closed all the braces we opened, stop
        if started and brace_depth <= 0:
            return spread_count, offset + 1

    return spread_count, 1


def check(filepath: str, source: str) -> list[Finding]:
    """Detect deeply nested spread operators."""
    findings: list[Finding] = []
    lines = source.split("\n")
    in_block_comment = False
    already_flagged: set[int] = set()

    for line_idx, raw_line in enumerate(lines):
        line_num = line_idx + 1

        # Handle block comments
        if in_block_comment:
            if BLOCK_COMMENT_CLOSE.search(raw_line):
                in_block_comment = False
            continue
        if BLOCK_COMMENT_OPEN.search(raw_line) and not BLOCK_COMMENT_CLOSE.search(raw_line):
            in_block_comment = True
            continue

        if line_num in already_flagged:
            continue

        stripped = _strip_strings(COMMENT_RE.sub("", raw_line))

        # Quick pre-check: does this line have at least one spread?
        if "..." not in stripped:
            continue

        # Check if this line starts a deeply-nested spread expression
        # Look for patterns like: { ...a, key: { ...b, ... }}
        spreads_on_line = len(SPREAD_PATTERN.findall(stripped))

        if spreads_on_line >= MIN_SPREADS:
            findings.append(
                Finding(
                    tool=TOOL_NAME,
                    severity=Severity.MEDIUM,
                    category=Category.RENDER,
                    file=filepath,
                    rule_id=RULE_ID,
                    rule_name=RULE_NAME,
                    message=(
                        f"Deeply nested object spread ({spreads_on_line} spread "
                        f"operators) — creates multiple shallow copies on every call"
                    ),
                    line=line_num,
                    fix_hint=FIX_HINT,
                    effort=Effort.MEDIUM,
                )
            )
            already_flagged.add(line_num)
            continue

        # If this line has a spread and opens braces, check multi-line expression
        if spreads_on_line >= 1 and "{" in stripped:
            total_spreads, span = _count_spread_depth(lines, line_idx)
            if total_spreads >= MIN_SPREADS:
                findings.append(
                    Finding(
                        tool=TOOL_NAME,
                        severity=Severity.MEDIUM,
                        category=Category.RENDER,
                        file=filepath,
                        rule_id=RULE_ID,
                        rule_name=RULE_NAME,
                        message=(
                            f"Deeply nested object spread ({total_spreads} spread "
                            f"operators across {span} lines) — creates multiple "
                            f"shallow copies on every call"
                        ),
                        line=line_num,
                        fix_hint=FIX_HINT,
                        effort=Effort.MEDIUM,
                    )
                )
                # Mark all lines in this span as flagged
                for offset in range(span):
                    already_flagged.add(line_num + offset)

    return findings
