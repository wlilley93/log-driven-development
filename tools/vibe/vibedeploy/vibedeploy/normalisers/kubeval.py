"""Normaliser for kubeval JSON output."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser


class KubevalNormaliser(BaseNormaliser):
    tool_name = "kubeval"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings = []
        status = raw_data.get("status", "")
        filename = raw_data.get("filename", "unknown")
        kind = raw_data.get("kind", "unknown")
        errors = raw_data.get("errors", [])

        if status == "invalid":
            for error_msg in errors:
                if isinstance(error_msg, str):
                    message = error_msg
                elif isinstance(error_msg, dict):
                    message = error_msg.get("message", str(error_msg))
                else:
                    message = str(error_msg)

                findings.append(Finding(
                    tool=self.tool_name,
                    severity=Severity.HIGH,
                    category=Category.KUBERNETES,
                    file=filename,
                    rule_id=f"kubeval-invalid-{kind.lower()}",
                    rule_name=f"Invalid {kind}",
                    message=f"Invalid {kind} manifest: {message}",
                    blocks_deploy=True,
                    effort=Effort.LOW,
                    fix_hint=f"Fix the {kind} manifest to conform to the Kubernetes API schema",
                    raw=raw_data,
                ))

        elif status == "error":
            findings.append(Finding(
                tool=self.tool_name,
                severity=Severity.MEDIUM,
                category=Category.KUBERNETES,
                file=filename,
                rule_id="kubeval-error",
                rule_name="Validation Error",
                message=f"Could not validate {kind}: {'; '.join(str(e) for e in errors) if errors else 'unknown error'}",
                blocks_deploy=False,
                effort=Effort.LOW,
                fix_hint="Check if the resource uses a CRD or non-standard API version",
                raw=raw_data,
            ))

        return findings
