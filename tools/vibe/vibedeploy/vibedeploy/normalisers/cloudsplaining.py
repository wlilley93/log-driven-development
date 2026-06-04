"""Normaliser for cloudsplaining JSON output."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser

# Privilege escalation and data exfiltration are the most critical
_RISK_SEVERITY = {
    "PrivilegeEscalation": Severity.CRITICAL,
    "DataExfiltration": Severity.CRITICAL,
    "ResourceExposure": Severity.HIGH,
    "InfrastructureModification": Severity.HIGH,
    "ServiceWildcard": Severity.MEDIUM,
    "CredentialsExposure": Severity.CRITICAL,
}


class CloudsplainingNormaliser(BaseNormaliser):
    tool_name = "cloudsplaining"

    def normalise(self, raw_data: Any) -> list[Finding]:
        """Parse cloudsplaining results.

        Output format varies, but generally:
        {
          "roles": [...],
          "users": [...],
          "groups": [...],
          "policies": {
            "<policy_name>": {
              "PrivilegeEscalation": [...],
              "DataExfiltration": [...],
              "ResourceExposure": [...],
              "InfrastructureModification": [...],
              "ServiceWildcard": [...],
              "CredentialsExposure": [...]
            }
          }
        }

        Or a flat list of risk findings.
        """
        findings: list[Finding] = []

        if not isinstance(raw_data, dict):
            return findings

        # Handle policy-centric output
        policies = raw_data.get("policies", {})
        if isinstance(policies, dict):
            for policy_name, risks in policies.items():
                if not isinstance(risks, dict):
                    continue
                self._process_policy_risks(policy_name, risks, findings)

        # Handle principal-centric output (roles, users, groups)
        for principal_type in ("roles", "users", "groups"):
            principals = raw_data.get(principal_type, [])
            if isinstance(principals, list):
                for principal in principals:
                    if not isinstance(principal, dict):
                        continue
                    name = principal.get("name", principal.get("RoleName",
                           principal.get("UserName", principal.get("GroupName", "unknown"))))
                    risks = {k: v for k, v in principal.items()
                             if k in _RISK_SEVERITY and isinstance(v, list) and v}
                    if risks:
                        self._process_policy_risks(
                            f"{principal_type}/{name}", risks, findings
                        )

        # Handle flat findings list
        if "findings" in raw_data:
            for item in raw_data["findings"]:
                if isinstance(item, dict):
                    self._process_flat_finding(item, findings)

        return findings

    def _process_policy_risks(
        self, policy_name: str, risks: dict, findings: list[Finding]
    ) -> None:
        """Process risk categories for a single policy."""
        for risk_type, actions in risks.items():
            if not isinstance(actions, list) or not actions:
                continue

            severity = _RISK_SEVERITY.get(risk_type, Severity.MEDIUM)
            blocks = severity in (Severity.CRITICAL, Severity.HIGH)

            # Summarise actions
            action_list = []
            for action in actions[:10]:
                if isinstance(action, str):
                    action_list.append(action)
                elif isinstance(action, dict):
                    action_list.append(
                        action.get("action", action.get("Action", str(action)))
                    )

            actions_str = ", ".join(action_list)
            if len(actions) > 10:
                actions_str += f" (+{len(actions) - 10} more)"

            findings.append(Finding(
                tool=self.tool_name,
                severity=severity,
                category=Category.CLOUD,
                file=policy_name,
                rule_id=f"cloudsplaining-{risk_type.lower()}",
                rule_name=f"IAM {risk_type}",
                message=f"Policy {policy_name} allows {risk_type}: {actions_str}",
                blocks_deploy=blocks,
                effort=Effort.HIGH,
                fix_hint=f"Restrict IAM policy {policy_name} to remove {risk_type} permissions",
            ))

    def _process_flat_finding(self, item: dict, findings: list[Finding]) -> None:
        """Process a single flat finding object."""
        risk_type = item.get("type", item.get("risk_type", "unknown"))
        policy = item.get("policy", item.get("PolicyName", "unknown"))
        message = item.get("message", item.get("description", f"{risk_type} in {policy}"))

        severity = _RISK_SEVERITY.get(risk_type, Severity.MEDIUM)
        blocks = severity in (Severity.CRITICAL, Severity.HIGH)

        findings.append(Finding(
            tool=self.tool_name,
            severity=severity,
            category=Category.CLOUD,
            file=policy,
            rule_id=f"cloudsplaining-{risk_type.lower()}",
            rule_name=f"IAM {risk_type}",
            message=message,
            blocks_deploy=blocks,
            effort=Effort.HIGH,
            fix_hint=item.get("remediation", f"Review and restrict {risk_type} permissions"),
            raw=item,
        ))
