"""Normaliser for prowler JSON output."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser

_STATUS_SEVERITY = {
    "FAIL": Severity.HIGH,
    "WARNING": Severity.MEDIUM,
    "INFO": Severity.INFO,
    "PASS": Severity.INFO,
}

# Prowler severity text mapping
_PROWLER_SEVERITY = {
    "critical": Severity.CRITICAL,
    "high": Severity.HIGH,
    "medium": Severity.MEDIUM,
    "low": Severity.LOW,
    "informational": Severity.INFO,
}


class ProwlerNormaliser(BaseNormaliser):
    tool_name = "prowler"

    def normalise(self, raw_data: Any) -> list[Finding]:
        """Normalise a single prowler check result.

        Prowler outputs one JSON object per check. Each object includes:
        - StatusExtended / Status: PASS, FAIL, WARNING, INFO
        - CheckID: e.g. "check11"
        - CheckTitle: human-readable name
        - ServiceName: AWS service
        - Severity: critical, high, medium, low, informational
        - ResourceId / ResourceArn
        - Region
        - Remediation.Recommendation.Text / Url
        """
        findings: list[Finding] = []

        if not isinstance(raw_data, dict):
            return findings

        status = raw_data.get("Status", raw_data.get("status", ""))
        # Only report failures and warnings
        if status.upper() in ("PASS", "INFO"):
            return findings

        check_id = raw_data.get("CheckID", raw_data.get("check_id", "unknown"))
        check_title = raw_data.get("CheckTitle", raw_data.get("check_title", check_id))
        service = raw_data.get("ServiceName", raw_data.get("service_name", "unknown"))
        resource_id = raw_data.get("ResourceId", raw_data.get("resource_id", ""))
        resource_arn = raw_data.get("ResourceArn", raw_data.get("resource_arn", ""))
        region = raw_data.get("Region", raw_data.get("region", ""))
        status_extended = raw_data.get("StatusExtended", raw_data.get("status_extended", ""))

        # Severity from prowler's own field or from status
        sev_text = raw_data.get("Severity", raw_data.get("severity", "")).lower()
        severity = _PROWLER_SEVERITY.get(sev_text, _STATUS_SEVERITY.get(status.upper(), Severity.MEDIUM))

        # Remediation
        remediation = raw_data.get("Remediation", raw_data.get("remediation", {}))
        recommendation = remediation.get("Recommendation", remediation.get("recommendation", {}))
        if isinstance(recommendation, dict):
            fix_hint = recommendation.get("Text", recommendation.get("text"))
            docs_url = recommendation.get("Url", recommendation.get("url"))
        else:
            fix_hint = str(recommendation) if recommendation else None
            docs_url = None

        # File context: use resource ARN or resource ID
        file_context = resource_arn or resource_id or f"{service}/{region}"

        blocks = severity in (Severity.CRITICAL, Severity.HIGH)

        findings.append(Finding(
            tool=self.tool_name,
            severity=severity,
            category=Category.CLOUD,
            file=file_context,
            rule_id=check_id,
            rule_name=check_title,
            message=status_extended or f"{check_title} ({status})",
            blocks_deploy=blocks,
            effort=Effort.MEDIUM,
            fix_hint=fix_hint,
            docs_url=docs_url,
            raw=raw_data,
        ))

        return findings
