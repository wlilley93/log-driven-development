"""Normaliser for polaris audit JSON output."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser


# Map polaris severity strings to our severity enum
_POLARIS_SEVERITY = {
    "danger": Severity.HIGH,
    "warning": Severity.MEDIUM,
    "ignore": Severity.INFO,
}


class PolarisNormaliser(BaseNormaliser):
    tool_name = "polaris"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings = []

        # Polaris audit output has Results keyed by namespace/resource
        results = raw_data.get("Results", [])
        if isinstance(results, dict):
            results = list(results.values())

        for result in results:
            name = result.get("Name", "unknown")
            namespace = result.get("Namespace", "")
            kind = result.get("Kind", "unknown")
            pod_result = result.get("PodResult", {})
            file_path = result.get("CreatedTime", "")

            # Build a readable file identifier
            resource_id = f"{namespace}/{kind}/{name}" if namespace else f"{kind}/{name}"

            # Check container-level results
            container_results = pod_result.get("ContainerResults", [])
            for container in container_results:
                container_name = container.get("Name", "unknown")
                check_results = container.get("Results", {})
                for check_id, check in check_results.items():
                    success = check.get("Success", True)
                    if success:
                        continue

                    severity_str = check.get("Severity", "warning")
                    polaris_category = check.get("Category", "")
                    message = check.get("Message", f"Failed check: {check_id}")

                    severity = _POLARIS_SEVERITY.get(severity_str, Severity.MEDIUM)
                    blocks = severity >= Severity.HIGH

                    findings.append(Finding(
                        tool=self.tool_name,
                        severity=severity,
                        category=Category.KUBERNETES,
                        file=resource_id,
                        rule_id=f"polaris-{check_id}",
                        rule_name=check_id,
                        message=f"[{container_name}] {message}",
                        blocks_deploy=blocks,
                        effort=Effort.LOW,
                        fix_hint=f"Fix {check_id} for container '{container_name}' in {resource_id}",
                        raw={"check": check, "resource": resource_id, "category": polaris_category},
                    ))

            # Check pod-level results
            pod_checks = pod_result.get("Results", {})
            for check_id, check in pod_checks.items():
                success = check.get("Success", True)
                if success:
                    continue

                severity_str = check.get("Severity", "warning")
                message = check.get("Message", f"Failed check: {check_id}")
                severity = _POLARIS_SEVERITY.get(severity_str, Severity.MEDIUM)
                blocks = severity >= Severity.HIGH

                findings.append(Finding(
                    tool=self.tool_name,
                    severity=severity,
                    category=Category.KUBERNETES,
                    file=resource_id,
                    rule_id=f"polaris-{check_id}",
                    rule_name=check_id,
                    message=message,
                    blocks_deploy=blocks,
                    effort=Effort.LOW,
                    fix_hint=f"Fix {check_id} in {resource_id}",
                    raw={"check": check, "resource": resource_id},
                ))

        return findings
