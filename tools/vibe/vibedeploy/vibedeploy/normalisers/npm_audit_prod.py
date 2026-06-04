"""Normaliser for npm audit --production JSON output."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser


class NpmAuditProdNormaliser(BaseNormaliser):
    tool_name = "npm_audit_prod"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings: list[Finding] = []

        # npm audit v2 JSON format (npm 7+)
        vulnerabilities = raw_data.get("vulnerabilities", {})
        if vulnerabilities:
            return self._normalise_v2(vulnerabilities)

        # npm audit v1 JSON format (npm 6)
        advisories = raw_data.get("advisories", {})
        if advisories:
            return self._normalise_v1(advisories)

        return findings

    def _normalise_v2(self, vulnerabilities: dict) -> list[Finding]:
        """Normalise npm audit v2 format (npm 7+)."""
        findings: list[Finding] = []

        for pkg_name, vuln_data in vulnerabilities.items():
            severity_text = vuln_data.get("severity", "moderate")
            is_direct = vuln_data.get("isDirect", False)
            via_list = vuln_data.get("via", [])
            fix_available = vuln_data.get("fixAvailable", False)
            effects = vuln_data.get("effects", [])
            vuln_range = vuln_data.get("range", "")

            severity = self.text_severity(severity_text)

            # Extract advisory details from 'via' entries
            advisories: list[dict] = []
            for via in via_list:
                if isinstance(via, dict):
                    advisories.append(via)

            if advisories:
                for advisory in advisories:
                    adv_title = advisory.get("title", "Unknown vulnerability")
                    adv_url = advisory.get("url", None)
                    adv_severity = advisory.get("severity", severity_text)
                    adv_cwe = advisory.get("cwe", [])
                    adv_cvss = advisory.get("cvss", {}).get("score", None)
                    source_id = str(advisory.get("source", "unknown"))

                    mapped_severity = self.text_severity(adv_severity)
                    if adv_cvss is not None:
                        mapped_severity = self.cvss_to_severity(adv_cvss)

                    fix_hint = None
                    if fix_available:
                        if isinstance(fix_available, dict):
                            fix_name = fix_available.get("name", pkg_name)
                            fix_ver = fix_available.get("version", "latest")
                            fix_hint = f"npm install {fix_name}@{fix_ver}"
                        else:
                            fix_hint = f"npm audit fix (or update {pkg_name})"

                    findings.append(Finding(
                        tool=self.tool_name,
                        severity=mapped_severity,
                        category=Category.SUPPLY_CHAIN,
                        file="package-lock.json",
                        rule_id=f"npm-advisory-{source_id}",
                        rule_name=adv_title,
                        message=f"{pkg_name} ({vuln_range}): {adv_title}",
                        cvss=adv_cvss,
                        fix_hint=fix_hint,
                        docs_url=adv_url,
                        effort=Effort.LOW if fix_available else Effort.MEDIUM,
                        blocks_deploy=mapped_severity in (Severity.CRITICAL, Severity.HIGH),
                        raw={"package": pkg_name, "advisory": advisory},
                    ))
            else:
                # 'via' contains only package name strings (transitive)
                via_names = [v for v in via_list if isinstance(v, str)]
                fix_hint = None
                if fix_available:
                    fix_hint = f"npm audit fix (or update {pkg_name})"

                findings.append(Finding(
                    tool=self.tool_name,
                    severity=severity,
                    category=Category.SUPPLY_CHAIN,
                    file="package-lock.json",
                    rule_id=f"npm-vuln-{pkg_name}",
                    rule_name=f"Vulnerable dependency: {pkg_name}",
                    message=f"{pkg_name} ({vuln_range}) via {', '.join(via_names)}",
                    fix_hint=fix_hint,
                    effort=Effort.LOW if fix_available else Effort.MEDIUM,
                    blocks_deploy=severity in (Severity.CRITICAL, Severity.HIGH),
                ))

        return findings

    def _normalise_v1(self, advisories: dict) -> list[Finding]:
        """Normalise npm audit v1 format (npm 6)."""
        findings: list[Finding] = []

        for adv_id, advisory in advisories.items():
            title = advisory.get("title", "Unknown vulnerability")
            module_name = advisory.get("module_name", "unknown")
            severity_text = advisory.get("severity", "moderate")
            url = advisory.get("url", None)
            vulnerable_versions = advisory.get("vulnerable_versions", "")
            patched_versions = advisory.get("patched_versions", "")
            cves = advisory.get("cves", [])
            cvss_score = advisory.get("cvss", {}).get("score", None)

            severity = self.text_severity(severity_text)
            if cvss_score is not None:
                severity = self.cvss_to_severity(cvss_score)

            cve = cves[0] if cves else None
            fix_hint = None
            if patched_versions and patched_versions != "<0.0.0":
                fix_hint = f"npm install {module_name}@\"{patched_versions}\""

            findings.append(Finding(
                tool=self.tool_name,
                severity=severity,
                category=Category.SUPPLY_CHAIN,
                file="package-lock.json",
                rule_id=f"npm-advisory-{adv_id}",
                rule_name=title,
                message=f"{module_name} ({vulnerable_versions}): {title}",
                cve=cve,
                cvss=cvss_score,
                fix_hint=fix_hint,
                docs_url=url,
                effort=Effort.LOW if patched_versions else Effort.MEDIUM,
                blocks_deploy=severity in (Severity.CRITICAL, Severity.HIGH),
                raw=advisory,
            ))

        return findings
