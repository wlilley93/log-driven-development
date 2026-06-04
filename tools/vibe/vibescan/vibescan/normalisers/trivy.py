"""Normaliser for Trivy vulnerability scanner output."""

from __future__ import annotations

from typing import Any

from vibescan.models import Category, Finding, Severity
from vibescan.normalisers.base import BaseNormaliser


class TrivyNormaliser(BaseNormaliser):
    """Transform Trivy JSON output into normalised Findings.

    Input: dict with "Results" key containing list of target results.
    Each target has "Vulnerabilities" list with: VulnerabilityID, PkgName,
    InstalledVersion, FixedVersion, Severity, Title, Description, CVSS.
    """

    tool_name = "trivy"

    def _extract_cvss_score(self, cvss_data: Any) -> float | None:
        """Extract highest CVSS score from Trivy's CVSS dict.

        Trivy stores CVSS as a dict mapping source to score objects,
        e.g. {"nvd": {"V3Score": 7.5}, "redhat": {"V3Score": 7.2}}.
        """
        if not isinstance(cvss_data, dict):
            return None

        max_score: float | None = None
        for _source, score_obj in cvss_data.items():
            if not isinstance(score_obj, dict):
                continue
            # Try V3Score first, then V2Score
            score = score_obj.get("V3Score") or score_obj.get("V2Score")
            if score is not None:
                try:
                    score_float = float(score)
                    if max_score is None or score_float > max_score:
                        max_score = score_float
                except (ValueError, TypeError):
                    continue

        return max_score

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        results = raw_data.get("Results", [])
        if not isinstance(results, list):
            return []

        findings: list[Finding] = []
        for target in results:
            if not isinstance(target, dict):
                continue

            target_name = target.get("Target", "unknown")
            vulnerabilities = target.get("Vulnerabilities") or []
            if not isinstance(vulnerabilities, list):
                continue

            for vuln in vulnerabilities:
                if not isinstance(vuln, dict):
                    continue

                vuln_id = vuln.get("VulnerabilityID", "unknown")
                pkg_name = vuln.get("PkgName", "unknown")
                installed_version = vuln.get("InstalledVersion", "")
                fixed_version = vuln.get("FixedVersion")
                title = vuln.get("Title", vuln_id)
                description = vuln.get("Description", "")

                # CVSS-based severity
                cvss_score = self._extract_cvss_score(vuln.get("CVSS"))
                if cvss_score is not None:
                    severity = self.cvss_to_severity(cvss_score)
                else:
                    # Fall back to Trivy's own severity string
                    severity = self.text_severity(vuln.get("Severity", "MEDIUM"))

                # Build fix hint
                fix_hint = None
                if fixed_version:
                    fix_hint = f"Upgrade {pkg_name} to {fixed_version}"

                message = f"{title}: {pkg_name}@{installed_version}"
                if description:
                    message = f"{title}: {description[:200]}"

                findings.append(
                    Finding(
                        tool=self.tool_name,
                        severity=severity,
                        category=Category.VULNERABILITY,
                        file=target_name,
                        rule_id=vuln_id,
                        rule_name=title,
                        message=message,
                        cve=vuln_id if vuln_id.startswith("CVE-") else None,
                        cvss=cvss_score,
                        fix_hint=fix_hint,
                        raw=vuln,
                    )
                )

        return findings
