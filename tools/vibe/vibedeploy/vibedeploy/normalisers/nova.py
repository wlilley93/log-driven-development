"""Normaliser for nova JSON output — outdated Helm chart detection."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser


class NovaNormaliser(BaseNormaliser):
    tool_name = "nova"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings = []

        # nova output: { "releases": [...] } or { "helm_releases": [...] }
        releases = raw_data.get("releases", [])
        if not releases:
            releases = raw_data.get("helm_releases", [])

        if not isinstance(releases, list):
            return findings

        for release in releases:
            name = release.get("release", release.get("name", "unknown"))
            chart_name = release.get("chartName", name)
            namespace = release.get("namespace", "default")
            installed = release.get("Installed", release.get("installed", {})
            )
            latest = release.get("Latest", release.get("latest", {}))
            outdated = release.get("outdated", release.get("IsOld", False))
            deprecated = release.get("deprecated", False)

            # Extract version strings
            if isinstance(installed, dict):
                installed_version = installed.get("version", "unknown")
            else:
                installed_version = str(installed) if installed else "unknown"

            if isinstance(latest, dict):
                latest_version = latest.get("version", "unknown")
            else:
                latest_version = str(latest) if latest else "unknown"

            if not outdated and not deprecated:
                continue

            resource_id = f"{namespace}/{chart_name}"

            if deprecated:
                findings.append(Finding(
                    tool=self.tool_name,
                    severity=Severity.HIGH,
                    category=Category.KUBERNETES,
                    file=resource_id,
                    rule_id=f"nova-deprecated-{chart_name}",
                    rule_name=f"Deprecated Chart: {chart_name}",
                    message=f"Helm chart '{chart_name}' (release '{name}') is deprecated",
                    blocks_deploy=False,
                    effort=Effort.HIGH,
                    fix_hint=f"Find a replacement for deprecated chart '{chart_name}'",
                    raw=release,
                ))

            if outdated:
                # Determine severity based on version gap
                severity = Severity.MEDIUM
                if installed_version != "unknown" and latest_version != "unknown":
                    # Major version bump = higher severity
                    try:
                        installed_major = int(installed_version.split(".")[0])
                        latest_major = int(latest_version.split(".")[0])
                        if latest_major - installed_major >= 2:
                            severity = Severity.HIGH
                    except (ValueError, IndexError):
                        pass

                findings.append(Finding(
                    tool=self.tool_name,
                    severity=severity,
                    category=Category.KUBERNETES,
                    file=resource_id,
                    rule_id=f"nova-outdated-{chart_name}",
                    rule_name=f"Outdated Chart: {chart_name}",
                    message=(
                        f"Helm chart '{chart_name}' (release '{name}') "
                        f"is outdated: {installed_version} -> {latest_version}"
                    ),
                    blocks_deploy=False,
                    effort=Effort.MEDIUM,
                    fix_hint=f"helm upgrade {name} {chart_name} --version {latest_version}",
                    raw=release,
                ))

        return findings
