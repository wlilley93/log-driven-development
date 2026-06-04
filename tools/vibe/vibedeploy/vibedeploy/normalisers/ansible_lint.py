"""Normaliser for ansible-lint JSON output."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser


class AnsibleLintNormaliser(BaseNormaliser):
    tool_name = "ansible_lint"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings: list[Finding] = []

        # ansible-lint JSON output is a list of violation objects
        if not isinstance(raw_data, list):
            return findings

        for violation in raw_data:
            if not isinstance(violation, dict):
                continue

            rule_id = violation.get("rule", {}).get("id", "unknown") if isinstance(violation.get("rule"), dict) else violation.get("rule", "unknown")
            rule_desc = ""
            rule_url = None
            severity_str = "MEDIUM"

            if isinstance(violation.get("rule"), dict):
                rule_desc = violation["rule"].get("shortdesc", violation["rule"].get("description", ""))
                rule_url = violation["rule"].get("url", None)
                severity_str = violation["rule"].get("severity", "MEDIUM")

            message = violation.get("message", violation.get("detail", rule_desc))
            file_path = violation.get("filename", violation.get("location", {}).get("path", "unknown"))
            line = violation.get("linenumber", violation.get("location", {}).get("lines", {}).get("begin"))
            tag = violation.get("tag", "")

            # ansible-lint uses tags like "warning", "error"
            level = violation.get("level", violation.get("type", ""))

            severity = self._map_severity(severity_str, level)

            findings.append(Finding(
                tool=self.tool_name,
                severity=severity,
                category=Category.IAC,
                file=file_path,
                line=line,
                rule_id=str(rule_id),
                rule_name=tag or rule_desc or str(rule_id),
                message=message or f"Ansible lint violation: {rule_id}",
                docs_url=rule_url,
                effort=Effort.LOW,
                blocks_deploy=severity in (Severity.CRITICAL, Severity.HIGH),
                raw=violation,
            ))

        return findings

    @staticmethod
    def _map_severity(severity_str: str, level: str) -> Severity:
        """Map ansible-lint severity/level to Severity enum."""
        # Check the level first (error, warning, etc.)
        level_lower = level.lower() if level else ""
        if level_lower in ("error", "fatal"):
            return Severity.HIGH
        if level_lower == "warning":
            return Severity.MEDIUM

        # Fall back to severity string
        mapping = {
            "VERY_HIGH": Severity.CRITICAL,
            "HIGH": Severity.HIGH,
            "MEDIUM": Severity.MEDIUM,
            "LOW": Severity.LOW,
            "VERY_LOW": Severity.INFO,
            "INFO": Severity.INFO,
        }
        return mapping.get(severity_str.upper(), Severity.MEDIUM)
