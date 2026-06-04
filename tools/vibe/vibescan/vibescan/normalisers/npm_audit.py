"""Normaliser for npm audit output."""

from __future__ import annotations

from typing import Any

from vibescan.models import Category, Finding, Severity
from vibescan.normalisers.base import BaseNormaliser


class NpmAuditNormaliser(BaseNormaliser):
    """Transform npm audit JSON output into normalised Findings.

    Input: dict with "vulnerabilities" key (npm v7+ format).
    Each entry maps package name to {severity, via, effects, range, nodes, fix}.
    """

    tool_name = "npm-audit"

    _severity_map = {
        "critical": Severity.CRITICAL,
        "high": Severity.HIGH,
        "moderate": Severity.MEDIUM,
        "low": Severity.LOW,
        "info": Severity.INFO,
    }

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        vulnerabilities = raw_data.get("vulnerabilities", {})
        if not isinstance(vulnerabilities, dict):
            return []

        findings: list[Finding] = []
        for pkg_name, vuln_data in vulnerabilities.items():
            if not isinstance(vuln_data, dict):
                continue

            raw_severity = str(vuln_data.get("severity", "medium")).lower()
            severity = self._severity_map.get(raw_severity, Severity.MEDIUM)

            # Build message from "via" field
            via = vuln_data.get("via", [])
            via = via if isinstance(via, list) else [via]
            via_descriptions: list[str] = []
            cve = None
            for v in via:
                if isinstance(v, dict):
                    via_descriptions.append(v.get("title", v.get("name", str(v))))
                    # Extract CVE from url if present
                    url = v.get("url", "")
                    if isinstance(url, str) and "CVE-" in url.upper():
                        cve = url.split("/")[-1] if "/" in url else None
                elif isinstance(v, str):
                    via_descriptions.append(v)

            message = f"{pkg_name}: {', '.join(via_descriptions)}" if via_descriptions else f"Vulnerability in {pkg_name}"

            # Fix info
            fix_data = vuln_data.get("fix", {})
            fix_data = fix_data if isinstance(fix_data, dict) else {}
            fix_available = fix_data.get("available", False)
            fix_hint = None
            if fix_available:
                fix_name = fix_data.get("name", pkg_name)
                fix_version = fix_data.get("version", "")
                if fix_version:
                    fix_hint = f"Upgrade {fix_name} to {fix_version}"
                else:
                    fix_hint = f"Run npm audit fix for {pkg_name}"

            # Range info
            version_range = vuln_data.get("range", "")

            findings.append(
                Finding(
                    tool=self.tool_name,
                    severity=severity,
                    category=Category.VULNERABILITY,
                    file="package.json",
                    rule_id=pkg_name,
                    rule_name=pkg_name,
                    message=message,
                    cve=cve,
                    fix_hint=fix_hint,
                    raw=vuln_data,
                )
            )

        return findings
