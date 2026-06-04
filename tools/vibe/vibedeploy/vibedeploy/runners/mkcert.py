"""mkcert runner — detects self-signed dev certificates in production."""

from __future__ import annotations

import re
from pathlib import Path

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner


# Patterns indicating mkcert-generated certificates
_MKCERT_INDICATORS = [
    b"mkcert",
    b"mkcert development CA",
    b"mkcert development certificate",
]

# Text-based patterns for PEM header inspection
_MKCERT_TEXT_PATTERNS = [
    re.compile(r"mkcert", re.IGNORECASE),
    re.compile(r"mkcert development CA", re.IGNORECASE),
]

# Common dev cert file names
_DEV_CERT_NAMES = [
    "localhost.pem",
    "localhost-key.pem",
    "localhost+*.pem",
    "dev.pem",
    "dev-key.pem",
    "local.pem",
    "local-key.pem",
]


class MkcertRunner(AsyncToolRunner):
    name = "mkcert"

    def should_run(self) -> bool:
        cert_files = self._scan_files("*.pem", "*.crt", "*.cert", "*.key")
        if not cert_files:
            self.skip_reason = "no certificate files found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        cert_files = self._scan_files("*.pem", "*.crt", "*.cert")
        if not cert_files:
            return ToolResult(tool=self.name, status=ToolStatus.SKIPPED)

        findings: list[Finding] = []

        for cert_file in cert_files:
            try:
                rel_path = str(cert_file.relative_to(self.target))
            except ValueError:
                rel_path = str(cert_file)

            # Check if filename matches common dev cert patterns
            filename = cert_file.name.lower()
            is_dev_name = any(
                dev_name.lower() in filename
                for dev_name in _DEV_CERT_NAMES
            ) or "localhost" in filename

            # Read file contents and check for mkcert markers
            try:
                content_bytes = cert_file.read_bytes()
            except OSError:
                continue

            is_mkcert = any(
                indicator in content_bytes for indicator in _MKCERT_INDICATORS
            )

            # Also check text content
            if not is_mkcert:
                try:
                    content_text = content_bytes.decode("utf-8", errors="replace")
                    is_mkcert = any(
                        pat.search(content_text) for pat in _MKCERT_TEXT_PATTERNS
                    )
                except Exception:
                    pass

            if is_mkcert:
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.HIGH,
                    category=Category.SSL_TLS,
                    file=rel_path,
                    rule_id="mkcert-dev-cert",
                    rule_name="mkcert Development Certificate",
                    message=f"mkcert-generated development certificate found: {rel_path}",
                    blocks_deploy=True,
                    effort=Effort.LOW,
                    fix_hint=(
                        "Remove mkcert dev certificates from production. "
                        "Use a real CA certificate (e.g., Let's Encrypt) instead."
                    ),
                ))
            elif is_dev_name:
                # File has a dev-like name but no mkcert markers — still suspicious
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.MEDIUM,
                    category=Category.SSL_TLS,
                    file=rel_path,
                    rule_id="mkcert-dev-cert-name",
                    rule_name="Suspicious Dev Certificate Name",
                    message=f"Certificate file has development-style name: {rel_path}",
                    effort=Effort.LOW,
                    fix_hint="Verify this is a production-ready certificate, not a dev placeholder",
                ))

        # Check for mkcert CAROOT environment variable or rootCA files
        self._check_ca_root(findings)

        return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=findings)

    def _check_ca_root(self, findings: list[Finding]) -> None:
        """Check for mkcert CA root files in the project."""
        ca_files = self._scan_files("rootCA.pem", "rootCA-key.pem")
        for ca_file in ca_files:
            try:
                rel_path = str(ca_file.relative_to(self.target))
            except ValueError:
                rel_path = str(ca_file)

            # Check if it's an mkcert CA
            try:
                content = ca_file.read_bytes()
                if any(indicator in content for indicator in _MKCERT_INDICATORS):
                    findings.append(Finding(
                        tool=self.name,
                        severity=Severity.CRITICAL,
                        category=Category.SSL_TLS,
                        file=rel_path,
                        rule_id="mkcert-ca-root-in-project",
                        rule_name="mkcert CA Root in Project",
                        message=(
                            f"mkcert CA root file found in project: {rel_path}. "
                            "This is a private key that should never be committed."
                        ),
                        blocks_deploy=True,
                        effort=Effort.TRIVIAL,
                        fix_hint="Remove the CA root files and add them to .gitignore",
                        fix_command=f"rm {rel_path} && echo '{rel_path}' >> .gitignore",
                    ))
            except OSError:
                continue
