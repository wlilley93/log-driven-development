"""Normaliser for Bandit Python security linter output."""

from __future__ import annotations

from typing import Any

from vibescan.models import Category, Finding, Severity
from vibescan.normalisers.base import BaseNormaliser


class BanditNormaliser(BaseNormaliser):
    """Transform Bandit JSON output into normalised Findings.

    Input: dict with "results" key.
    Each result: test_id, test_name, filename, line_number, col_offset,
                 issue_severity, issue_confidence, issue_text, more_info.
    """

    tool_name = "bandit"

    _severity_order = [Severity.INFO, Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]

    def _downgrade(self, severity: Severity) -> Severity:
        """Downgrade severity by one level."""
        idx = self._severity_order.index(severity)
        if idx > 0:
            return self._severity_order[idx - 1]
        return severity

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        results = raw_data.get("results", [])
        if not isinstance(results, list):
            return []

        findings: list[Finding] = []
        for result in results:
            if not isinstance(result, dict):
                continue

            test_id = result.get("test_id", "unknown")
            test_name = result.get("test_name", test_id)
            filename = result.get("filename", "unknown")
            line_number = result.get("line_number")
            col_offset = result.get("col_offset")
            issue_text = result.get("issue_text", "Security issue detected")
            more_info = result.get("more_info")

            raw_severity = str(result.get("issue_severity", "MEDIUM")).upper()
            raw_confidence = str(result.get("issue_confidence", "MEDIUM")).upper()

            severity = self.text_severity(raw_severity)

            # Downgrade severity if confidence is LOW
            if raw_confidence == "LOW":
                severity = self._downgrade(severity)

            findings.append(
                Finding(
                    tool=self.tool_name,
                    severity=severity,
                    category=Category.CODE,
                    file=filename,
                    rule_id=test_id,
                    rule_name=test_name,
                    message=issue_text,
                    line=int(line_number) if line_number is not None else None,
                    col=int(col_offset) if col_offset is not None else None,
                    fix_hint=str(more_info) if more_info else None,
                    raw=result,
                )
            )

        return findings
