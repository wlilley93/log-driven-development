"""Normaliser for grype JSON output."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser


class GrypeNormaliser(BaseNormaliser):
    tool_name = "grype"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings: list[Finding] = []

        matches = raw_data.get("matches", [])

        for match in matches:
            vulnerability = match.get("vulnerability", {})
            artifact = match.get("artifact", {})
            related = match.get("relatedVulnerabilities", [])

            vuln_id = vulnerability.get("id", "unknown")
            severity_text = vulnerability.get("severity", "Unknown")
            description = vulnerability.get("description", "")
            fix_versions = vulnerability.get("fix", {}).get("versions", [])
            data_source = vulnerability.get("dataSource", None)

            # Get CVSS score from vulnerability or related
            cvss_score = None
            cvss_entries = vulnerability.get("cvss", [])
            if cvss_entries:
                cvss_score = max(
                    (entry.get("metrics", {}).get("baseScore", 0) for entry in cvss_entries),
                    default=None,
                )
            if cvss_score is None and related:
                for rel in related:
                    rel_cvss = rel.get("cvss", [])
                    if rel_cvss:
                        cvss_score = max(
                            (entry.get("metrics", {}).get("baseScore", 0) for entry in rel_cvss),
                            default=None,
                        )
                        if cvss_score:
                            break

            # Artifact info
            pkg_name = artifact.get("name", "unknown")
            pkg_version = artifact.get("version", "unknown")
            pkg_type = artifact.get("type", "unknown")
            locations = artifact.get("locations", [])
            file_path = locations[0].get("path", ".") if locations else "."

            # Map severity
            if cvss_score is not None:
                severity = self.cvss_to_severity(cvss_score)
            else:
                severity = self.text_severity(severity_text)

            # Build fix hint
            fix_hint = None
            if fix_versions:
                fix_hint = f"Upgrade {pkg_name} to {', '.join(fix_versions)}"

            # Truncate description
            message = f"{vuln_id}: {pkg_name}@{pkg_version} ({pkg_type})"
            if description:
                desc_short = description[:200] + "..." if len(description) > 200 else description
                message = f"{message} — {desc_short}"

            findings.append(Finding(
                tool=self.tool_name,
                severity=severity,
                category=Category.SUPPLY_CHAIN,
                file=file_path,
                rule_id=vuln_id,
                rule_name=f"{pkg_name} vulnerability",
                message=message,
                cve=vuln_id if vuln_id.startswith("CVE-") else None,
                cvss=cvss_score,
                fix_hint=fix_hint,
                docs_url=data_source,
                effort=Effort.LOW if fix_versions else Effort.MEDIUM,
                blocks_deploy=severity in (Severity.CRITICAL, Severity.HIGH),
                raw=match,
            ))

        return findings
