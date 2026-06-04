"""Normaliser for steampipe check JSON output."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser

_STATUS_MAP = {
    "alarm": Severity.CRITICAL,
    "error": Severity.HIGH,
    "ok": Severity.INFO,
    "info": Severity.INFO,
    "skip": Severity.INFO,
}


class SteampipeNormaliser(BaseNormaliser):
    tool_name = "steampipe"

    def normalise(self, raw_data: Any) -> list[Finding]:
        """Parse steampipe check JSON output.

        Steampipe check output structure:
        {
          "groups": [...],
          "summary": {...},
          "controls": [
            {
              "control_id": "...",
              "title": "...",
              "description": "...",
              "status": "alarm" | "ok" | "error" | "skip" | "info",
              "severity": "critical" | "high" | "medium" | "low",
              "resource": "...",
              "reason": "...",
              "results": [...]
            }
          ]
        }
        """
        findings: list[Finding] = []

        if not isinstance(raw_data, dict):
            return findings

        # steampipe can nest groups → controls → results
        self._extract_from_group(raw_data, findings)

        return findings

    def _extract_from_group(self, group: dict, findings: list[Finding]) -> None:
        """Recursively extract findings from steampipe group/control hierarchy."""
        # Process nested groups
        for sub_group in group.get("groups", []):
            if isinstance(sub_group, dict):
                self._extract_from_group(sub_group, findings)

        # Process controls at this level
        for control in group.get("controls", []):
            if not isinstance(control, dict):
                continue
            self._process_control(control, findings)

        # Also handle top-level results (flat format)
        for result in group.get("results", []):
            if isinstance(result, dict):
                self._process_result(result, group, findings)

    def _process_control(self, control: dict, findings: list[Finding]) -> None:
        """Process a single control with its results."""
        control_id = control.get("control_id", control.get("name", "unknown"))
        title = control.get("title", control_id)
        description = control.get("description", "")

        results = control.get("results", [])
        if not results:
            # Control-level status
            status = control.get("status", "ok")
            if status.lower() in ("ok", "skip"):
                return
            severity = _STATUS_MAP.get(status.lower(), Severity.MEDIUM)
            sev_override = control.get("severity", "")
            if sev_override:
                severity = self.text_severity(sev_override)

            findings.append(Finding(
                tool=self.tool_name,
                severity=severity,
                category=Category.CLOUD,
                file=control.get("resource", control_id),
                rule_id=control_id,
                rule_name=title,
                message=description or f"{title} — {status}",
                blocks_deploy=severity in (Severity.CRITICAL, Severity.HIGH),
                effort=Effort.MEDIUM,
                raw=control,
            ))
            return

        for result in results:
            if isinstance(result, dict):
                self._process_result(result, control, findings)

    def _process_result(self, result: dict, control: dict, findings: list[Finding]) -> None:
        """Process a single steampipe check result."""
        status = result.get("status", "ok")
        if status.lower() in ("ok", "skip"):
            return

        control_id = control.get("control_id", control.get("name", "unknown"))
        title = control.get("title", control_id)
        resource = result.get("resource", control.get("resource", control_id))
        reason = result.get("reason", result.get("status_reason", ""))

        severity = _STATUS_MAP.get(status.lower(), Severity.MEDIUM)
        sev_override = control.get("severity", result.get("severity", ""))
        if sev_override:
            severity = self.text_severity(sev_override)

        findings.append(Finding(
            tool=self.tool_name,
            severity=severity,
            category=Category.CLOUD,
            file=resource,
            rule_id=control_id,
            rule_name=title,
            message=reason or f"{title} — {status}",
            blocks_deploy=severity in (Severity.CRITICAL, Severity.HIGH),
            effort=Effort.MEDIUM,
            raw=result,
        ))
