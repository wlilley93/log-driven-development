"""Normaliser for certigo JSON output."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser


class CertigoNormaliser(BaseNormaliser):
    tool_name = "certigo"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings: list[Finding] = []

        data = raw_data.get("data", {})
        file_path = raw_data.get("file", "unknown")

        # certigo --json outputs certificates as a list
        certs = data if isinstance(data, list) else data.get("certificates", [data])

        for cert in certs:
            if not isinstance(cert, dict):
                continue

            # Extract expiry info
            not_after = cert.get("not_after") or cert.get("notAfter") or cert.get("NotAfter")
            subject = cert.get("subject", {})
            subject_cn = ""
            if isinstance(subject, dict):
                subject_cn = subject.get("common_name", "") or subject.get("CN", "")
            elif isinstance(subject, str):
                subject_cn = subject

            issuer = cert.get("issuer", {})
            issuer_cn = ""
            if isinstance(issuer, dict):
                issuer_cn = issuer.get("common_name", "") or issuer.get("CN", "")
            elif isinstance(issuer, str):
                issuer_cn = issuer

            # Check key size
            key_size = cert.get("key_size") or cert.get("keySize") or cert.get("publicKeySize")
            if key_size and isinstance(key_size, int) and key_size < 2048:
                findings.append(Finding(
                    tool=self.tool_name,
                    severity=Severity.HIGH,
                    category=Category.SSL_TLS,
                    file=file_path,
                    rule_id="certigo-weak-key",
                    rule_name="Weak Certificate Key",
                    message=f"Certificate key size {key_size} bits is below 2048-bit minimum"
                            + (f" (CN={subject_cn})" if subject_cn else ""),
                    effort=Effort.MEDIUM,
                    fix_hint="Regenerate the certificate with at least a 2048-bit key",
                    raw=cert,
                ))

            # Check signature algorithm
            sig_algo = cert.get("signature_algorithm") or cert.get("signatureAlgorithm") or ""
            if isinstance(sig_algo, str) and any(
                weak in sig_algo.lower() for weak in ("sha1", "md5", "md2")
            ):
                findings.append(Finding(
                    tool=self.tool_name,
                    severity=Severity.HIGH,
                    category=Category.SSL_TLS,
                    file=file_path,
                    rule_id="certigo-weak-signature",
                    rule_name="Weak Signature Algorithm",
                    message=f"Certificate uses weak signature algorithm: {sig_algo}"
                            + (f" (CN={subject_cn})" if subject_cn else ""),
                    effort=Effort.MEDIUM,
                    fix_hint="Regenerate the certificate with SHA-256 or stronger",
                    raw=cert,
                ))

            # Parse and check expiry
            if not_after:
                expiry = self._parse_date(not_after)
                if expiry:
                    now = datetime.now(timezone.utc)
                    days_left = (expiry - now).days

                    if days_left < 0:
                        findings.append(Finding(
                            tool=self.tool_name,
                            severity=Severity.CRITICAL,
                            category=Category.SSL_TLS,
                            file=file_path,
                            rule_id="certigo-cert-expired",
                            rule_name="Certificate Expired",
                            message=f"Certificate expired {abs(days_left)} days ago"
                                    + (f" (CN={subject_cn})" if subject_cn else ""),
                            blocks_deploy=True,
                            effort=Effort.MEDIUM,
                            fix_hint="Renew the expired certificate immediately",
                            raw=cert,
                        ))
                    elif days_left < 7:
                        findings.append(Finding(
                            tool=self.tool_name,
                            severity=Severity.CRITICAL,
                            category=Category.SSL_TLS,
                            file=file_path,
                            rule_id="certigo-cert-expiring-critical",
                            rule_name="Certificate Expiring Within 7 Days",
                            message=f"Certificate expires in {days_left} days"
                                    + (f" (CN={subject_cn})" if subject_cn else ""),
                            blocks_deploy=True,
                            effort=Effort.MEDIUM,
                            fix_hint="Renew the certificate before it expires",
                            raw=cert,
                        ))
                    elif days_left < 30:
                        findings.append(Finding(
                            tool=self.tool_name,
                            severity=Severity.HIGH,
                            category=Category.SSL_TLS,
                            file=file_path,
                            rule_id="certigo-cert-expiring-soon",
                            rule_name="Certificate Expiring Within 30 Days",
                            message=f"Certificate expires in {days_left} days"
                                    + (f" (CN={subject_cn})" if subject_cn else ""),
                            effort=Effort.MEDIUM,
                            fix_hint="Plan certificate renewal soon",
                            raw=cert,
                        ))

            # Check self-signed
            if subject_cn and issuer_cn and subject_cn == issuer_cn:
                # Check if it's not a CA cert
                is_ca = cert.get("is_ca", False) or cert.get("isCA", False)
                if not is_ca:
                    findings.append(Finding(
                        tool=self.tool_name,
                        severity=Severity.MEDIUM,
                        category=Category.SSL_TLS,
                        file=file_path,
                        rule_id="certigo-self-signed",
                        rule_name="Self-Signed Certificate",
                        message=f"Certificate appears self-signed (CN={subject_cn})",
                        effort=Effort.MEDIUM,
                        fix_hint="Use a certificate from a trusted CA for production",
                        raw=cert,
                    ))

        return findings

    @staticmethod
    def _parse_date(date_val: Any) -> datetime | None:
        """Parse a date value from certigo output."""
        if isinstance(date_val, datetime):
            if date_val.tzinfo is None:
                return date_val.replace(tzinfo=timezone.utc)
            return date_val

        if not isinstance(date_val, str):
            return None

        formats = (
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S %Z",
            "%Y-%m-%d %H:%M:%S",
            "%b %d %H:%M:%S %Y %Z",
            "%b %d %H:%M:%S %Y",
        )

        for fmt in formats:
            try:
                dt = datetime.strptime(date_val, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue

        return None
