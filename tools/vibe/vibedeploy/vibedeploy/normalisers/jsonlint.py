"""Normaliser for JSON validation errors."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser


class JsonlintNormaliser(BaseNormaliser):
    tool_name = "jsonlint"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings: list[Finding] = []

        file_path = raw_data.get("file", "unknown")
        error_msg = raw_data.get("error", "")
        line_num = raw_data.get("line")
        col_num = raw_data.get("col")
        msg = raw_data.get("msg", error_msg)

        if not error_msg and not msg:
            return findings

        findings.append(Finding(
            tool=self.tool_name,
            severity=Severity.HIGH,
            category=Category.CONFIG,
            file=file_path,
            line=line_num,
            col=col_num,
            rule_id="json-parse-error",
            rule_name="Invalid JSON",
            message=f"JSON syntax error: {msg}",
            effort=Effort.TRIVIAL,
            blocks_deploy=True,
            fix_hint="Fix JSON syntax error at the indicated position",
        ))

        return findings
