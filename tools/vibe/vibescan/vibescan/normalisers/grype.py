"""Normaliser for Grype vulnerability scanner output."""

from __future__ import annotations

from typing import Any

from vibescan.models import Category, Finding, Severity
from vibescan.normalisers.base import BaseNormaliser


class GrypeNormaliser(BaseNormaliser):
    """Transform Grype JSON output into normalised Findings.

    Input: dict with "matches" key.
    Each match: vulnerability.id, vulnerability.severity, vulnerability.description,
                vulnerability.cvss (list), vulnerability.fix.versions,
                artifact.name, artifact.version, artifact.locations[0].path.
    """

    tool_name = "grype"

    def _extract_cvss_score(self, cvss_list: Any) -> float | None:
        """Extract highest CVSS score from Grype's CVSS list.

        Grype stores CVSS as a list of objects, each with a "metrics" dict
        containing "baseScore", or sometimes a top-level "score" field.
        """
        if not isinstance(cvss_list, list):
            return None

        max_score: float | None = None
        for entry in cvss_list:
            if not isinstance(entry, dict):
                continue

            # Try metrics.baseScore first
            metrics = entry.get("metrics", {})
            if isinstance(metrics, dict):
                score = metrics.get("baseScore")
                if score is not None:
                    try:
                        score_float = float(score)
                        if max_score is None or score_float > max_score:
                            max_score = score_float
                    except (ValueError, TypeError):
                        pass

            # Fall back to top-level score
            score = entry.get("score")
            if score is not None:
                try:
                    score_float = float(score)
                    if max_score is None or score_float > max_score:
                        max_score = score_float
                except (ValueError, TypeError):
                    pass

        return max_score

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        matches = raw_data.get("matches", [])
        if not isinstance(matches, list):
            return []

        findings: list[Finding] = []
        for match in matches:
            if not isinstance(match, dict):
                continue

            vuln = match.get("vulnerability", {})
            vuln = vuln if isinstance(vuln, dict) else {}

            vuln_id = vuln.get("id", "unknown")
            description = vuln.get("description", "")
            raw_severity = vuln.get("severity", "MEDIUM")

            # CVSS-based severity
            cvss_score = self._extract_cvss_score(vuln.get("cvss"))
            if cvss_score is not None:
                severity = self.cvss_to_severity(cvss_score)
            else:
                severity = self.text_severity(str(raw_severity))

            # Fix versions
            fix_data = vuln.get("fix", {})
            fix_data = fix_data if isinstance(fix_data, dict) else {}
            fix_versions = fix_data.get("versions", [])
            fix_versions = fix_versions if isinstance(fix_versions, list) else []

            # Artifact info
            artifact = match.get("artifact", {})
            artifact = artifact if isinstance(artifact, dict) else {}
            pkg_name = artifact.get("name", "unknown")
            pkg_version = artifact.get("version", "")

            # File path from artifact locations
            locations = artifact.get("locations", [])
            locations = locations if isinstance(locations, list) else []
            file_path = "unknown"
            if locations and isinstance(locations[0], dict):
                file_path = locations[0].get("path", "unknown")

            # Build fix hint
            fix_hint = None
            if fix_versions:
                fix_hint = f"Upgrade {pkg_name} to {fix_versions[0]}"

            message = f"{vuln_id}: {pkg_name}@{pkg_version}"
            if description:
                message = f"{vuln_id}: {description[:200]}"

            findings.append(
                Finding(
                    tool=self.tool_name,
                    severity=severity,
                    category=Category.VULNERABILITY,
                    file=file_path,
                    rule_id=vuln_id,
                    rule_name=vuln_id,
                    message=message,
                    cve=vuln_id if vuln_id.startswith("CVE-") else None,
                    cvss=cvss_score,
                    fix_hint=fix_hint,
                    raw=match,
                )
            )

        return findings
