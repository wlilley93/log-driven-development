"""Normaliser for ScoutSuite JSON output."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser

_LEVEL_MAP = {
    "danger": Severity.CRITICAL,
    "warning": Severity.HIGH,
    "caution": Severity.MEDIUM,
    "good": Severity.INFO,
}


class ScoutSuiteNormaliser(BaseNormaliser):
    tool_name = "scoutsuite"

    def normalise(self, raw_data: Any) -> list[Finding]:
        """Parse ScoutSuite results JSON.

        The results object contains a nested structure:
        {
          "services": {
            "<service_name>": {
              "findings": {
                "<finding_key>": {
                  "level": "danger" | "warning" | ...,
                  "description": "...",
                  "rationale": "...",
                  "remediation": "...",
                  "service": "...",
                  "flagged_items": 5,
                  "items": ["item1", "item2", ...],
                }
              }
            }
          }
        }
        """
        findings: list[Finding] = []

        if not isinstance(raw_data, dict):
            return findings

        services = raw_data.get("services", {})
        if not isinstance(services, dict):
            return findings

        for service_name, service_data in services.items():
            if not isinstance(service_data, dict):
                continue

            service_findings = service_data.get("findings", {})
            if not isinstance(service_findings, dict):
                continue

            for finding_key, finding_data in service_findings.items():
                if not isinstance(finding_data, dict):
                    continue

                level = finding_data.get("level", "warning")
                # Skip non-issues
                if level in ("good",):
                    continue

                severity = _LEVEL_MAP.get(level, Severity.MEDIUM)
                description = finding_data.get("description", finding_key)
                rationale = finding_data.get("rationale", "")
                remediation = finding_data.get("remediation", None)
                flagged_items = finding_data.get("flagged_items", 0)
                items = finding_data.get("items", [])

                if flagged_items == 0 and not items:
                    continue

                blocks = severity in (Severity.CRITICAL, Severity.HIGH)
                message = description
                if rationale:
                    message = f"{description} — {rationale}"
                if flagged_items:
                    message = f"{message} ({flagged_items} resources affected)"

                # Report one finding per flagged item for granularity, or one aggregate
                if items and len(items) <= 20:
                    for item in items:
                        item_str = item if isinstance(item, str) else str(item)
                        findings.append(Finding(
                            tool=self.tool_name,
                            severity=severity,
                            category=Category.CLOUD,
                            file=f"{service_name}/{item_str}",
                            rule_id=finding_key,
                            rule_name=description,
                            message=f"{description}: {item_str}",
                            blocks_deploy=blocks,
                            effort=Effort.MEDIUM,
                            fix_hint=remediation,
                            raw=finding_data,
                        ))
                else:
                    findings.append(Finding(
                        tool=self.tool_name,
                        severity=severity,
                        category=Category.CLOUD,
                        file=f"{service_name}",
                        rule_id=finding_key,
                        rule_name=description,
                        message=message,
                        blocks_deploy=blocks,
                        effort=Effort.MEDIUM,
                        fix_hint=remediation,
                        raw=finding_data,
                    ))

        return findings
