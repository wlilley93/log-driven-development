"""Normaliser for TruffleHog secret scanner output."""

from __future__ import annotations

from typing import Any

from vibescan.models import Category, Finding, Severity
from vibescan.normalisers.base import BaseNormaliser


class TrufflehogNormaliser(BaseNormaliser):
    """Transform TruffleHog newline-delimited JSON output into normalised Findings.

    Input: list of dicts (parsed from newline-delimited JSON).
    Keys: SourceMetadata.Data.Filesystem.file, SourceMetadata.Data.Filesystem.line,
          DetectorName, Verified, Raw, ExtraData.
    """

    tool_name = "trufflehog"

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, list):
            return []

        findings: list[Finding] = []
        for entry in raw_data:
            if not isinstance(entry, dict):
                continue

            # Navigate nested SourceMetadata safely
            source_meta = entry.get("SourceMetadata", {})
            data = source_meta.get("Data", {}) if isinstance(source_meta, dict) else {}
            filesystem = data.get("Filesystem", {}) if isinstance(data, dict) else {}

            file_path = filesystem.get("file", "unknown") if isinstance(filesystem, dict) else "unknown"
            line = filesystem.get("line") if isinstance(filesystem, dict) else None

            detector_name = entry.get("DetectorName", "unknown")
            verified = entry.get("Verified", False)

            severity = Severity.CRITICAL if verified else Severity.HIGH

            findings.append(
                Finding(
                    tool=self.tool_name,
                    severity=severity,
                    category=Category.SECRET,
                    file=file_path,
                    rule_id=detector_name,
                    rule_name=detector_name,
                    message=f"Secret detected by {detector_name}"
                    + (" (verified)" if verified else " (unverified)"),
                    line=int(line) if line is not None else None,
                    secret_verified=bool(verified),
                    raw=entry,
                )
            )

        return findings
