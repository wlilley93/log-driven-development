"""Detect inline object/array literals in JSX props that cause re-renders."""

from __future__ import annotations

import re

from viberapid.models import Category, Effort, Finding, Severity

TOOL_NAME = "ast-analyser"
RULE_ID = "js-inline-jsx-object"
RULE_NAME = "Inline Object/Array in JSX Prop"
FIX_HINT = "Extract to a constant or useMemo"

# Patterns for inline objects/arrays in JSX props:
#   prop={{...}}   — inline object
#   prop={[...]}   — inline array
#   prop={() =>    — inline arrow function (also causes re-renders)
# We look for `={}` where the inner content starts with `{`, `[`, or `(`
INLINE_OBJECT_PATTERN = re.compile(
    r"""
    (\w+)          # prop name
    \s*=\s*        # =
    \{\s*          # opening JSX expression {
    (\{|\[)        # opening { for object or [ for array
    """,
    re.VERBOSE,
)

# Inline arrow functions in JSX: `prop={() => ...}` or `prop={function`
INLINE_FUNCTION_PATTERN = re.compile(
    r"""
    (\w+)                   # prop name
    \s*=\s*                 # =
    \{\s*                   # opening JSX expression {
    (\(\s*\)\s*=>           # () =>
    |\(\s*\w+.*?\)\s*=>    # (args) =>
    |\w+\s*=>               # arg =>
    |function\b)            # function keyword
    """,
    re.VERBOSE,
)

# Single-line comment pattern
COMMENT_RE = re.compile(r"//.*$")
BLOCK_COMMENT_OPEN = re.compile(r"/\*")
BLOCK_COMMENT_CLOSE = re.compile(r"\*/")

# Allowlist: these props commonly need inline objects and are typically fine
ALLOWLISTED_PROPS = frozenset({
    "key",
    "ref",
    "dangerouslySetInnerHTML",
})


def _strip_comments(line: str) -> str:
    """Remove single-line comments."""
    return COMMENT_RE.sub("", line)


def _is_in_jsx_context(lines: list[str], line_idx: int) -> bool:
    """Heuristic: check if we're likely inside JSX (return statement or component body)."""
    # Look backwards for `return` or JSX-like parent elements
    for i in range(line_idx, max(line_idx - 15, -1), -1):
        stripped = lines[i].strip()
        if stripped.startswith("return") or stripped.startswith("<"):
            return True
        # If we hit a function signature, stop looking
        if re.match(r"^\s*(function|const|let|var|class)\s+", stripped):
            break
    return False


def check(filepath: str, source: str) -> list[Finding]:
    """Detect inline object/array/function literals in JSX props."""
    findings: list[Finding] = []

    # Only check JSX/TSX files
    if not filepath.endswith((".jsx", ".tsx")):
        return findings

    lines = source.split("\n")
    in_block_comment = False

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

        stripped = _strip_comments(working)

        # Check for inline objects/arrays
        for match in INLINE_OBJECT_PATTERN.finditer(stripped):
            prop_name = match.group(1)
            if prop_name in ALLOWLISTED_PROPS:
                continue

            # Verify we're in a JSX context
            if _is_in_jsx_context(lines, line_idx):
                findings.append(
                    Finding(
                        tool=TOOL_NAME,
                        severity=Severity.MEDIUM,
                        category=Category.RENDER,
                        file=filepath,
                        rule_id=RULE_ID,
                        rule_name=RULE_NAME,
                        message=(
                            f"Inline object/array literal for prop `{prop_name}` "
                            f"creates a new reference on every render"
                        ),
                        line=line_num,
                        fix_hint=FIX_HINT,
                        effort=Effort.LOW,
                    )
                )

        # Check for inline functions
        for match in INLINE_FUNCTION_PATTERN.finditer(stripped):
            prop_name = match.group(1)
            if prop_name in ALLOWLISTED_PROPS:
                continue

            # Common event handlers — lower severity since they're often intentional
            is_event_handler = prop_name.startswith("on") and len(prop_name) > 2

            if _is_in_jsx_context(lines, line_idx):
                findings.append(
                    Finding(
                        tool=TOOL_NAME,
                        severity=Severity.LOW if is_event_handler else Severity.MEDIUM,
                        category=Category.RENDER,
                        file=filepath,
                        rule_id=RULE_ID,
                        rule_name="Inline Function in JSX Prop",
                        message=(
                            f"Inline function for prop `{prop_name}` "
                            f"creates a new closure on every render"
                        ),
                        line=line_num,
                        fix_hint="Extract to useCallback or a stable reference",
                        effort=Effort.LOW,
                    )
                )

    return findings
