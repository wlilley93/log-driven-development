"""Detect exported function components that don't use React.memo."""

from __future__ import annotations

import re

from viberapid.models import Category, Effort, Finding, Severity

TOOL_NAME = "ast-analyser"
RULE_ID = "js-missing-memo"
RULE_NAME = "Exported Component Without React.memo"
FIX_HINT = "Consider wrapping with React.memo if props are stable"

# Pattern for `export function ComponentName` (PascalCase = component)
EXPORT_FUNC_PATTERN = re.compile(
    r"^export\s+(?:default\s+)?function\s+([A-Z][A-Za-z0-9]*)"
)

# Pattern for `export const ComponentName = (` or `export const ComponentName: ...= (`
EXPORT_CONST_PATTERN = re.compile(
    r"^export\s+(?:default\s+)?const\s+([A-Z][A-Za-z0-9]*)\s*(?::\s*\w[^=]*)?\s*="
)

# Pattern for React.memo wrapping
MEMO_PATTERN = re.compile(r"\bReact\.memo\b|\bmemo\s*\(")

# Pattern for forwardRef (already wrapped, doesn't need memo check)
FORWARD_REF_PATTERN = re.compile(r"\bforwardRef\s*[<(]|\bReact\.forwardRef\b")

# File path patterns for component directories
COMPONENT_DIR_PATTERNS = [
    "/components/",
    "/pages/",
    "/views/",
    "/screens/",
    "/features/",
    "/widgets/",
    "/ui/",
    "/layouts/",
]

# Comment patterns
COMMENT_RE = re.compile(r"//.*$")


def _is_component_file(filepath: str) -> bool:
    """Check if the file is in a components-like directory."""
    filepath_lower = filepath.lower().replace("\\", "/")
    return any(pattern in filepath_lower for pattern in COMPONENT_DIR_PATTERNS)


def _source_has_memo(source: str) -> bool:
    """Check if the file already imports or uses React.memo."""
    return bool(MEMO_PATTERN.search(source))


def _source_has_forward_ref(source: str) -> bool:
    """Check if the file uses forwardRef (skip memo check)."""
    return bool(FORWARD_REF_PATTERN.search(source))


def check(filepath: str, source: str) -> list[Finding]:
    """Detect exported function components without React.memo."""
    findings: list[Finding] = []

    # Only check JSX/TSX files in component directories
    if not filepath.endswith((".jsx", ".tsx")):
        return findings

    if not _is_component_file(filepath):
        return findings

    # If the file already uses memo or forwardRef, skip it
    if _source_has_memo(source) or _source_has_forward_ref(source):
        return findings

    lines = source.split("\n")

    for line_idx, raw_line in enumerate(lines):
        line_num = line_idx + 1
        stripped = COMMENT_RE.sub("", raw_line).strip()

        # Check export function ComponentName
        match = EXPORT_FUNC_PATTERN.match(stripped)
        if match:
            component_name = match.group(1)
            findings.append(
                Finding(
                    tool=TOOL_NAME,
                    severity=Severity.LOW,
                    category=Category.RENDER,
                    file=filepath,
                    rule_id=RULE_ID,
                    rule_name=RULE_NAME,
                    message=(
                        f"Exported component `{component_name}` is not wrapped "
                        f"with React.memo — may cause unnecessary re-renders"
                    ),
                    line=line_num,
                    fix_hint=FIX_HINT,
                    effort=Effort.LOW,
                )
            )
            continue

        # Check export const ComponentName = ...
        match = EXPORT_CONST_PATTERN.match(stripped)
        if match:
            component_name = match.group(1)
            # Check the rest of the line and next few lines for React.memo
            context = "\n".join(lines[line_idx:line_idx + 3])
            if MEMO_PATTERN.search(context):
                continue

            findings.append(
                Finding(
                    tool=TOOL_NAME,
                    severity=Severity.LOW,
                    category=Category.RENDER,
                    file=filepath,
                    rule_id=RULE_ID,
                    rule_name=RULE_NAME,
                    message=(
                        f"Exported component `{component_name}` is not wrapped "
                        f"with React.memo — may cause unnecessary re-renders"
                    ),
                    line=line_num,
                    fix_hint=FIX_HINT,
                    effort=Effort.LOW,
                )
            )

    return findings
