"""Normaliser for trivy image scan JSON output."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser

_SEVERITY_MAP = {
    "CRITICAL": Severity.CRITICAL,
    "HIGH": Severity.HIGH,
    "MEDIUM": Severity.MEDIUM,
    "LOW": Severity.LOW,
    "UNKNOWN": Severity.INFO,
}


class TrivyImageNormaliser(BaseNormaliser):
    tool_name = "trivy_image"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings: list[Finding] = []

        if not isinstance(raw_data, dict):
            return findings

        results = raw_data.get("Results", [])
        if not isinstance(results, list):
            return findings

        for result in results:
            target = result.get("Target", "unknown")
            result_type = result.get("Type", "")
            vulnerabilities = result.get("Vulnerabilities") or []

            for vuln in vulnerabilities:
                vuln_id = vuln.get("VulnerabilityID", "UNKNOWN")
                pkg_name = vuln.get("PkgName", "unknown")
                installed_version = vuln.get("InstalledVersion", "")
                fixed_version = vuln.get("FixedVersion", "")
                title = vuln.get("Title", "")
                description = vuln.get("Description", "")
                severity_str = vuln.get("Severity", "UNKNOWN")
                cvss_data = vuln.get("CVSS", {})
                primary_url = vuln.get("PrimaryURL", "")
                references = vuln.get("References", [])

                severity = _SEVERITY_MAP.get(severity_str, Severity.MEDIUM)

                # Extract best available CVSS score
                cvss_score = None
                for source in ("nvd", "redhat", "ghsa"):
                    source_data = cvss_data.get(source, {})
                    if isinstance(source_data, dict):
                        score = source_data.get("V3Score") or source_data.get("V2Score")
                        if score is not None:
                            cvss_score = float(score)
                            break
                # Also check top-level CVSS fields
                if cvss_score is None:
                    for source_data in cvss_data.values():
                        if isinstance(source_data, dict):
                            score = source_data.get("V3Score") or source_data.get("V2Score")
                            if score is not None:
                                cvss_score = float(score)
                                break

                # Override severity from CVSS if available
                if cvss_score is not None:
                    severity = self.cvss_to_severity(cvss_score)

                # CRITICAL CVEs block deploy
                blocks = severity == Severity.CRITICAL

                # Build message
                msg_parts = []
                if title:
                    msg_parts.append(title)
                else:
                    msg_parts.append(f"Vulnerability {vuln_id} in {pkg_name}")

                if installed_version:
                    msg_parts.append(f"Installed: {installed_version}")
                if fixed_version:
                    msg_parts.append(f"Fixed in: {fixed_version}")

                message = " | ".join(msg_parts)

                # Fix hint based on whether a fix is available
                fix_hint = None
                if fixed_version:
                    fix_hint = f"Update {pkg_name} to version {fixed_version}"
                    effort = Effort.LOW
                else:
                    fix_hint = f"No fix available yet for {vuln_id} in {pkg_name}. Consider using an alternative package."
                    effort = Effort.MEDIUM

                docs_url = primary_url or (references[0] if references else None)

                findings.append(Finding(
                    tool=self.tool_name,
                    severity=severity,
                    category=Category.DOCKER,
                    file=target,
                    rule_id=vuln_id,
                    rule_name=f"{pkg_name}: {vuln_id}",
                    message=message,
                    blocks_deploy=blocks,
                    effort=effort,
                    fix_hint=fix_hint,
                    docs_url=docs_url,
                    cve=vuln_id if vuln_id.startswith("CVE-") else None,
                    cvss=cvss_score,
                    raw=vuln,
                ))

        return findings
