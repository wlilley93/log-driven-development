"""Normaliser for terrascan JSON output."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser


class TerrascanNormaliser(BaseNormaliser):
    tool_name = "terrascan"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings: list[Finding] = []

        if not isinstance(raw_data, dict):
            return findings

        # terrascan output: { "results": { "violations": [...], "scan_summary": {...} } }
        results = raw_data.get("results", {})
        violations = results.get("violations", [])
        if violations is None:
            violations = []

        for violation in violations:
            if not isinstance(violation, dict):
                continue

            rule_id = violation.get("rule_id", violation.get("id", "unknown"))
            rule_name = violation.get("rule_name", rule_id)
            description = violation.get("description", rule_name)
            severity_str = violation.get("severity", "MEDIUM")
            file_path = violation.get("file", "unknown")
            line = violation.get("line", None)
            resource_name = violation.get("resource_name", "")
            resource_type = violation.get("resource_type", "")
            category_str = violation.get("category", "")

            severity = self._map_severity(severity_str)

            message = description
            if resource_name:
                message = f"{description} (resource: {resource_type}/{resource_name})"

            findings.append(Finding(
                tool=self.tool_name,
                severity=severity,
                category=Category.IAC,
                file=file_path,
                line=line,
                rule_id=rule_id,
                rule_name=rule_name,
                message=message,
                effort=Effort.MEDIUM,
                blocks_deploy=severity in (Severity.CRITICAL, Severity.HIGH),
                raw=violation,
            ))

        return findings

    @staticmethod
    def _map_severity(severity_str: str) -> Severity:
        """Map terrascan severity to Severity enum."""
        mapping = {
            "HIGH": Severity.HIGH,
            "MEDIUM": Severity.MEDIUM,
            "LOW": Severity.LOW,
        }
        return mapping.get(severity_str.upper(), Severity.MEDIUM)
