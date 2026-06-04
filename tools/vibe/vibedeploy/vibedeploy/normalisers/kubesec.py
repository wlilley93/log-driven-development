"""Normaliser for kubesec JSON output."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser


class KubesecNormaliser(BaseNormaliser):
    tool_name = "kubesec"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings = []
        file_path = raw_data.get("_file", "unknown")
        score = raw_data.get("score", 0)

        # Process critical findings
        for item in raw_data.get("scoring", {}).get("critical", []):
            selector = item.get("selector", "")
            reason = item.get("reason", "")
            rule_id = item.get("id", selector)
            findings.append(Finding(
                tool=self.tool_name,
                severity=Severity.CRITICAL,
                category=Category.KUBERNETES,
                file=file_path,
                rule_id=f"kubesec-critical-{rule_id}",
                rule_name=rule_id,
                message=reason or f"Critical security issue: {selector}",
                blocks_deploy=True,
                effort=Effort.MEDIUM,
                fix_hint=f"Fix selector: {selector}",
                raw=item,
            ))

        # Process advise findings (recommendations)
        for item in raw_data.get("scoring", {}).get("advise", []):
            selector = item.get("selector", "")
            reason = item.get("reason", "")
            rule_id = item.get("id", selector)
            findings.append(Finding(
                tool=self.tool_name,
                severity=Severity.MEDIUM,
                category=Category.KUBERNETES,
                file=file_path,
                rule_id=f"kubesec-advise-{rule_id}",
                rule_name=rule_id,
                message=reason or f"Security recommendation: {selector}",
                blocks_deploy=False,
                effort=Effort.LOW,
                fix_hint=f"Apply recommendation for selector: {selector}",
                raw=item,
            ))

        # If score is very low with no specific findings, add a summary finding
        if score < 0 and not findings:
            findings.append(Finding(
                tool=self.tool_name,
                severity=Severity.HIGH,
                category=Category.KUBERNETES,
                file=file_path,
                rule_id="kubesec-low-score",
                rule_name="Low Security Score",
                message=f"Kubesec score is {score} (negative score indicates security issues)",
                blocks_deploy=True,
                effort=Effort.MEDIUM,
                fix_hint="Review kubesec output and apply security best practices",
                raw={"score": score},
            ))

        return findings
