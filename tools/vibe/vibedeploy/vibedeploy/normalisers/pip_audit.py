"""Normaliser for pip-audit JSON output."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser


class PipAuditNormaliser(BaseNormaliser):
    tool_name = "pip_audit"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings: list[Finding] = []

        # pip-audit JSON format: {"dependencies": [...]}
        dependencies = raw_data.get("dependencies", [])

        for dep in dependencies:
            pkg_name = dep.get("name", "unknown")
            pkg_version = dep.get("version", "unknown")
            vulns = dep.get("vulns", [])

            for vuln in vulns:
                vuln_id = vuln.get("id", "unknown")
                description = vuln.get("description", "")
                fix_versions = vuln.get("fix_versions", [])
                aliases = vuln.get("aliases", [])

                # Extract CVE from vuln_id or aliases
                cve = None
                if vuln_id.startswith("CVE-"):
                    cve = vuln_id
                else:
                    for alias in aliases:
                        if alias.startswith("CVE-"):
                            cve = alias
                            break

                # Determine severity from description heuristics or default
                severity = self._infer_severity(description, vuln_id)

                # Build fix hint
                fix_hint = None
                if fix_versions:
                    fix_hint = f"pip install {pkg_name}>={fix_versions[0]}"

                # Truncate description
                desc_short = description[:200] + "..." if len(description) > 200 else description
                message = f"{vuln_id}: {pkg_name}=={pkg_version} — {desc_short}" if desc_short else f"{vuln_id}: {pkg_name}=={pkg_version}"

                findings.append(Finding(
                    tool=self.tool_name,
                    severity=severity,
                    category=Category.SUPPLY_CHAIN,
                    file="requirements.txt",
                    rule_id=vuln_id,
                    rule_name=f"{pkg_name} vulnerability",
                    message=message,
                    cve=cve,
                    fix_hint=fix_hint,
                    effort=Effort.LOW if fix_versions else Effort.MEDIUM,
                    blocks_deploy=severity in (Severity.CRITICAL, Severity.HIGH),
                    raw=vuln,
                ))

        return findings

    @staticmethod
    def _infer_severity(description: str, vuln_id: str) -> Severity:
        """Infer severity from description keywords when CVSS is unavailable."""
        desc_lower = description.lower()
        if any(kw in desc_lower for kw in ("remote code execution", "rce", "arbitrary code")):
            return Severity.CRITICAL
        if any(kw in desc_lower for kw in ("sql injection", "command injection", "ssrf", "xss")):
            return Severity.HIGH
        if any(kw in desc_lower for kw in ("denial of service", "dos", "buffer overflow")):
            return Severity.HIGH
        if any(kw in desc_lower for kw in ("information disclosure", "path traversal")):
            return Severity.MEDIUM
        # PYSEC advisories are generally at least medium
        if vuln_id.startswith("PYSEC-"):
            return Severity.MEDIUM
        return Severity.MEDIUM
