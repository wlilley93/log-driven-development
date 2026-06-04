"""Normaliser for cfn-lint JSON output."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser


class CfnLintNormaliser(BaseNormaliser):
    tool_name = "cfn_lint"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings: list[Finding] = []

        # cfn-lint JSON output is a list of rule matches
        if not isinstance(raw_data, list):
            return findings

        for match in raw_data:
            if not isinstance(match, dict):
                continue

            rule = match.get("Rule", {})
            rule_id = rule.get("Id", match.get("id", "unknown"))
            rule_shortdesc = rule.get("ShortDescription", "")
            source_url = rule.get("Source", None)
            message = match.get("Message", match.get("message", rule_shortdesc))
            file_path = match.get("Filename", match.get("filename", "unknown"))
            location = match.get("Location", {})
            start = location.get("Start", {})
            line = start.get("LineNumber", match.get("linenumber"))
            col = start.get("ColumnNumber", match.get("columnnumber"))
            level = match.get("Level", match.get("level", "Warning"))

            severity = self._map_severity(rule_id, level)

            findings.append(Finding(
                tool=self.tool_name,
                severity=severity,
                category=Category.IAC,
                file=file_path,
                line=line,
                col=col,
                rule_id=rule_id,
                rule_name=rule_shortdesc or rule_id,
                message=message,
                docs_url=source_url,
                effort=Effort.LOW,
                blocks_deploy=severity in (Severity.CRITICAL, Severity.HIGH),
                raw=match,
            ))

        return findings

    @staticmethod
    def _map_severity(rule_id: str, level: str) -> Severity:
        """Map cfn-lint rule prefix and level to Severity.

        Rule ID conventions:
        - E* = Error (HIGH)
        - W* = Warning (MEDIUM)
        - I* = Informational (LOW)
        """
        # First check explicit level string
        level_mapping = {
            "Error": Severity.HIGH,
            "Warning": Severity.MEDIUM,
            "Informational": Severity.LOW,
        }
        if level in level_mapping:
            return level_mapping[level]

        # Fall back to rule ID prefix
        if rule_id.startswith("E"):
            return Severity.HIGH
        if rule_id.startswith("W"):
            return Severity.MEDIUM
        if rule_id.startswith("I"):
            return Severity.LOW
        return Severity.MEDIUM
