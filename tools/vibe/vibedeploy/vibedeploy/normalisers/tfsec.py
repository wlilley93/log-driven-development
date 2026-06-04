"""Normaliser for tfsec JSON output."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser


class TfsecNormaliser(BaseNormaliser):
    tool_name = "tfsec"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings: list[Finding] = []

        # tfsec JSON output has a "results" key (or may be a list directly)
        results = raw_data.get("results", []) if isinstance(raw_data, dict) else raw_data
        if results is None:
            results = []

        for result in results:
            if not isinstance(result, dict):
                continue

            rule_id = result.get("rule_id", result.get("long_id", "unknown"))
            description = result.get("description", "")
            resolution = result.get("resolution", "")
            severity_str = result.get("severity", "MEDIUM")
            file_path = result.get("location", {}).get("filename", "unknown")
            start_line = result.get("location", {}).get("start_line")
            end_line = result.get("location", {}).get("end_line")
            rule_description = result.get("rule_description", description)

            # Also handle flat structure from some tfsec versions
            if file_path == "unknown":
                file_path = result.get("filename", "unknown")
            if start_line is None:
                start_line = result.get("start_line")

            links = result.get("links", [])
            docs_url = links[0] if links else None

            severity = self._map_severity(severity_str)

            findings.append(Finding(
                tool=self.tool_name,
                severity=severity,
                category=Category.IAC,
                file=file_path,
                line=start_line,
                rule_id=rule_id,
                rule_name=rule_description or rule_id,
                message=description,
                fix_hint=resolution if resolution else None,
                docs_url=docs_url,
                effort=Effort.MEDIUM,
                blocks_deploy=severity in (Severity.CRITICAL, Severity.HIGH),
                raw=result,
            ))

        return findings

    @staticmethod
    def _map_severity(severity_str: str) -> Severity:
        """Map tfsec severity string to Severity enum."""
        mapping = {
            "CRITICAL": Severity.CRITICAL,
            "HIGH": Severity.HIGH,
            "MEDIUM": Severity.MEDIUM,
            "LOW": Severity.LOW,
        }
        return mapping.get(severity_str.upper(), Severity.MEDIUM)
