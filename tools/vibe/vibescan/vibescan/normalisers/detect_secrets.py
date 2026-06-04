"""Normaliser for detect-secrets scanner output."""

from __future__ import annotations

from typing import Any

from vibescan.models import Category, Finding, Severity
from vibescan.normalisers.base import BaseNormaliser


class DetectSecretsNormaliser(BaseNormaliser):
    """Transform detect-secrets JSON output into normalised Findings.

    Input: dict with "results" key mapping file paths to lists of findings.
    Each finding has: type, line_number, hashed_secret, is_verified.
    """

    tool_name = "detect-secrets"

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        results = raw_data.get("results", {})
        if not isinstance(results, dict):
            return []

        findings: list[Finding] = []
        for file_path, file_findings in results.items():
            if not isinstance(file_findings, list):
                continue

            for entry in file_findings:
                if not isinstance(entry, dict):
                    continue

                secret_type = entry.get("type", "unknown")
                line_number = entry.get("line_number")
                is_verified = entry.get("is_verified", False)

                findings.append(
                    Finding(
                        tool=self.tool_name,
                        severity=Severity.HIGH,
                        category=Category.SECRET,
                        file=file_path,
                        rule_id=secret_type,
                        rule_name=secret_type,
                        message=f"Potential secret detected: {secret_type} (requires human review)",
                        line=int(line_number) if line_number is not None else None,
                        secret_verified=bool(is_verified) if is_verified is not None else None,
                        raw=entry,
                    )
                )

        return findings
