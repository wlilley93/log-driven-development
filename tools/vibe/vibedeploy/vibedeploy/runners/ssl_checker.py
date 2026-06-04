"""ssl_checker — custom runner that checks SSL/TLS configuration via URL."""

from __future__ import annotations

import socket
import ssl
from datetime import datetime, timezone
from urllib.parse import urlparse

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner


class SslCheckerRunner(AsyncToolRunner):
    name = "ssl_checker"
    requires_url = True

    def should_run(self) -> bool:
        if not self.config.url:
            self.skip_reason = "requires --url"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        url = self.config.url
        if not url:
            return self._make_error_result("No URL configured")

        parsed = urlparse(url if "://" in url else f"https://{url}")
        hostname = parsed.hostname
        port = parsed.port or 443

        if not hostname:
            return self._make_error_result(f"Could not parse hostname from URL: {url}")

        findings: list[Finding] = []

        # Check certificate details
        try:
            context = ssl.create_default_context()
            with socket.create_connection((hostname, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    protocol_version = ssock.version()
                    cipher = ssock.cipher()

                    if cert:
                        self._check_certificate(cert, hostname, findings)
                    if protocol_version:
                        self._check_protocol(protocol_version, hostname, findings)
                    if cipher:
                        self._check_cipher(cipher, hostname, findings)

        except ssl.SSLCertVerificationError as e:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.CRITICAL,
                category=Category.SSL_TLS,
                file=hostname,
                rule_id="ssl-cert-verification-failed",
                rule_name="Certificate Verification Failed",
                message=f"SSL certificate verification failed for {hostname}: {e}",
                blocks_deploy=True,
                effort=Effort.MEDIUM,
                fix_hint="Ensure the certificate is valid, not expired, and issued by a trusted CA",
            ))
        except ssl.SSLError as e:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.HIGH,
                category=Category.SSL_TLS,
                file=hostname,
                rule_id="ssl-connection-error",
                rule_name="SSL Connection Error",
                message=f"SSL connection error for {hostname}: {e}",
                effort=Effort.MEDIUM,
                fix_hint="Check that the server supports TLS and the certificate is properly configured",
            ))
        except (socket.timeout, socket.gaierror, ConnectionRefusedError, OSError) as e:
            return self._make_error_result(f"Could not connect to {hostname}:{port}: {e}")

        # Check for deprecated protocol support
        self._check_deprecated_protocols(hostname, port, findings)

        return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=findings)

    def _check_certificate(
        self, cert: dict, hostname: str, findings: list[Finding]
    ) -> None:
        """Check certificate expiry and details."""
        not_after = cert.get("notAfter")
        if not_after:
            try:
                # Python ssl cert dates use format: 'Mon DD HH:MM:SS YYYY GMT'
                expiry = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(
                    tzinfo=timezone.utc
                )
                now = datetime.now(timezone.utc)
                days_left = (expiry - now).days

                if days_left < 0:
                    findings.append(Finding(
                        tool=self.name,
                        severity=Severity.CRITICAL,
                        category=Category.SSL_TLS,
                        file=hostname,
                        rule_id="ssl-cert-expired",
                        rule_name="SSL Certificate Expired",
                        message=f"SSL certificate for {hostname} expired {abs(days_left)} days ago",
                        blocks_deploy=True,
                        effort=Effort.MEDIUM,
                        fix_hint="Renew the SSL certificate immediately",
                    ))
                elif days_left < 7:
                    findings.append(Finding(
                        tool=self.name,
                        severity=Severity.CRITICAL,
                        category=Category.SSL_TLS,
                        file=hostname,
                        rule_id="ssl-cert-expiring-critical",
                        rule_name="SSL Certificate Expiring Within 7 Days",
                        message=f"SSL certificate for {hostname} expires in {days_left} days",
                        blocks_deploy=True,
                        effort=Effort.MEDIUM,
                        fix_hint="Renew the SSL certificate before it expires",
                    ))
                elif days_left < 30:
                    findings.append(Finding(
                        tool=self.name,
                        severity=Severity.HIGH,
                        category=Category.SSL_TLS,
                        file=hostname,
                        rule_id="ssl-cert-expiring-soon",
                        rule_name="SSL Certificate Expiring Within 30 Days",
                        message=f"SSL certificate for {hostname} expires in {days_left} days",
                        effort=Effort.MEDIUM,
                        fix_hint="Plan SSL certificate renewal",
                    ))
                elif days_left < 90:
                    findings.append(Finding(
                        tool=self.name,
                        severity=Severity.LOW,
                        category=Category.SSL_TLS,
                        file=hostname,
                        rule_id="ssl-cert-expiring-90d",
                        rule_name="SSL Certificate Expiring Within 90 Days",
                        message=f"SSL certificate for {hostname} expires in {days_left} days",
                        effort=Effort.LOW,
                        fix_hint="Consider setting up auto-renewal (e.g., certbot)",
                    ))
            except ValueError:
                pass

        # Check subject
        subject = dict(x[0] for x in cert.get("subject", []))
        issuer = dict(x[0] for x in cert.get("issuer", []))

        # Check if self-signed
        subject_cn = subject.get("commonName", "")
        issuer_cn = issuer.get("commonName", "")
        issuer_org = issuer.get("organizationName", "")

        if subject_cn == issuer_cn and not issuer_org:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.HIGH,
                category=Category.SSL_TLS,
                file=hostname,
                rule_id="ssl-self-signed",
                rule_name="Self-Signed Certificate",
                message=f"Certificate for {hostname} appears to be self-signed",
                effort=Effort.MEDIUM,
                fix_hint="Use a certificate from a trusted CA (e.g., Let's Encrypt)",
            ))

    def _check_protocol(
        self, protocol_version: str, hostname: str, findings: list[Finding]
    ) -> None:
        """Check the negotiated protocol version."""
        version_lower = protocol_version.lower()

        if "tlsv1.3" in version_lower:
            # TLS 1.3 is great, no findings
            return

        if "tlsv1.2" in version_lower:
            # TLS 1.2 is acceptable but note TLS 1.3 is preferred
            findings.append(Finding(
                tool=self.name,
                severity=Severity.INFO,
                category=Category.SSL_TLS,
                file=hostname,
                rule_id="ssl-tls12-only",
                rule_name="TLS 1.2 Negotiated",
                message=f"Server negotiated TLS 1.2 (TLS 1.3 preferred) for {hostname}",
                effort=Effort.MEDIUM,
                fix_hint="Enable TLS 1.3 on the server for better performance and security",
            ))
            return

        if "tlsv1.1" in version_lower:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.HIGH,
                category=Category.SSL_TLS,
                file=hostname,
                rule_id="ssl-tls11-deprecated",
                rule_name="Deprecated TLS 1.1",
                message=f"Server negotiated deprecated TLS 1.1 for {hostname}",
                effort=Effort.MEDIUM,
                fix_hint="Disable TLS 1.1 and use TLS 1.2+ only",
            ))
            return

        if "tlsv1.0" in version_lower or "tlsv1" in version_lower:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.HIGH,
                category=Category.SSL_TLS,
                file=hostname,
                rule_id="ssl-tls10-deprecated",
                rule_name="Deprecated TLS 1.0",
                message=f"Server negotiated deprecated TLS 1.0 for {hostname}",
                effort=Effort.MEDIUM,
                fix_hint="Disable TLS 1.0 and use TLS 1.2+ only",
            ))
            return

        if "sslv3" in version_lower or "sslv2" in version_lower:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.CRITICAL,
                category=Category.SSL_TLS,
                file=hostname,
                rule_id="ssl-legacy-protocol",
                rule_name="Legacy SSL Protocol",
                message=f"Server negotiated insecure {protocol_version} for {hostname}",
                blocks_deploy=True,
                effort=Effort.MEDIUM,
                fix_hint="Disable SSLv2/SSLv3 immediately; use TLS 1.2+ only",
            ))

    def _check_cipher(
        self, cipher: tuple, hostname: str, findings: list[Finding]
    ) -> None:
        """Check the negotiated cipher suite."""
        cipher_name = cipher[0] if cipher else ""
        cipher_lower = cipher_name.lower()

        weak_ciphers = {
            "rc4": "RC4 is broken — disable all RC4 cipher suites",
            "des": "DES/3DES is weak — disable DES-CBC cipher suites",
            "null": "NULL cipher provides no encryption",
            "export": "Export-grade ciphers are weak — remove EXPORT suites",
            "anon": "Anonymous cipher suites are vulnerable to MITM attacks",
        }

        for weak, hint in weak_ciphers.items():
            if weak in cipher_lower:
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.HIGH,
                    category=Category.SSL_TLS,
                    file=hostname,
                    rule_id=f"ssl-weak-cipher-{weak}",
                    rule_name=f"Weak Cipher: {cipher_name}",
                    message=f"Server using weak cipher suite {cipher_name} for {hostname}",
                    effort=Effort.MEDIUM,
                    fix_hint=hint,
                ))
                break

    def _check_deprecated_protocols(
        self, hostname: str, port: int, findings: list[Finding]
    ) -> None:
        """Attempt connections with deprecated protocols to check if they are enabled."""
        deprecated = [
            ("TLS 1.0", ssl.TLSVersion.TLSv1, Severity.HIGH),
            ("TLS 1.1", ssl.TLSVersion.TLSv1_1, Severity.HIGH),
        ]

        for proto_name, proto_version, severity in deprecated:
            try:
                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                ctx.minimum_version = proto_version
                ctx.maximum_version = proto_version

                with socket.create_connection((hostname, port), timeout=5) as sock:
                    with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                        # Connection succeeded — deprecated protocol is enabled
                        findings.append(Finding(
                            tool=self.name,
                            severity=severity,
                            category=Category.SSL_TLS,
                            file=hostname,
                            rule_id=f"ssl-supports-{proto_name.lower().replace(' ', '-').replace('.', '')}",
                            rule_name=f"Supports Deprecated {proto_name}",
                            message=f"Server {hostname} accepts deprecated {proto_name} connections",
                            effort=Effort.MEDIUM,
                            fix_hint=f"Disable {proto_name} in server TLS configuration",
                        ))
            except (ssl.SSLError, socket.error, OSError):
                # Good — connection with deprecated protocol failed
                pass
