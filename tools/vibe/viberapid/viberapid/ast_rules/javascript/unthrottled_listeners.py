"""Detect unthrottled/undebounced scroll, resize, and mousemove event listeners."""

from __future__ import annotations

import re

from viberapid.models import Category, Effort, Finding, Severity

TOOL_NAME = "ast-analyser"
RULE_ID = "js-unthrottled-listener"
RULE_NAME = "Unthrottled Event Listener"
FIX_HINT = "Wrap handler with throttle() or debounce()"

# High-frequency events that should be throttled/debounced
HIGH_FREQ_EVENTS = frozenset({
    "scroll",
    "resize",
    "mousemove",
    "touchmove",
    "wheel",
    "pointermove",
})

# Pattern to detect addEventListener with a high-frequency event
# Captures: addEventListener('scroll', handler) or addEventListener("scroll", handler)
ADD_LISTENER_PATTERN = re.compile(
    r"""addEventListener\s*\(\s*['"](\w+)['"]\s*,\s*(.+?)(?:\s*\)|$)""",
)

# Alternative: on-event assignment: window.onscroll = handler
ON_EVENT_PATTERN = re.compile(
    r"""\b(?:window|document|element)\s*\.\s*on(scroll|resize|mousemove|touchmove|wheel|pointermove)\s*=""",
)

# Patterns indicating the handler is throttled/debounced
THROTTLE_PATTERNS = [
    re.compile(r"\bthrottle\s*\("),
    re.compile(r"\bdebounce\s*\("),
    re.compile(r"\buseThrottle\b"),
    re.compile(r"\buseDebounce\b"),
    re.compile(r"\b_\.throttle\b"),
    re.compile(r"\b_\.debounce\b"),
    re.compile(r"\brequestAnimationFrame\b"),
    re.compile(r"\braf\s*\("),
]

# Comment pattern
COMMENT_RE = re.compile(r"//.*$")
BLOCK_COMMENT_OPEN = re.compile(r"/\*")
BLOCK_COMMENT_CLOSE = re.compile(r"\*/")


def _handler_is_throttled(handler_text: str, surrounding_lines: list[str]) -> bool:
    """Check if the handler reference appears to be throttled/debounced."""
    # Check the handler expression itself
    for pattern in THROTTLE_PATTERNS:
        if pattern.search(handler_text):
            return True

    # Check if the handler variable was assigned a throttled value nearby
    # Extract variable name if handler_text is a simple identifier
    handler_name = handler_text.strip().rstrip(",).;")
    if handler_name.isidentifier():
        for line in surrounding_lines:
            # Look for: const handlerName = throttle(...) or debounce(...)
            assign_pattern = re.compile(
                rf"\b{re.escape(handler_name)}\s*=\s*"
            )
            if assign_pattern.search(line):
                for throttle_pat in THROTTLE_PATTERNS:
                    if throttle_pat.search(line):
                        return True

    return False


def check(filepath: str, source: str) -> list[Finding]:
    """Detect addEventListener for high-frequency events without throttle/debounce."""
    findings: list[Finding] = []
    lines = source.split("\n")
    in_block_comment = False

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

        stripped = COMMENT_RE.sub("", raw_line)

        # Check addEventListener
        for match in ADD_LISTENER_PATTERN.finditer(stripped):
            event_name = match.group(1)
            handler_text = match.group(2)

            if event_name not in HIGH_FREQ_EVENTS:
                continue

            # Check surrounding context (20 lines before and after) for throttle setup
            context_start = max(0, line_idx - 20)
            context_end = min(len(lines), line_idx + 20)
            surrounding = lines[context_start:context_end]

            if _handler_is_throttled(handler_text, surrounding):
                continue

            findings.append(
                Finding(
                    tool=TOOL_NAME,
                    severity=Severity.MEDIUM,
                    category=Category.RENDER,
                    file=filepath,
                    rule_id=RULE_ID,
                    rule_name=RULE_NAME,
                    message=(
                        f"Event listener for '{event_name}' appears unthrottled — "
                        f"fires at 60+ fps and may cause jank"
                    ),
                    line=line_num,
                    fix_hint=FIX_HINT,
                    effort=Effort.LOW,
                )
            )

        # Check on-event assignments
        for match in ON_EVENT_PATTERN.finditer(stripped):
            event_name = match.group(1)
            # Check surrounding context
            context_start = max(0, line_idx - 20)
            context_end = min(len(lines), line_idx + 20)
            surrounding = lines[context_start:context_end]

            rest_of_line = stripped[match.end():]
            if _handler_is_throttled(rest_of_line, surrounding):
                continue

            findings.append(
                Finding(
                    tool=TOOL_NAME,
                    severity=Severity.MEDIUM,
                    category=Category.RENDER,
                    file=filepath,
                    rule_id=RULE_ID,
                    rule_name=RULE_NAME,
                    message=(
                        f"Direct `on{event_name}` assignment appears unthrottled — "
                        f"fires at 60+ fps and may cause jank"
                    ),
                    line=line_num,
                    fix_hint=FIX_HINT,
                    effort=Effort.LOW,
                )
            )

    return findings
