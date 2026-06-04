"""Normaliser for pluto JSON output — deprecated/removed Kubernetes APIs."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser


class PlutoNormaliser(BaseNormaliser):
    tool_name = "pluto"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings = []

        # pluto output can be { "items": [...] } or a bare list
        items = raw_data
        if isinstance(raw_data, dict):
            items = raw_data.get("items", [])

        if not isinstance(items, list):
            return findings

        for item in items:
            name = item.get("name", "unknown")
            api_version = item.get("api", {})
            file_path = item.get("filePath", name)

            # Extract API version details
            if isinstance(api_version, dict):
                version = api_version.get("version", "unknown")
                kind = api_version.get("kind", "unknown")
                removed = api_version.get("removed", False)
                deprecated = api_version.get("deprecated", False)
                removed_in = api_version.get("removedIn", "")
                replacement_api = api_version.get("replacementApi", "")
            else:
                version = str(api_version)
                kind = item.get("kind", "unknown")
                removed = item.get("removed", False)
                deprecated = item.get("deprecated", False)
                removed_in = item.get("removedIn", "")
                replacement_api = item.get("replacementApi", "")

            # Removed APIs are critical and block deploy
            if removed:
                severity = Severity.CRITICAL
                blocks = True
                message = (
                    f"Removed API version {version} used by {kind}/{name}"
                    f"{f' (removed in {removed_in})' if removed_in else ''}"
                )
                fix_hint = (
                    f"Migrate {kind}/{name} to {replacement_api}"
                    if replacement_api
                    else f"Migrate {kind}/{name} to a supported API version"
                )
            elif deprecated:
                severity = Severity.HIGH
                blocks = False
                message = (
                    f"Deprecated API version {version} used by {kind}/{name}"
                    f"{f' (will be removed in {removed_in})' if removed_in else ''}"
                )
                fix_hint = (
                    f"Migrate {kind}/{name} to {replacement_api}"
                    if replacement_api
                    else f"Migrate {kind}/{name} to the latest API version"
                )
            else:
                continue

            findings.append(Finding(
                tool=self.tool_name,
                severity=severity,
                category=Category.KUBERNETES,
                file=file_path,
                rule_id=f"pluto-{'removed' if removed else 'deprecated'}-{kind.lower()}",
                rule_name=f"{'Removed' if removed else 'Deprecated'} API: {kind}",
                message=message,
                blocks_deploy=blocks,
                effort=Effort.MEDIUM,
                fix_hint=fix_hint,
                raw=item,
            ))

        return findings
