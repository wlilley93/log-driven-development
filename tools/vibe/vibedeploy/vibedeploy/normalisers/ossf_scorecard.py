"""Normaliser for OSSF Scorecard JSON output."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser

# Scorecard checks and their severity thresholds
# Score is 0-10, higher is better. Low scores are concerning.
CRITICAL_THRESHOLD = 3
HIGH_THRESHOLD = 5
MEDIUM_THRESHOLD = 7


class OssfScorecardNormaliser(BaseNormaliser):
    tool_name = "ossf_scorecard"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings: list[Finding] = []

        checks = raw_data.get("checks", [])
        repo = raw_data.get("repo", {}).get("name", "unknown")
        aggregate_score = raw_data.get("score", None)

        for check in checks:
            check_name = check.get("name", "unknown")
            score = check.get("score", -1)
            reason = check.get("reason", "")
            documentation = check.get("documentation", {})
            docs_url = documentation.get("url", None)

            # Skip checks that passed well (score >= 8)
            if score >= 8:
                continue

            # Skip checks that returned -1 (not applicable)
            if score < 0:
                continue

            severity = self._score_to_severity(score)
            rule_id = f"scorecard-{check_name.lower().replace(' ', '-')}"

            findings.append(Finding(
                tool=self.tool_name,
                severity=severity,
                category=Category.SUPPLY_CHAIN,
                file=".",
                rule_id=rule_id,
                rule_name=f"Scorecard: {check_name}",
                message=f"{check_name} scored {score}/10: {reason}",
                docs_url=docs_url,
                effort=self._check_effort(check_name),
                blocks_deploy=severity in (Severity.CRITICAL,),
                raw=check,
            ))

        # Overall score finding if low
        if aggregate_score is not None and aggregate_score < MEDIUM_THRESHOLD:
            severity = self._score_to_severity(aggregate_score)
            findings.append(Finding(
                tool=self.tool_name,
                severity=severity,
                category=Category.SUPPLY_CHAIN,
                file=".",
                rule_id="scorecard-aggregate",
                rule_name="OSSF Scorecard Aggregate Score",
                message=f"Repository aggregate security score is {aggregate_score}/10",
                effort=Effort.HIGH,
                blocks_deploy=False,
                docs_url="https://securityscorecards.dev/",
            ))

        return findings

    @staticmethod
    def _score_to_severity(score: int | float) -> Severity:
        if score <= CRITICAL_THRESHOLD:
            return Severity.CRITICAL
        if score <= HIGH_THRESHOLD:
            return Severity.HIGH
        if score <= MEDIUM_THRESHOLD:
            return Severity.MEDIUM
        return Severity.LOW

    @staticmethod
    def _check_effort(check_name: str) -> Effort:
        """Estimate effort based on the check type."""
        low_effort = {
            "License", "Security-Policy", "SAST", "Token-Permissions",
            "Binary-Artifacts", "Pinned-Dependencies",
        }
        medium_effort = {
            "Branch-Protection", "Code-Review", "CI-Tests",
            "Dependency-Update-Tool", "Fuzzing", "Packaging",
        }
        if check_name in low_effort:
            return Effort.LOW
        if check_name in medium_effort:
            return Effort.MEDIUM
        return Effort.HIGH
