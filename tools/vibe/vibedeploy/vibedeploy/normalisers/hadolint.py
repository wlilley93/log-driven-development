"""Normaliser for hadolint JSON output."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser

# Rules about running as root that should block deploys
_ROOT_RULES = {"DL3002", "DL3007", "DL3047"}

# Rules related to pinning versions (security-relevant)
_PIN_RULES = {"DL3006", "DL3007", "DL3008", "DL3009", "DL3013", "DL3016", "DL3018"}

_LEVEL_MAP = {
    "error": Severity.HIGH,
    "warning": Severity.MEDIUM,
    "info": Severity.LOW,
    "style": Severity.INFO,
}


class HadolintNormaliser(BaseNormaliser):
    tool_name = "hadolint"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings: list[Finding] = []

        if not isinstance(raw_data, list):
            return findings

        for item in raw_data:
            code = item.get("code", "UNKNOWN")
            level = item.get("level", "warning")
            message = item.get("message", "")
            line_num = item.get("line")
            file_path = item.get("file", "Dockerfile")
            column = item.get("column")

            severity = _LEVEL_MAP.get(level, Severity.MEDIUM)
            blocks = code in _ROOT_RULES

            # Upgrade severity for root-related rules
            if code in _ROOT_RULES:
                severity = Severity.HIGH

            effort = Effort.TRIVIAL
            if code in _PIN_RULES:
                effort = Effort.LOW

            fix_hint = None
            if code == "DL3002":
                fix_hint = "Add a USER instruction to run as non-root"
            elif code == "DL3007":
                fix_hint = "Pin the base image to a specific version tag instead of 'latest'"
            elif code in _PIN_RULES:
                fix_hint = "Pin package versions for reproducible builds"

            findings.append(Finding(
                tool=self.tool_name,
                severity=severity,
                category=Category.DOCKER,
                file=file_path,
                line=line_num,
                col=column,
                rule_id=code,
                rule_name=code,
                message=message,
                blocks_deploy=blocks,
                effort=effort,
                fix_hint=fix_hint,
                docs_url=f"https://github.com/hadolint/hadolint/wiki/{code}",
                raw=item,
            ))

        return findings
