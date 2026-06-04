"""Normaliser for KICS JSON output."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser


class KicsNormaliser(BaseNormaliser):
    tool_name = "kics"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings: list[Finding] = []

        if not isinstance(raw_data, dict):
            return findings

        # KICS JSON output: { "queries": [...] }
        queries = raw_data.get("queries", [])
        if queries is None:
            queries = []

        for query in queries:
            if not isinstance(query, dict):
                continue

            query_name = query.get("query_name", "unknown")
            query_id = query.get("query_id", "unknown")
            query_url = query.get("query_url", None)
            severity_str = query.get("severity", "MEDIUM")
            platform = query.get("platform", "")
            description = query.get("description", query_name)
            category_str = query.get("category", "")

            severity = self._map_severity(severity_str)

            # Each query has a list of files (results)
            files = query.get("files", [])
            if files is None:
                files = []

            for file_entry in files:
                if not isinstance(file_entry, dict):
                    continue

                file_path = file_entry.get("file_name", "unknown")
                line = file_entry.get("line", None)
                expected_value = file_entry.get("expected_value", "")
                actual_value = file_entry.get("actual_value", "")
                issue_type = file_entry.get("issue_type", "")
                search_key = file_entry.get("search_key", "")
                resource_type = file_entry.get("resource_type", "")

                message = description
                if expected_value and actual_value:
                    message = f"{description}. Expected: {expected_value}, Actual: {actual_value}"

                fix_hint = None
                if expected_value:
                    fix_hint = f"Expected: {expected_value}"

                findings.append(Finding(
                    tool=self.tool_name,
                    severity=severity,
                    category=Category.IAC,
                    file=file_path,
                    line=line,
                    rule_id=query_id,
                    rule_name=query_name,
                    message=message,
                    fix_hint=fix_hint,
                    docs_url=query_url,
                    effort=Effort.MEDIUM,
                    blocks_deploy=severity in (Severity.CRITICAL, Severity.HIGH),
                    raw=file_entry,
                ))

        return findings

    @staticmethod
    def _map_severity(severity_str: str) -> Severity:
        """Map KICS severity string to Severity enum."""
        mapping = {
            "CRITICAL": Severity.CRITICAL,
            "HIGH": Severity.HIGH,
            "MEDIUM": Severity.MEDIUM,
            "LOW": Severity.LOW,
            "INFO": Severity.INFO,
            "TRACE": Severity.INFO,
        }
        return mapping.get(severity_str.upper(), Severity.MEDIUM)
