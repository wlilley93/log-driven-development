"""Normaliser for syft SBOM JSON output."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser

# Package types that are more security-sensitive
_SENSITIVE_TYPES = {"deb", "rpm", "apk", "python", "npm", "gem", "java-archive"}

# Known problematic packages that should be flagged
_FLAGGED_PACKAGES = {
    "libssl1.0": "OpenSSL 1.0 is end-of-life",
    "python2": "Python 2 is end-of-life",
    "node8": "Node.js 8 is end-of-life",
    "node10": "Node.js 10 is end-of-life",
    "node12": "Node.js 12 is end-of-life",
    "node14": "Node.js 14 is end-of-life",
}


class SyftNormaliser(BaseNormaliser):
    tool_name = "syft"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings: list[Finding] = []

        if not isinstance(raw_data, dict):
            return findings

        artifacts = raw_data.get("artifacts", [])
        if not isinstance(artifacts, list):
            return findings

        source_info = raw_data.get("source", {})
        source_target = source_info.get("target", {}) if isinstance(source_info, dict) else {}
        image_ref = ""
        if isinstance(source_target, dict):
            image_ref = source_target.get("userInput", source_target.get("imageID", ""))
        elif isinstance(source_target, str):
            image_ref = source_target

        total_packages = len(artifacts)
        pkg_types: dict[str, int] = {}

        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue

            name = artifact.get("name", "unknown")
            version = artifact.get("version", "")
            pkg_type = artifact.get("type", "unknown")
            locations = artifact.get("locations", [])

            pkg_types[pkg_type] = pkg_types.get(pkg_type, 0) + 1

            # Check for known problematic packages
            name_lower = name.lower()
            for flagged, reason in _FLAGGED_PACKAGES.items():
                if flagged in name_lower:
                    file_path = "Dockerfile"
                    if locations and isinstance(locations[0], dict):
                        file_path = locations[0].get("path", "Dockerfile")

                    findings.append(Finding(
                        tool=self.tool_name,
                        severity=Severity.HIGH,
                        category=Category.DOCKER,
                        file=file_path,
                        rule_id=f"syft-eol-{flagged}",
                        rule_name=f"End-of-Life Package: {name}",
                        message=f"{name} {version}: {reason}",
                        blocks_deploy=False,
                        effort=Effort.MEDIUM,
                        fix_hint=f"Replace {name} with a supported version",
                        raw=artifact,
                    ))

            # Check for packages without version pinning
            if not version or version in ("0.0.0", "0", "latest"):
                file_path = "Dockerfile"
                if locations and isinstance(locations[0], dict):
                    file_path = locations[0].get("path", "Dockerfile")

                findings.append(Finding(
                    tool=self.tool_name,
                    severity=Severity.LOW,
                    category=Category.DOCKER,
                    file=file_path,
                    rule_id="syft-unversioned-pkg",
                    rule_name=f"Unversioned Package: {name}",
                    message=f"Package {name} has no version or uses a non-specific version ({version or 'none'})",
                    blocks_deploy=False,
                    effort=Effort.TRIVIAL,
                    fix_hint=f"Pin {name} to a specific version for reproducible builds",
                    raw=artifact,
                ))

        # Report high package count as informational
        if total_packages > 500:
            findings.append(Finding(
                tool=self.tool_name,
                severity=Severity.INFO,
                category=Category.DOCKER,
                file=image_ref or "Dockerfile",
                rule_id="syft-high-pkg-count",
                rule_name="High Package Count",
                message=(
                    f"Image contains {total_packages} packages across "
                    f"{len(pkg_types)} types. Consider using a minimal base image "
                    f"to reduce attack surface."
                ),
                blocks_deploy=False,
                effort=Effort.MEDIUM,
                fix_hint="Use a minimal base image (e.g., alpine, distroless) to reduce the number of installed packages",
                raw={"total": total_packages, "by_type": pkg_types},
            ))

        return findings
