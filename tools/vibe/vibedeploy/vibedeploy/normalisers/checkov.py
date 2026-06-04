"""Normaliser for checkov JSON output."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser


class CheckovNormaliser(BaseNormaliser):
    tool_name = "checkov"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings: list[Finding] = []

        # checkov output can be a list of check-type results or a single dict
        results_list = raw_data if isinstance(raw_data, list) else [raw_data]

        for result_block in results_list:
            if not isinstance(result_block, dict):
                continue

            # Each block has passed_checks and failed_checks
            failed_checks = result_block.get("results", {}).get("failed_checks", [])
            for check in failed_checks:
                check_id = check.get("check_id", "unknown")
                check_result = check.get("check_result", {})
                result_status = check_result.get("result", "FAILED") if isinstance(check_result, dict) else str(check_result)
                file_path = check.get("file_path", "unknown")
                file_line_range = check.get("file_line_range", [])
                check_name = check.get("check_name", check_id)
                guideline = check.get("guideline", None)

                # Map severity based on check_id prefix conventions
                severity = self._map_severity(check.get("severity", None), check_id)

                line = file_line_range[0] if file_line_range else None

                findings.append(Finding(
                    tool=self.tool_name,
                    severity=severity,
                    category=Category.IAC,
                    file=file_path.lstrip("/"),
                    line=line,
                    rule_id=check_id,
                    rule_name=check_name,
                    message=f"{check_name} ({result_status})",
                    docs_url=guideline,
                    effort=Effort.MEDIUM,
                    blocks_deploy=severity in (Severity.CRITICAL, Severity.HIGH),
                    raw=check,
                ))

        return findings

    @staticmethod
    def _map_severity(severity_str: str | None, check_id: str) -> Severity:
        """Map checkov severity or infer from check ID."""
        if severity_str:
            mapping = {
                "CRITICAL": Severity.CRITICAL,
                "HIGH": Severity.HIGH,
                "MEDIUM": Severity.MEDIUM,
                "LOW": Severity.LOW,
                "INFO": Severity.INFO,
            }
            return mapping.get(severity_str.upper(), Severity.MEDIUM)

        # Infer from check_id prefix (CKV_ checks are generally medium)
        if check_id.startswith("CKV_AWS") or check_id.startswith("CKV_GCP") or check_id.startswith("CKV_AZURE"):
            return Severity.HIGH
        return Severity.MEDIUM
