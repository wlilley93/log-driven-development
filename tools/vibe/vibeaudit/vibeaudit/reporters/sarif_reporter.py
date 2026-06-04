"""SARIF 2.1.0 reporter for integration with GitHub Code Scanning and other tools."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console

from vibeaudit.models import Finding, ScanResult, Severity, VULN_CLASS_LABELS
from vibeaudit.reporters.base import Reporter

_SARIF_SCHEMA = "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json"

# Map vibeaudit severity to SARIF level
_SEVERITY_TO_LEVEL: dict[Severity, str] = {
    Severity.CRITICAL: "error",
    Severity.HIGH: "error",
    Severity.MEDIUM: "warning",
    Severity.LOW: "note",
    Severity.INFO: "note",
}


class SarifReporter(Reporter):
    """Outputs scan results in SARIF 2.1.0 format."""

    def report(self, result: ScanResult, console: Console, output_path: Path | None = None) -> None:
        sarif = self._build_sarif(result)
        json_str = json.dumps(sarif, indent=2, ensure_ascii=False)

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json_str, encoding="utf-8")
            console.print(f"[green]SARIF report written to {output_path}[/green]")
        else:
            console.print(json_str, highlight=False)

    def _build_sarif(self, result: ScanResult) -> dict:
        """Build a complete SARIF 2.1.0 document."""
        rules = self._build_rules(result.findings)
        results = self._build_results(result.findings)

        tool_driver: dict = {
            "name": "vibeaudit",
            "version": "0.1.0",
            "informationUri": "https://github.com/vibeaudit/vibeaudit",
            "rules": rules,
        }

        run: dict = {
            "tool": {"driver": tool_driver},
            "results": results,
        }

        # Add invocation metadata
        if result.provider or result.model:
            run["properties"] = {}
            if result.provider:
                run["properties"]["provider"] = result.provider
            if result.model:
                run["properties"]["model"] = result.model
            if result.total_tokens > 0:
                run["properties"]["totalTokens"] = result.total_tokens
            if result.total_cost_usd > 0:
                run["properties"]["totalCostUsd"] = round(result.total_cost_usd, 4)
            if result.duration_seconds > 0:
                run["properties"]["durationSeconds"] = round(result.duration_seconds, 2)

        return {
            "$schema": _SARIF_SCHEMA,
            "version": "2.1.0",
            "runs": [run],
        }

    def _build_rules(self, findings: list[Finding]) -> list[dict]:
        """Build SARIF rule definitions from unique vuln classes in findings."""
        seen: set[str] = set()
        rules: list[dict] = []

        for finding in findings:
            rule_id = f"vibeaudit/{finding.vuln_class.value}"
            if rule_id in seen:
                continue
            seen.add(rule_id)

            label = VULN_CLASS_LABELS.get(finding.vuln_class, finding.vuln_class.value)

            rule: dict = {
                "id": rule_id,
                "name": finding.vuln_class.value,
                "shortDescription": {"text": label},
                "fullDescription": {"text": f"Detects {label.lower()} vulnerabilities."},
                "defaultConfiguration": {
                    "level": _SEVERITY_TO_LEVEL.get(finding.severity, "warning"),
                },
                "properties": {
                    "tags": ["security"],
                },
            }

            if finding.cwe_id:
                rule["properties"]["cwe"] = finding.cwe_id
            if finding.owasp_category:
                rule["properties"]["owasp"] = finding.owasp_category

            rules.append(rule)

        return rules

    def _build_results(self, findings: list[Finding]) -> list[dict]:
        """Build SARIF result objects from findings."""
        results: list[dict] = []

        for finding in findings:
            rule_id = f"vibeaudit/{finding.vuln_class.value}"
            level = _SEVERITY_TO_LEVEL.get(finding.severity, "warning")

            # Build message
            message_parts = [finding.title]
            if finding.description:
                message_parts.append(finding.description)
            message_text = "\n\n".join(message_parts)

            sarif_result: dict = {
                "ruleId": rule_id,
                "level": level,
                "message": {"text": message_text},
            }

            # Build locations from snippets
            locations = self._build_locations(finding)
            if locations:
                sarif_result["locations"] = locations

            # Properties
            props: dict = {}
            if finding.confidence:
                props["confidence"] = finding.confidence.value
            if finding.cwe_id:
                props["cwe"] = finding.cwe_id
            if finding.owasp_category:
                props["owasp"] = finding.owasp_category
            if finding.attack_scenario:
                props["attackScenario"] = finding.attack_scenario
            if finding.remediation:
                props["remediation"] = finding.remediation
            if finding.id:
                props["vibeauditId"] = finding.id
            if props:
                sarif_result["properties"] = props

            # Fixes (remediation suggestion)
            if finding.fix_example:
                sarif_result["fixes"] = [{
                    "description": {"text": finding.remediation or "Apply the suggested fix."},
                    "artifactChanges": [],
                }]

            results.append(sarif_result)

        return results

    def _build_locations(self, finding: Finding) -> list[dict]:
        """Build SARIF location objects from finding snippets."""
        locations: list[dict] = []

        for snippet in finding.snippets:
            location: dict = {
                "physicalLocation": {
                    "artifactLocation": {
                        "uri": snippet.file_path,
                        "uriBaseId": "%SRCROOT%",
                    },
                    "region": {
                        "startLine": snippet.start_line,
                        "endLine": snippet.end_line,
                    },
                },
            }

            # Add code snippet
            if snippet.content:
                location["physicalLocation"]["region"]["snippet"] = {
                    "text": snippet.content,
                }

            locations.append(location)

        return locations
