"""cosign runner — check for container image signing practices.

Checks Dockerfiles for base images and verifies whether cosign is set up
for image signing. Reports unsigned base image references and missing
signing configuration.
"""

from __future__ import annotations

import re
from pathlib import Path

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner

# Well-known registries that typically have signed images
_SIGNED_REGISTRIES = {
    "gcr.io",
    "ghcr.io",
    "docker.io/library",
    "registry.k8s.io",
    "quay.io",
    "mcr.microsoft.com",
    "public.ecr.aws",
}

# Base images commonly signed by publishers
_COMMONLY_SIGNED = {
    "node", "python", "golang", "rust", "ruby", "java", "openjdk",
    "alpine", "ubuntu", "debian", "fedora", "centos",
    "nginx", "redis", "postgres", "mysql", "mongo",
}


class CosignRunner(AsyncToolRunner):
    name = "cosign"
    requires_docker = True

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "cosign not installed"
            return False
        if not self._file_exists("Dockerfile", "docker-compose.yml", "docker-compose.yaml"):
            self.skip_reason = "no Dockerfile found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        dockerfiles = self._scan_files("Dockerfile", "Dockerfile.*", "*.Dockerfile")
        if not dockerfiles:
            return ToolResult(tool=self.name, status=ToolStatus.SKIPPED)

        all_findings: list[Finding] = []

        for dockerfile in dockerfiles:
            content = self._read_file(dockerfile)
            if not content:
                continue
            rel_path = str(dockerfile.relative_to(self.target))
            all_findings.extend(self._check_base_images(content, rel_path))

        # Check for cosign signing configuration in CI
        all_findings.extend(self._check_signing_config())

        return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=all_findings)

    def _check_base_images(self, content: str, file_path: str) -> list[Finding]:
        """Check base images referenced in FROM instructions."""
        findings: list[Finding] = []

        for i, line in enumerate(content.split("\n"), start=1):
            stripped = line.strip()
            if not stripped.upper().startswith("FROM "):
                continue

            # Parse the FROM instruction
            parts = stripped[5:].strip().split()
            if not parts:
                continue

            image_ref = parts[0]
            if image_ref.lower() == "scratch":
                continue

            # Check if the image is from a registry known to support signing
            is_from_signed_registry = any(
                image_ref.startswith(reg) for reg in _SIGNED_REGISTRIES
            )

            # Check if it's a commonly signed official image
            image_name = image_ref.split("/")[-1].split(":")[0].split("@")[0]
            is_commonly_signed = image_name.lower() in _COMMONLY_SIGNED

            # Check if using digest pinning (most secure)
            uses_digest = "@sha256:" in image_ref

            if uses_digest:
                # Good practice, no finding needed
                continue

            # Try to verify the image signature with cosign
            verified = False
            if is_from_signed_registry or is_commonly_signed:
                try:
                    result = self._exec(
                        [self.bin_path, "verify", "--certificate-identity-regexp", ".*", "--certificate-oidc-issuer-regexp", ".*", image_ref],
                        timeout=30,
                    )
                    verified = result.returncode == 0
                except Exception:
                    pass

            if not verified and not uses_digest:
                severity = Severity.LOW if is_commonly_signed else Severity.MEDIUM
                findings.append(Finding(
                    tool=self.name,
                    severity=severity,
                    category=Category.DOCKER,
                    file=file_path,
                    line=i,
                    rule_id="cosign-unsigned-base",
                    rule_name="Unsigned Base Image",
                    message=f"Base image '{image_ref}' is not verified with cosign and does not use digest pinning",
                    blocks_deploy=False,
                    effort=Effort.LOW,
                    fix_hint=f"Use digest pinning (e.g., {image_ref}@sha256:...) or verify the image with cosign",
                ))

        return findings

    def _check_signing_config(self) -> list[Finding]:
        """Check for cosign signing setup in CI/CD configuration."""
        findings: list[Finding] = []

        # Look for CI config files
        ci_files = (
            self._scan_files(".github/workflows/*.yml", ".github/workflows/*.yaml")
            + self._scan_files(".gitlab-ci.yml")
            + self._scan_files("Jenkinsfile")
            + self._scan_files(".circleci/config.yml")
        )

        has_signing_step = False
        for ci_file in ci_files:
            content = self._read_file(ci_file)
            if "cosign sign" in content or "cosign-installer" in content:
                has_signing_step = True
                break

        # Also check for cosign.key or cosign.pub
        has_cosign_key = self._file_exists("cosign.key", "cosign.pub")

        if not has_signing_step and not has_cosign_key and ci_files:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.INFO,
                category=Category.DOCKER,
                file="Dockerfile",
                rule_id="cosign-no-signing",
                rule_name="No Image Signing Configuration",
                message="No cosign image signing found in CI/CD pipelines. Signed images improve supply chain security.",
                blocks_deploy=False,
                effort=Effort.MEDIUM,
                fix_hint="Add cosign signing to your CI/CD pipeline to sign published container images",
                docs_url="https://docs.sigstore.dev/cosign/signing/signing_with_containers/",
            ))

        return findings
