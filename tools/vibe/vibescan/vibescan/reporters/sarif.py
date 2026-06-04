"""SARIF 2.1.0 reporter — OASIS standard for static analysis results."""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console

from vibescan.config import Config
from vibescan.models import Finding, ScanResult, Severity, ToolStatus
from vibescan.reporters.base import BaseReporter

_SARIF_SCHEMA = (
    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/"
    "sarif-2.1/schema/sarif-schema-2.1.0.json"
)

_SEVERITY_TO_LEVEL: dict[Severity, str] = {
    Severity.CRITICAL: "error",
    Severity.HIGH: "error",
    Severity.MEDIUM: "warning",
    Severity.LOW: "note",
    Severity.INFO: "note",
}

_STATUS_TO_SARIF: dict[ToolStatus, str] = {
    ToolStatus.SUCCESS: "success",
    ToolStatus.PARTIAL: "notApplicable",
    ToolStatus.FAILED: "failure",
    ToolStatus.SKIPPED: "notApplicable",
    ToolStatus.TIMEOUT: "failure",
}


def _build_region(finding: Finding) -> dict[str, Any] | None:
    """Build a SARIF region object from line/col info."""
    if finding.line is None:
        return None
    region: dict[str, Any] = {"startLine": finding.line}
    if finding.col is not None:
        region["startColumn"] = finding.col
    return region


def _build_rule(finding: Finding) -> dict[str, Any]:
    """Build a SARIF reportingDescriptor (rule) from a finding."""
    rule: dict[str, Any] = {
        "id": finding.rule_id,
        "name": finding.rule_name,
        "shortDescription": {"text": finding.rule_name},
    }

    # Default configuration with severity level
    level = _SEVERITY_TO_LEVEL.get(finding.severity, "note")
    rule["defaultConfiguration"] = {"level": level}

    # Help text from fix_hint
    if finding.fix_hint:
        rule["help"] = {"text": finding.fix_hint}

    # Properties for extra metadata
    props: dict[str, Any] = {"severity": finding.severity.value}
    if finding.cve:
        props["cve"] = finding.cve
    if finding.cvss is not None:
        props["cvss"] = finding.cvss
    if finding.category:
        props["category"] = finding.category.value
    rule["properties"] = props

    return rule


def _build_result(finding: Finding) -> dict[str, Any]:
    """Build a SARIF result object from a finding."""
    level = _SEVERITY_TO_LEVEL.get(finding.severity, "note")

    location: dict[str, Any] = {
        "physicalLocation": {
            "artifactLocation": {"uri": finding.file},
        }
    }
    region = _build_region(finding)
    if region:
        location["physicalLocation"]["region"] = region

    result: dict[str, Any] = {
        "ruleId": finding.rule_id,
        "level": level,
        "message": {"text": finding.message},
        "locations": [location],
    }

    # Fingerprint for deduplication
    result["fingerprints"] = {"vibescan/finding/v1": finding.id}

    # Properties bag
    props: dict[str, Any] = {
        "severity": finding.severity.value,
        "category": finding.category.value if finding.category else None,
    }
    if finding.cve:
        props["cve"] = finding.cve
    if finding.cvss is not None:
        props["cvss"] = finding.cvss
    if finding.licence:
        props["licence"] = finding.licence
    if finding.fix_hint:
        props["fixHint"] = finding.fix_hint
    if finding.tools:
        props["alsoFoundBy"] = finding.tools

    result["properties"] = props
    return result


class SarifReporter(BaseReporter):
    """SARIF 2.1.0 JSON output, one run per tool."""

    def __init__(self, result: ScanResult, config: Config):
        super().__init__(result, config)

    def render(self, console: Console) -> None:
        console.print_json(self.render_to_string())

    def render_to_string(self) -> str:
        return json.dumps(self._build_sarif(), indent=2, default=str)

    def _build_sarif(self) -> dict[str, Any]:
        sarif: dict[str, Any] = {
            "$schema": _SARIF_SCHEMA,
            "version": "2.1.0",
            "runs": [],
        }

        # Group deduplicated findings by tool
        findings_by_tool: dict[str, list[Finding]] = {}
        for f in self.result.deduplicated_findings:
            findings_by_tool.setdefault(f.tool, []).append(f)

        # Create a run for each tool that was executed
        for tr in self.result.tool_results:
            tool_findings = findings_by_tool.get(tr.tool, [])
            run = self._build_run(tr.tool, tr, tool_findings)
            sarif["runs"].append(run)

        return sarif

    def _build_run(
        self,
        tool_name: str,
        tool_result: Any,
        findings: list[Finding],
    ) -> dict[str, Any]:
        # Collect unique rules
        seen_rules: dict[str, dict[str, Any]] = {}
        for f in findings:
            if f.rule_id not in seen_rules:
                seen_rules[f.rule_id] = _build_rule(f)

        run: dict[str, Any] = {
            "tool": {
                "driver": {
                    "name": tool_name,
                    "rules": list(seen_rules.values()),
                },
            },
            "results": [_build_result(f) for f in findings],
        }

        # Add version if available
        if tool_result.version:
            run["tool"]["driver"]["version"] = tool_result.version

        # Invocations array with execution status
        invocation: dict[str, Any] = {
            "executionSuccessful": tool_result.status in (
                ToolStatus.SUCCESS,
                ToolStatus.PARTIAL,
            ),
        }
        sarif_status = _STATUS_TO_SARIF.get(tool_result.status)
        if sarif_status:
            invocation["exitCode"] = 0 if sarif_status == "success" else 1

        if tool_result.error:
            invocation["toolExecutionNotifications"] = [
                {
                    "level": "error",
                    "message": {"text": tool_result.error},
                }
            ]

        run["invocations"] = [invocation]

        return run
