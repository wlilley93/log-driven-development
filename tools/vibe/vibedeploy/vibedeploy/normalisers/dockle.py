"""Normaliser for dockle JSON output."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser

_LEVEL_MAP = {
    "FATAL": Severity.CRITICAL,
    "WARN": Severity.HIGH,
    "INFO": Severity.MEDIUM,
    "SKIP": Severity.INFO,
    "PASS": Severity.INFO,
}


class DockleNormaliser(BaseNormaliser):
    tool_name = "dockle"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings: list[Finding] = []

        if not isinstance(raw_data, dict):
            return findings

        details = raw_data.get("details", [])
        if not isinstance(details, list):
            return findings

        for detail in details:
            code = detail.get("code", "UNKNOWN")
            title = detail.get("title", "")
            level = detail.get("level", "INFO")
            alerts = detail.get("alerts", [])

            severity = _LEVEL_MAP.get(level, Severity.MEDIUM)
            blocks = severity == Severity.CRITICAL

            effort = Effort.LOW
            if severity <= Severity.LOW:
                effort = Effort.TRIVIAL

            if not alerts:
                # Even rules with no specific alerts are worth reporting
                findings.append(Finding(
                    tool=self.tool_name,
                    severity=severity,
                    category=Category.DOCKER,
                    file="Dockerfile",
                    rule_id=code,
                    rule_name=title or code,
                    message=title or f"Dockle check {code}",
                    blocks_deploy=blocks,
                    effort=effort,
                    raw=detail,
                ))
            else:
                for alert in alerts:
                    alert_msg = alert if isinstance(alert, str) else str(alert)
                    findings.append(Finding(
                        tool=self.tool_name,
                        severity=severity,
                        category=Category.DOCKER,
                        file="Dockerfile",
                        rule_id=code,
                        rule_name=title or code,
                        message=f"{title}: {alert_msg}" if title else alert_msg,
                        blocks_deploy=blocks,
                        effort=effort,
                        raw=detail,
                    ))

        return findings
