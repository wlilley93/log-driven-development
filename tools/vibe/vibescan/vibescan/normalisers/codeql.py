"""CodeQL normaliser — transforms SARIF output into normalised findings."""

from __future__ import annotations

from typing import Any

from vibescan.models import Category, Finding, Severity
from vibescan.normalisers.base import BaseNormaliser

# SARIF level → Severity
LEVEL_MAP = {
    "error": Severity.HIGH,
    "warning": Severity.MEDIUM,
    "note": Severity.LOW,
    "none": Severity.INFO,
}


class CodeqlNormaliser(BaseNormaliser):
    tool_name = "codeql"

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        findings: list[Finding] = []
        runs = raw_data.get("runs", [])

        for run in runs:
            if not isinstance(run, dict):
                continue

            # Build rule lookup
            rules: dict[str, dict] = {}
            tool_obj = run.get("tool", {})
            driver = tool_obj.get("driver", {})
            for rule in driver.get("rules", []):
                if isinstance(rule, dict):
                    rules[rule.get("id", "")] = rule

            for result in run.get("results", []):
                if not isinstance(result, dict):
                    continue

                rule_id = result.get("ruleId", "unknown")
                level = result.get("level", "warning")
                severity = LEVEL_MAP.get(level, Severity.MEDIUM)

                # Extract message
                message_obj = result.get("message", {})
                message = message_obj.get("text", "") if isinstance(message_obj, dict) else str(message_obj)

                # Extract location
                file_path = ""
                line = None
                col = None
                locations = result.get("locations", [])
                if locations and isinstance(locations[0], dict):
                    phys = locations[0].get("physicalLocation", {})
                    artifact = phys.get("artifactLocation", {})
                    file_path = artifact.get("uri", "")
                    region = phys.get("region", {})
                    raw_line = region.get("startLine")
                    line = int(raw_line) if raw_line is not None else None
                    raw_col = region.get("startColumn")
                    col = int(raw_col) if raw_col is not None else None

                # Rule metadata
                rule_meta = rules.get(rule_id, {})
                rule_name = rule_meta.get("name", rule_id)
                short_desc = rule_meta.get("shortDescription", {})
                if isinstance(short_desc, dict):
                    short_desc = short_desc.get("text", "")
                fix_hint = rule_meta.get("help", {})
                if isinstance(fix_hint, dict):
                    fix_hint = fix_hint.get("text", None)

                findings.append(
                    Finding(
                        tool=self.tool_name,
                        severity=severity,
                        category=Category.CODE,
                        file=file_path,
                        line=line,
                        col=col,
                        rule_id=rule_id,
                        rule_name=rule_name,
                        message=message or str(short_desc),
                        fix_hint=fix_hint,
                        raw=result,
                    )
                )

        return findings
