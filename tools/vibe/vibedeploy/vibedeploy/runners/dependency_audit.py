"""dependency_audit — run npm audit and pip-audit for dependency vulnerabilities."""

from __future__ import annotations

import json
import shutil

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner


class DependencyAuditRunner(AsyncToolRunner):
    name = "dependency_audit"

    def should_run(self) -> bool:
        has_npm = self._file_exists("package.json", "package-lock.json")
        has_pip = self._file_exists("requirements.txt", "Pipfile", "pyproject.toml", "setup.py")
        if not has_npm and not has_pip:
            self.skip_reason = "no package.json or Python dependency files found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        findings: list[Finding] = []

        # Run npm audit if applicable
        if self._file_exists("package.json", "package-lock.json"):
            npm_findings = self._run_npm_audit()
            findings.extend(npm_findings)

        # Run pip-audit if applicable
        if self._file_exists("requirements.txt", "Pipfile", "pyproject.toml", "setup.py"):
            pip_findings = self._run_pip_audit()
            findings.extend(pip_findings)

        status = ToolStatus.SUCCESS if not findings else ToolStatus.PARTIAL
        return ToolResult(tool=self.name, status=status, findings=findings)

    def _run_npm_audit(self) -> list[Finding]:
        """Run npm audit --production and parse results."""
        findings: list[Finding] = []

        npm_bin = shutil.which("npm")
        if not npm_bin:
            return findings

        cmd = [npm_bin, "audit", "--production", "--json"]
        result = self._exec(cmd, timeout=120)

        if not result.stdout.strip():
            return findings

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return findings

        # npm audit JSON format: { "vulnerabilities": { "<pkg>": { ... } } }
        # or older: { "advisories": { "<id>": { ... } } }
        vulnerabilities = data.get("vulnerabilities", {})
        if isinstance(vulnerabilities, dict):
            for pkg_name, vuln_info in vulnerabilities.items():
                if not isinstance(vuln_info, dict):
                    continue

                sev_text = vuln_info.get("severity", "moderate")
                severity = self._map_npm_severity(sev_text)
                via = vuln_info.get("via", [])
                fix_available = vuln_info.get("fixAvailable", False)

                # Extract CVE and advisory URL from via entries
                cve = None
                docs_url = None
                message_parts = []
                for v in (via if isinstance(via, list) else [via]):
                    if isinstance(v, dict):
                        cve = v.get("cve", cve)
                        docs_url = v.get("url", docs_url)
                        title = v.get("title", v.get("name", ""))
                        if title:
                            message_parts.append(title)
                    elif isinstance(v, str):
                        message_parts.append(v)

                message = f"Vulnerable dependency: {pkg_name}"
                if message_parts:
                    message = f"{pkg_name}: {'; '.join(message_parts[:3])}"

                blocks = severity in (Severity.CRITICAL, Severity.HIGH)

                fix_hint = None
                if fix_available:
                    fix_hint = f"Run: npm audit fix (or npm update {pkg_name})"
                else:
                    fix_hint = f"Check for alternative packages or override for {pkg_name}"

                findings.append(Finding(
                    tool=self.name,
                    severity=severity,
                    category=Category.BUILD,
                    file="package.json",
                    rule_id=f"npm-vuln-{pkg_name}",
                    rule_name=f"NPM Vulnerability: {pkg_name}",
                    message=message,
                    blocks_deploy=blocks,
                    effort=Effort.LOW if fix_available else Effort.MEDIUM,
                    fix_hint=fix_hint,
                    fix_command="npm audit fix" if fix_available else None,
                    cve=cve,
                    docs_url=docs_url,
                    raw=vuln_info,
                ))

        # Handle older npm audit format with advisories
        advisories = data.get("advisories", {})
        if isinstance(advisories, dict) and not vulnerabilities:
            for adv_id, advisory in advisories.items():
                if not isinstance(advisory, dict):
                    continue

                sev_text = advisory.get("severity", "moderate")
                severity = self._map_npm_severity(sev_text)
                pkg_name = advisory.get("module_name", str(adv_id))
                title = advisory.get("title", f"Vulnerability in {pkg_name}")
                cve = None
                cves = advisory.get("cves", [])
                if cves:
                    cve = cves[0]

                findings.append(Finding(
                    tool=self.name,
                    severity=severity,
                    category=Category.BUILD,
                    file="package.json",
                    rule_id=f"npm-advisory-{adv_id}",
                    rule_name=title,
                    message=f"{pkg_name}: {title}",
                    blocks_deploy=severity in (Severity.CRITICAL, Severity.HIGH),
                    effort=Effort.LOW,
                    fix_hint=f"Run: npm audit fix (or manually update {pkg_name})",
                    fix_command="npm audit fix",
                    cve=cve,
                    docs_url=advisory.get("url"),
                    raw=advisory,
                ))

        # Add summary finding for vulnerability counts
        metadata = data.get("metadata", {})
        vuln_counts = metadata.get("vulnerabilities", {})
        if isinstance(vuln_counts, dict):
            total = sum(v for v in vuln_counts.values() if isinstance(v, int))
            critical = vuln_counts.get("critical", 0)
            high = vuln_counts.get("high", 0)
            if total > 0 and not vulnerabilities and not advisories:
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.CRITICAL if critical else Severity.HIGH if high else Severity.MEDIUM,
                    category=Category.BUILD,
                    file="package.json",
                    rule_id="npm-audit-summary",
                    rule_name="NPM Audit Summary",
                    message=f"npm audit found {total} vulnerabilities ({critical} critical, {high} high)",
                    blocks_deploy=critical > 0 or high > 0,
                    effort=Effort.MEDIUM,
                    fix_hint="Run: npm audit fix",
                    fix_command="npm audit fix",
                ))

        return findings

    def _run_pip_audit(self) -> list[Finding]:
        """Run pip-audit and parse results."""
        findings: list[Finding] = []

        pip_audit_bin = shutil.which("pip-audit")
        if not pip_audit_bin:
            return findings

        # Determine requirements file
        req_file = None
        for candidate in ("requirements.txt", "requirements/production.txt", "requirements/base.txt"):
            if self._file_exists(candidate):
                req_file = candidate
                break

        if req_file:
            cmd = [pip_audit_bin, "-r", req_file, "--format", "json"]
        else:
            cmd = [pip_audit_bin, "--format", "json"]

        result = self._exec(cmd, timeout=120)

        if not result.stdout.strip():
            return findings

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return findings

        # pip-audit JSON: { "dependencies": [ { "name": ..., "vulns": [...] } ] }
        # or a flat list of vulnerabilities
        deps = data.get("dependencies", data if isinstance(data, list) else [])
        for dep in deps:
            if not isinstance(dep, dict):
                continue

            pkg_name = dep.get("name", "unknown")
            version = dep.get("version", "")
            vulns = dep.get("vulns", dep.get("vulnerabilities", []))

            for vuln in vulns:
                if not isinstance(vuln, dict):
                    continue

                vuln_id = vuln.get("id", vuln.get("cve", "unknown"))
                description = vuln.get("description", vuln.get("summary", f"Vulnerability in {pkg_name}"))
                fix_versions = vuln.get("fix_versions", vuln.get("fixed_in", []))

                # Determine severity from CVSS or vuln ID
                cvss = None
                severity = Severity.MEDIUM
                if "cvss" in vuln:
                    try:
                        cvss = float(vuln["cvss"])
                        if cvss >= 9.0:
                            severity = Severity.CRITICAL
                        elif cvss >= 7.0:
                            severity = Severity.HIGH
                        elif cvss >= 4.0:
                            severity = Severity.MEDIUM
                        else:
                            severity = Severity.LOW
                    except (ValueError, TypeError):
                        pass

                blocks = severity in (Severity.CRITICAL, Severity.HIGH)

                fix_hint = None
                if fix_versions:
                    fix_str = ", ".join(str(v) for v in fix_versions[:3])
                    fix_hint = f"Upgrade {pkg_name} to {fix_str}"
                else:
                    fix_hint = f"Check for updates to {pkg_name} or find an alternative"

                findings.append(Finding(
                    tool=self.name,
                    severity=severity,
                    category=Category.BUILD,
                    file=req_file or "requirements.txt",
                    rule_id=f"pip-vuln-{vuln_id}",
                    rule_name=f"Python Vulnerability: {pkg_name}",
                    message=f"{pkg_name}=={version}: {description[:200]}",
                    blocks_deploy=blocks,
                    effort=Effort.LOW,
                    fix_hint=fix_hint,
                    cve=vuln_id if vuln_id.startswith("CVE") else None,
                    cvss=cvss,
                    docs_url=vuln.get("url"),
                    raw=vuln,
                ))

        return findings

    @staticmethod
    def _map_npm_severity(text: str) -> Severity:
        """Map npm audit severity text to Severity enum."""
        mapping = {
            "critical": Severity.CRITICAL,
            "high": Severity.HIGH,
            "moderate": Severity.MEDIUM,
            "low": Severity.LOW,
            "info": Severity.INFO,
        }
        return mapping.get(text.lower(), Severity.MEDIUM)
