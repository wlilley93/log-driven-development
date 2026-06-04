"""Normaliser for Gitleaks secret scanner output."""

from __future__ import annotations

from typing import Any

from vibescan.models import Category, Finding, Severity
from vibescan.normalisers.base import BaseNormaliser


class GitleaksNormaliser(BaseNormaliser):
    """Transform Gitleaks JSON report into normalised Findings.

    Input: list of dicts, each representing a detected secret.
    Keys: RuleID, Description, File, StartLine, StartColumn, Secret, Match, Entropy.
    """

    tool_name = "gitleaks"

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, list):
            return []

        findings: list[Finding] = []
        for entry in raw_data:
            if not isinstance(entry, dict):
                continue

            rule_id = entry.get("RuleID", "unknown")
            description = entry.get("Description", "Secret detected")
            file_path = entry.get("File", "unknown")
            start_line = entry.get("StartLine")
            start_col = entry.get("StartColumn")

            findings.append(
                Finding(
                    tool=self.tool_name,
                    severity=Severity.CRITICAL,
                    category=Category.SECRET,
                    file=file_path,
                    rule_id=rule_id,
                    rule_name=rule_id,
                    message=description,
                    line=int(start_line) if start_line is not None else None,
                    col=int(start_col) if start_col is not None else None,
                    raw=entry,
                )
            )

        return findings
