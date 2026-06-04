"""Normaliser for Snyk vulnerability scanner output."""

from __future__ import annotations

from typing import Any

from vibescan.models import Category, Finding, Severity
from vibescan.normalisers.base import BaseNormaliser


class SnykNormaliser(BaseNormaliser):
    """Transform Snyk JSON output into normalised Findings.

    Input: dict with "vulnerabilities" key.
    Each vuln: id, title, severity, packageName, version, from, fixedIn,
               description, CVSSv3, cvssScore, identifiers.
    """

    tool_name = "snyk"

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        vulnerabilities = raw_data.get("vulnerabilities", [])
        if not isinstance(vulnerabilities, list):
            return []

        findings: list[Finding] = []
        for vuln in vulnerabilities:
            if not isinstance(vuln, dict):
                continue

            vuln_id = vuln.get("id", "unknown")
            title = vuln.get("title", vuln_id)
            raw_severity = str(vuln.get("severity", "medium"))
            pkg_name = vuln.get("packageName", "unknown")
            pkg_version = vuln.get("version", "")
            description = vuln.get("description", "")
            cvss_score = vuln.get("cvssScore")
            fixed_in = vuln.get("fixedIn", [])
            fixed_in = fixed_in if isinstance(fixed_in, list) else []

            # Use native severity mapping
            severity = self.text_severity(raw_severity)

            # Parse CVSS score
            cvss: float | None = None
            if cvss_score is not None:
                try:
                    cvss = float(cvss_score)
                except (ValueError, TypeError):
                    cvss = None

            # Extract CVE from identifiers
            cve = None
            identifiers = vuln.get("identifiers", {})
            if isinstance(identifiers, dict):
                cve_list = identifiers.get("CVE", [])
                if isinstance(cve_list, list) and cve_list:
                    cve = str(cve_list[0])
            # Fallback: if vuln_id itself looks like a CVE
            if cve is None and vuln_id.startswith("CVE-"):
                cve = vuln_id

            # Fix hint
            fix_hint = None
            if fixed_in:
                fix_hint = f"Upgrade {pkg_name} to {fixed_in[0]}"

            # Dependency path from "from" field
            dep_from = vuln.get("from", [])
            dep_from = dep_from if isinstance(dep_from, list) else []

            message = f"{title}: {pkg_name}@{pkg_version}"
            if description:
                message = f"{title}: {description[:200]}"

            findings.append(
                Finding(
                    tool=self.tool_name,
                    severity=severity,
                    category=Category.VULNERABILITY,
                    file="package.json",
                    rule_id=vuln_id,
                    rule_name=title,
                    message=message,
                    cve=cve,
                    cvss=cvss,
                    fix_hint=fix_hint,
                    raw=vuln,
                )
            )

        return findings
