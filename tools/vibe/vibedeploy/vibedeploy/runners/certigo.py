"""certigo runner — certificate inspection and expiry checking."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.normalisers.certigo import CertigoNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class CertigoRunner(AsyncToolRunner):
    name = "certigo"

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "certigo not installed"
            return False
        cert_files = self._scan_files("*.pem", "*.crt", "*.cert")
        if not cert_files:
            self.skip_reason = "no certificate files found (*.pem, *.crt)"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        cert_files = self._scan_files("*.pem", "*.crt", "*.cert")
        if not cert_files:
            return ToolResult(tool=self.name, status=ToolStatus.SKIPPED)

        all_findings: list[Finding] = []
        normaliser = CertigoNormaliser()

        for cert_file in cert_files:
            try:
                rel_path = str(cert_file.relative_to(self.target))
            except ValueError:
                rel_path = str(cert_file)

            try:
                result = self._exec(
                    [self.bin_path, "dump", "--json", str(cert_file)],
                    timeout=30,
                )
            except Exception:
                all_findings.append(Finding(
                    tool=self.name,
                    severity=Severity.LOW,
                    category=Category.SSL_TLS,
                    file=rel_path,
                    rule_id="certigo-exec-error",
                    rule_name="Certigo Execution Error",
                    message=f"Failed to inspect certificate: {rel_path}",
                    effort=Effort.LOW,
                ))
                continue

            if result.stdout.strip():
                try:
                    data = json.loads(result.stdout)
                    findings = normaliser.normalise({
                        "data": data,
                        "file": rel_path,
                    })
                    all_findings.extend(findings)
                except json.JSONDecodeError:
                    # Try to parse text output for expiry info
                    findings = self._parse_text_output(result.stdout, rel_path)
                    all_findings.extend(findings)
            elif result.stderr.strip():
                all_findings.append(Finding(
                    tool=self.name,
                    severity=Severity.MEDIUM,
                    category=Category.SSL_TLS,
                    file=rel_path,
                    rule_id="certigo-parse-error",
                    rule_name="Certificate Parse Error",
                    message=f"certigo could not parse {rel_path}: {result.stderr[:200]}",
                    effort=Effort.LOW,
                ))

        return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=all_findings)

    def _parse_text_output(self, output: str, file_path: str) -> list[Finding]:
        """Fallback: parse certigo text output for expiry dates."""
        findings: list[Finding] = []

        # Look for "Not After" or expiry date patterns
        expiry_match = re.search(
            r"Not After\s*:\s*(.+?)(?:\n|$)", output, re.IGNORECASE
        )
        if expiry_match:
            try:
                expiry_str = expiry_match.group(1).strip()
                # Try common date formats
                for fmt in (
                    "%Y-%m-%d %H:%M:%S %Z",
                    "%Y-%m-%dT%H:%M:%SZ",
                    "%b %d %H:%M:%S %Y %Z",
                ):
                    try:
                        expiry = datetime.strptime(expiry_str, fmt).replace(
                            tzinfo=timezone.utc
                        )
                        break
                    except ValueError:
                        continue
                else:
                    return findings

                now = datetime.now(timezone.utc)
                days_left = (expiry - now).days

                if days_left < 0:
                    findings.append(Finding(
                        tool=self.name,
                        severity=Severity.CRITICAL,
                        category=Category.SSL_TLS,
                        file=file_path,
                        rule_id="certigo-cert-expired",
                        rule_name="Certificate Expired",
                        message=f"Certificate expired {abs(days_left)} days ago",
                        blocks_deploy=True,
                        effort=Effort.MEDIUM,
                        fix_hint="Renew the expired certificate immediately",
                    ))
                elif days_left < 7:
                    findings.append(Finding(
                        tool=self.name,
                        severity=Severity.CRITICAL,
                        category=Category.SSL_TLS,
                        file=file_path,
                        rule_id="certigo-cert-expiring-critical",
                        rule_name="Certificate Expiring Soon",
                        message=f"Certificate expires in {days_left} days",
                        blocks_deploy=True,
                        effort=Effort.MEDIUM,
                        fix_hint="Renew the certificate before it expires",
                    ))
                elif days_left < 30:
                    findings.append(Finding(
                        tool=self.name,
                        severity=Severity.HIGH,
                        category=Category.SSL_TLS,
                        file=file_path,
                        rule_id="certigo-cert-expiring-soon",
                        rule_name="Certificate Expiring Soon",
                        message=f"Certificate expires in {days_left} days",
                        effort=Effort.MEDIUM,
                        fix_hint="Plan certificate renewal",
                    ))
            except Exception:
                pass

        return findings
