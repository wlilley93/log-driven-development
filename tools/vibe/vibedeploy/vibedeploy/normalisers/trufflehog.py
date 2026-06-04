"""Normaliser for trufflehog JSON output."""

from __future__ import annotations
from typing import Any
from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser


class TrufflehogNormaliser(BaseNormaliser):
    tool_name = "trufflehog"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings = []
        source_meta = raw_data.get("SourceMetadata", {}).get("Data", {})
        file_path = "unknown"
        line = None
        for key in ("Filesystem", "Git"):
            if key in source_meta:
                file_path = source_meta[key].get("file", "unknown")
                line = source_meta[key].get("line")
                break

        verified = raw_data.get("Verified", False)
        detector = raw_data.get("DetectorName", "unknown")
        severity = Severity.CRITICAL if verified else Severity.HIGH

        findings.append(Finding(
            tool=self.tool_name,
            severity=severity,
            category=Category.ENV_SECRETS,
            file=file_path,
            line=line,
            rule_id=f"trufflehog-{detector}",
            rule_name=detector,
            message=f"{'Verified' if verified else 'Potential'} secret: {detector}",
            blocks_deploy=True,
            effort=Effort.LOW,
            fix_hint="Rotate the credential and remove from source",
        ))
        return findings
