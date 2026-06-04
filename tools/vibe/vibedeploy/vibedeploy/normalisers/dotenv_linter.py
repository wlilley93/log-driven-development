"""Normaliser for dotenv-linter output."""

from __future__ import annotations
import re
from typing import Any
from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser


class DotenvLinterNormaliser(BaseNormaliser):
    tool_name = "dotenv_linter"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings = []
        output = raw_data.get("output", "")
        file_path = raw_data.get("file", ".env")

        for line in output.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            # Format: file:line rule_id message
            match = re.match(r'.*?:(\d+)\s+(\S+)\s+(.*)', line)
            if match:
                line_num = int(match.group(1))
                rule_id = match.group(2)
                message = match.group(3)
                findings.append(Finding(
                    tool=self.tool_name,
                    severity=Severity.LOW,
                    category=Category.ENV_SECRETS,
                    file=file_path,
                    line=line_num,
                    rule_id=rule_id,
                    rule_name=rule_id,
                    message=message,
                    effort=Effort.TRIVIAL,
                ))
        return findings
