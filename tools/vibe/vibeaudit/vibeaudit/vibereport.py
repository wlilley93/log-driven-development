"""Merge vibeaudit JSON + SARIF into unified report."""

from __future__ import annotations

import json
from pathlib import Path

from vibeaudit.models import (
    CodeSnippet, Confidence, Finding, ScanResult, Severity, VulnClass,
)


def merge_reports(files: list[Path]) -> ScanResult:
    """Merge multiple report files (vibeaudit JSON + SARIF) into one ScanResult."""
    all_findings: list[Finding] = []
    seen_ids: set[str] = set()

    for path in files:
        content = path.read_text()

        if path.suffix == ".sarif":
            findings = _parse_sarif(content)
        elif path.suffix == ".json":
            findings = _parse_vibeaudit_json(content)
        else:
            continue

        for f in findings:
            if f.id not in seen_ids:
                seen_ids.add(f.id)
                all_findings.append(f)

    all_findings.sort(key=lambda f: f.severity.rank)
    return ScanResult(findings=all_findings)


def _parse_vibeaudit_json(content: str) -> list[Finding]:
    """Parse vibeaudit JSON format."""
    try:
        data = json.loads(content)
        if "findings" in data:
            result = ScanResult(**data)
            return result.findings
        return []
    except Exception:
        return []


def _parse_sarif(content: str) -> list[Finding]:
    """Parse SARIF 2.1.0 format into vibeaudit Findings."""
    try:
        sarif = json.loads(content)
    except json.JSONDecodeError:
        return []

    findings: list[Finding] = []

    for run in sarif.get("runs", []):
        rules = {r["id"]: r for r in run.get("tool", {}).get("driver", {}).get("rules", [])}

        for result in run.get("results", []):
            rule_id = result.get("ruleId", "")
            level = result.get("level", "warning")
            message = result.get("message", {}).get("text", "")

            # Map SARIF level to severity
            severity_map = {"error": "high", "warning": "medium", "note": "low", "none": "info"}
            severity = severity_map.get(level, "medium")

            # Map rule ID to vuln class if possible
            vuln_class = _guess_vuln_class(rule_id)

            # Extract location
            snippets = []
            for loc in result.get("locations", []):
                phys = loc.get("physicalLocation", {})
                artifact = phys.get("artifactLocation", {})
                region = phys.get("region", {})

                snippets.append(CodeSnippet(
                    file_path=artifact.get("uri", "unknown"),
                    start_line=region.get("startLine", 1),
                    end_line=region.get("endLine", region.get("startLine", 1)),
                    content=region.get("snippet", {}).get("text", ""),
                ))

            rule = rules.get(rule_id, {})

            findings.append(Finding(
                vuln_class=vuln_class,
                severity=Severity(severity),
                confidence=Confidence.MEDIUM,
                title=rule.get("shortDescription", {}).get("text", rule_id),
                description=message,
                snippets=snippets,
                cwe_id=_extract_cwe(result),
                source="sarif_import",
            ))

    return findings


def _guess_vuln_class(rule_id: str) -> VulnClass:
    """Best-effort mapping of external rule IDs to vibeaudit vuln classes."""
    rule_lower = rule_id.lower()
    mappings = {
        "sql": VulnClass.COMMAND_INJECTION,
        "xss": VulnClass.DATA_EXPOSURE,
        "ssrf": VulnClass.SSRF,
        "path": VulnClass.PATH_TRAVERSAL,
        "traversal": VulnClass.PATH_TRAVERSAL,
        "injection": VulnClass.COMMAND_INJECTION,
        "auth": VulnClass.AUTH_BYPASS,
        "crypto": VulnClass.CRYPTO_WEAKNESS,
        "xxe": VulnClass.XXE,
        "idor": VulnClass.IDOR,
    }
    for keyword, vc in mappings.items():
        if keyword in rule_lower:
            return vc
    return VulnClass.INSECURE_DEFAULTS


def _extract_cwe(result: dict) -> str:
    """Extract CWE ID from SARIF result properties."""
    props = result.get("properties", {})
    tags = props.get("tags", [])
    for tag in tags:
        if isinstance(tag, str) and tag.upper().startswith("CWE"):
            return tag
    return ""
