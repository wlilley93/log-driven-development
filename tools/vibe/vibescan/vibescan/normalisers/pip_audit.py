"""Normaliser for pip-audit output."""

from __future__ import annotations

from typing import Any

from vibescan.models import Category, Finding, Severity
from vibescan.normalisers.base import BaseNormaliser


class PipAuditNormaliser(BaseNormaliser):
    """Transform pip-audit JSON output into normalised Findings.

    Input: list of dicts from pip-audit JSON.
    Each entry: name, version, vulns (list of {id, fix_versions, description, aliases}).
    """

    tool_name = "pip-audit"

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, list):
            return []

        findings: list[Finding] = []
        for entry in raw_data:
            if not isinstance(entry, dict):
                continue

            pkg_name = entry.get("name", "unknown")
            pkg_version = entry.get("version", "")
            vulns = entry.get("vulns", [])
            if not isinstance(vulns, list):
                continue

            for vuln in vulns:
                if not isinstance(vuln, dict):
                    continue

                vuln_id = vuln.get("id", "unknown")
                description = vuln.get("description", "")
                fix_versions = vuln.get("fix_versions", [])
                fix_versions = fix_versions if isinstance(fix_versions, list) else []
                aliases = vuln.get("aliases", [])
                aliases = aliases if isinstance(aliases, list) else []

                # Build fix hint
                fix_hint = None
                if fix_versions:
                    fix_hint = f"Upgrade to {fix_versions[0]}"

                # Determine CVE: vuln_id itself or first alias that looks like a CVE
                cve = None
                if vuln_id.startswith("CVE-"):
                    cve = vuln_id
                else:
                    for alias in aliases:
                        if isinstance(alias, str) and alias.startswith("CVE-"):
                            cve = alias
                            break

                message = f"{vuln_id}: {pkg_name}@{pkg_version}"
                if description:
                    message = f"{vuln_id}: {description[:200]}"

                findings.append(
                    Finding(
                        tool=self.tool_name,
                        severity=Severity.MEDIUM,
                        category=Category.VULNERABILITY,
                        file="requirements.txt",
                        rule_id=vuln_id,
                        rule_name=vuln_id,
                        message=message,
                        cve=cve,
                        fix_hint=fix_hint,
                        raw=vuln,
                    )
                )

        return findings
