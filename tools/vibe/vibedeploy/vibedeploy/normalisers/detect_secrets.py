"""Normaliser for detect-secrets output."""

from __future__ import annotations
from typing import Any
from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser


class DetectSecretsNormaliser(BaseNormaliser):
    tool_name = "detect_secrets"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings = []
        results = raw_data.get("results", {})
        for filepath, secrets in results.items():
            for secret in secrets:
                findings.append(Finding(
                    tool=self.tool_name,
                    severity=Severity.CRITICAL,
                    category=Category.ENV_SECRETS,
                    file=filepath,
                    line=secret.get("line_number"),
                    rule_id=secret.get("type", "secret"),
                    rule_name=secret.get("type", "Secret Detected"),
                    message=f"Potential secret detected: {secret.get('type', 'unknown type')}",
                    blocks_deploy=True,
                    effort=Effort.LOW,
                    fix_hint="Remove secret from source and rotate credentials",
                ))
        return findings
