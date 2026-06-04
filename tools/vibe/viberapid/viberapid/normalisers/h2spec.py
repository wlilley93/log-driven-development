"""Normaliser for h2spec output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser


# Section IDs that indicate critical protocol violations
_CRITICAL_SECTIONS = {
    "3.5",   # Connection Preface
    "4.1",   # Frame Format
    "5.1",   # Stream States
    "6.5",   # SETTINGS
    "6.9",   # WINDOW_UPDATE
    "8.1",   # HTTP Request/Response Exchange
}


def _severity_for_section(section_id: str) -> Severity:
    """Determine severity based on the h2spec section ID."""
    # Critical sections relate to fundamental protocol mechanics
    for critical in _CRITICAL_SECTIONS:
        if section_id.startswith(critical):
            return Severity.HIGH
    return Severity.MEDIUM


def _fix_hint_for_section(section_id: str, description: str) -> str:
    """Generate a fix hint based on the failing test section."""
    section_prefix = section_id.split(".")[0] if "." in section_id else section_id

    hints = {
        "3": "Review the HTTP/2 connection preface handling. Ensure the server sends a valid SETTINGS frame as part of the connection preface.",
        "4": "Fix frame format handling. Ensure frames conform to the HTTP/2 wire format specification (RFC 7540 Section 4).",
        "5": "Fix stream state management. Ensure proper handling of stream lifecycle transitions (idle, open, half-closed, closed).",
        "6": "Fix frame type handling. Review the server's implementation of the specific HTTP/2 frame type per RFC 7540 Section 6.",
        "7": "Fix error handling. Ensure the server responds with correct error codes per RFC 7540 Section 7.",
        "8": "Fix HTTP message semantics over HTTP/2. Ensure proper handling of pseudo-headers and request/response formatting.",
    }

    return hints.get(
        section_prefix,
        f"Review RFC 7540 section {section_id} and fix the HTTP/2 protocol compliance issue."
    )


class H2specNormaliser(BaseNormaliser):
    """Convert h2spec JSON output to Finding objects.

    h2spec JSON shape:
    [
      {
        "title": "3. Starting HTTP/2",
        "testCount": 5,
        "passedCount": 4,
        "failedCount": 1,
        "skippedCount": 0,
        "testCases": [
          {
            "title": "Sends a client connection preface",
            "result": "passed" | "failed" | "skipped",
            "expected": "SETTINGS Frame (length:0, flags:0x01, stream_id:0)",
            "actual": "Timeout",
            "section": "3.5"
          },
          ...
        ],
        "groups": [
          {
            "title": "3.5. Connection Preface",
            "testCount": 2,
            "passedCount": 1,
            "failedCount": 1,
            "skippedCount": 0,
            "testCases": [ ... ]
          }
        ]
      }
    ]
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not raw_data:
            return []

        # Normalise to list
        suites = raw_data if isinstance(raw_data, list) else [raw_data]

        findings: list[Finding] = []
        self._walk_suites(suites, findings)
        return findings

    def _walk_suites(self, suites: list[Any], findings: list[Finding]) -> None:
        """Recursively walk h2spec test suites and extract failures."""
        for suite in suites:
            if not isinstance(suite, dict):
                continue

            suite_title = suite.get("title", "Unknown")

            # Process test cases in this suite
            test_cases = suite.get("testCases", [])
            for tc in test_cases:
                if not isinstance(tc, dict):
                    continue

                result = tc.get("result", "")
                if result != "failed":
                    continue

                title = tc.get("title", "Unknown test")
                section = tc.get("section", "")
                expected = tc.get("expected", "")
                actual = tc.get("actual", "")

                severity = _severity_for_section(section)

                # Build descriptive message
                msg_parts = [f"HTTP/2 compliance test failed: {title}"]
                if expected:
                    msg_parts.append(f"Expected: {expected}")
                if actual:
                    msg_parts.append(f"Actual: {actual}")
                message = ". ".join(msg_parts) + "."

                rule_id = f"h2-{section}" if section else f"h2-{title[:40]}"

                findings.append(Finding(
                    tool="h2spec",
                    severity=severity,
                    category=Category.NETWORK,
                    file="<url>",
                    rule_id=rule_id,
                    rule_name=f"HTTP/2: {suite_title}",
                    message=message,
                    effort=Effort.MEDIUM,
                    fix_hint=_fix_hint_for_section(section, title),
                    saving_estimate="Fix HTTP/2 protocol compliance to enable multiplexing, header compression, and server push",
                    raw={
                        "suite": suite_title,
                        "section": section,
                        "test": title,
                        "expected": expected,
                        "actual": actual,
                    },
                ))

            # Recurse into nested groups
            groups = suite.get("groups", [])
            if groups:
                self._walk_suites(groups, findings)
