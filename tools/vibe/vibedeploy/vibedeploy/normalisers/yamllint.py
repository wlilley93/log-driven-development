"""Normaliser for yamllint parsable output."""

from __future__ import annotations

import re
from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser

# yamllint parsable format: file:line:col: [error|warning] message (rule)
YAMLLINT_LINE = re.compile(
    r"""^(?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+):\s+\[(?P<level>error|warning)\]\s+(?P<message>.+?)(?:\s+\((?P<rule>[^)]+)\))?$"""
)


class YamllintNormaliser(BaseNormaliser):
    tool_name = "yamllint"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings: list[Finding] = []
        output = raw_data.get("output", "")
        fallback_file = raw_data.get("file", "unknown")

        for line in output.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            match = YAMLLINT_LINE.match(line)
            if match:
                level = match.group("level")
                message = match.group("message")
                rule_id = match.group("rule") or "unknown"
                file_path = match.group("file") or fallback_file
                line_num = int(match.group("line"))
                col_num = int(match.group("col"))

                severity = Severity.MEDIUM if level == "error" else Severity.LOW

                findings.append(Finding(
                    tool=self.tool_name,
                    severity=severity,
                    category=Category.CONFIG,
                    file=file_path if file_path != "stdin" else fallback_file,
                    line=line_num,
                    col=col_num,
                    rule_id=f"yamllint-{rule_id}",
                    rule_name=rule_id,
                    message=message,
                    effort=Effort.TRIVIAL,
                    blocks_deploy=level == "error",
                    docs_url="https://yamllint.readthedocs.io/en/stable/rules.html",
                ))

        return findings
