"""Normaliser for Semgrep static analysis output."""

from __future__ import annotations

from typing import Any

from vibescan.models import Category, Finding, Severity
from vibescan.normalisers.base import BaseNormaliser


class SemgrepNormaliser(BaseNormaliser):
    """Transform Semgrep JSON output into normalised Findings.

    Input: dict with "results" key containing list of matches.
    Each match: check_id, path, start.line, start.col, end.line,
                extra.message, extra.severity, extra.metadata.fix, extra.fix.
    """

    tool_name = "semgrep"

    _severity_map = {
        "ERROR": Severity.CRITICAL,
        "WARNING": Severity.HIGH,
        "INFO": Severity.MEDIUM,
    }

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        results = raw_data.get("results", [])
        if not isinstance(results, list):
            return []

        findings: list[Finding] = []
        for match in results:
            if not isinstance(match, dict):
                continue

            check_id = match.get("check_id", "unknown")
            file_path = match.get("path", "unknown")

            start = match.get("start", {})
            start = start if isinstance(start, dict) else {}
            line = start.get("line")
            col = start.get("col")

            extra = match.get("extra", {})
            extra = extra if isinstance(extra, dict) else {}
            message = extra.get("message", check_id)
            raw_severity = extra.get("severity", "WARNING")

            severity = self._severity_map.get(
                str(raw_severity).upper(), Severity.MEDIUM
            )

            # fix_hint: prefer extra.metadata.fix, fall back to extra.fix
            metadata = extra.get("metadata", {})
            metadata = metadata if isinstance(metadata, dict) else {}
            fix_hint = metadata.get("fix") or extra.get("fix")

            # Derive a short rule name from check_id (last segment)
            rule_name = check_id.rsplit(".", 1)[-1] if "." in check_id else check_id

            findings.append(
                Finding(
                    tool=self.tool_name,
                    severity=severity,
                    category=Category.CODE,
                    file=file_path,
                    rule_id=check_id,
                    rule_name=rule_name,
                    message=message,
                    line=int(line) if line is not None else None,
                    col=int(col) if col is not None else None,
                    fix_hint=str(fix_hint) if fix_hint else None,
                    raw=match,
                )
            )

        return findings
