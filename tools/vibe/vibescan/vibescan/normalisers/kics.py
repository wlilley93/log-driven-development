"""Normaliser for KICS (Keeping Infrastructure as Code Secure) output."""

from __future__ import annotations

from typing import Any

from vibescan.models import Category, Finding, Severity
from vibescan.normalisers.base import BaseNormaliser


class KicsNormaliser(BaseNormaliser):
    """Transform KICS JSON output into normalised Findings.

    Input: dict with "queries" key containing list of query results.
    Each query: query_name, severity, description,
                files (list with {file_name, line, search_key, expected_value, actual_value}).
    """

    tool_name = "kics"

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        queries = raw_data.get("queries", [])
        if not isinstance(queries, list):
            return []

        findings: list[Finding] = []
        for query in queries:
            if not isinstance(query, dict):
                continue

            query_name = query.get("query_name", "unknown")
            raw_severity = str(query.get("severity", "MEDIUM"))
            description = query.get("description", "")
            query_id = query.get("query_id", query_name)

            severity = self.text_severity(raw_severity)

            files = query.get("files", [])
            if not isinstance(files, list):
                continue

            for file_entry in files:
                if not isinstance(file_entry, dict):
                    continue

                file_name = file_entry.get("file_name", "unknown")
                line = file_entry.get("line")
                search_key = file_entry.get("search_key", "")
                expected_value = file_entry.get("expected_value", "")
                actual_value = file_entry.get("actual_value", "")

                # Build detailed message
                message = description or query_name
                if expected_value and actual_value:
                    message = f"{message}. Expected: {expected_value}, Actual: {actual_value}"

                fix_hint = None
                if expected_value:
                    fix_hint = f"Expected: {expected_value}"

                findings.append(
                    Finding(
                        tool=self.tool_name,
                        severity=severity,
                        category=Category.IAC,
                        file=file_name,
                        rule_id=str(query_id),
                        rule_name=query_name,
                        message=message,
                        line=int(line) if line is not None else None,
                        fix_hint=fix_hint,
                        raw=file_entry,
                    )
                )

        return findings
