"""Normaliser for conftest JSON output."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser


class ConftestNormaliser(BaseNormaliser):
    tool_name = "conftest"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings: list[Finding] = []

        # conftest JSON output is a list of file results
        if not isinstance(raw_data, list):
            return findings

        for file_result in raw_data:
            if not isinstance(file_result, dict):
                continue

            file_path = file_result.get("filename", "unknown")

            # Process failures
            for failure in file_result.get("failures", []):
                msg = failure.get("msg", "") if isinstance(failure, dict) else str(failure)
                metadata = failure.get("metadata", {}) if isinstance(failure, dict) else {}

                rule_id = metadata.get("rule_id", "conftest-failure")
                details = metadata.get("details", {})

                findings.append(Finding(
                    tool=self.tool_name,
                    severity=Severity.HIGH,
                    category=Category.IAC,
                    file=file_path,
                    line=None,
                    rule_id=rule_id,
                    rule_name=rule_id,
                    message=msg,
                    effort=Effort.MEDIUM,
                    blocks_deploy=True,
                    raw=failure if isinstance(failure, dict) else {"msg": msg},
                ))

            # Process warnings
            for warning in file_result.get("warnings", []):
                msg = warning.get("msg", "") if isinstance(warning, dict) else str(warning)
                metadata = warning.get("metadata", {}) if isinstance(warning, dict) else {}

                rule_id = metadata.get("rule_id", "conftest-warning")

                findings.append(Finding(
                    tool=self.tool_name,
                    severity=Severity.MEDIUM,
                    category=Category.IAC,
                    file=file_path,
                    line=None,
                    rule_id=rule_id,
                    rule_name=rule_id,
                    message=msg,
                    effort=Effort.LOW,
                    blocks_deploy=False,
                    raw=warning if isinstance(warning, dict) else {"msg": msg},
                ))

        return findings
