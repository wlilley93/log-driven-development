"""Normaliser for popeye JSON output."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser


# Popeye uses level 1-4: ok, info, warn, error
_POPEYE_LEVEL_SEVERITY = {
    0: Severity.INFO,     # ok
    1: Severity.INFO,     # info
    2: Severity.MEDIUM,   # warn
    3: Severity.HIGH,     # error
}


class PopeyeNormaliser(BaseNormaliser):
    tool_name = "popeye"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings = []

        # Popeye JSON structure: { "popeye": { "sanitizers": [...] } }
        popeye_data = raw_data.get("popeye", raw_data)
        sanitizers = popeye_data.get("sanitizers", [])

        for sanitizer in sanitizers:
            sanitizer_name = sanitizer.get("sanitizer", "unknown")
            issues_list = sanitizer.get("issues", {})

            # issues is a dict keyed by resource name
            if isinstance(issues_list, dict):
                for resource_name, issues in issues_list.items():
                    if not isinstance(issues, list):
                        continue
                    for issue in issues:
                        level = issue.get("level", 1)
                        message = issue.get("message", "")
                        group = issue.get("group", "")

                        # Skip ok/info level issues
                        if level < 2:
                            continue

                        severity = _POPEYE_LEVEL_SEVERITY.get(level, Severity.MEDIUM)
                        blocks = level >= 3

                        findings.append(Finding(
                            tool=self.tool_name,
                            severity=severity,
                            category=Category.KUBERNETES,
                            file=f"{sanitizer_name}/{resource_name}",
                            rule_id=f"popeye-{sanitizer_name}-L{level}",
                            rule_name=f"{sanitizer_name} Issue",
                            message=f"[{resource_name}] {message}",
                            blocks_deploy=blocks,
                            effort=Effort.LOW,
                            fix_hint=f"Address {sanitizer_name} issue for {resource_name}",
                            raw={"sanitizer": sanitizer_name, "resource": resource_name, "issue": issue},
                        ))

        return findings
