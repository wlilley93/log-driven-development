"""Normaliser for sqlfluff JSON output — SQL linting."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser

# Rule prefix severity mapping:
#   L00x = parsing errors → HIGH
#   L01x = layout/whitespace → LOW
#   L02x = layout/whitespace → LOW
#   L03x = references → MEDIUM
#   L04x = naming → LOW
#   L05x = logic → MEDIUM
#   L06x = anti-patterns → HIGH
#   AM/CP/CV/JJ/LT/RF/ST/TQ prefixes (sqlfluff 2.x+)
_PREFIX_SEVERITY: dict[str, Severity] = {
    "L00": Severity.HIGH,
    "L01": Severity.LOW,
    "L02": Severity.LOW,
    "L03": Severity.MEDIUM,
    "L04": Severity.LOW,
    "L05": Severity.MEDIUM,
    "L06": Severity.HIGH,
    "L07": Severity.MEDIUM,
    "L08": Severity.MEDIUM,
    "L09": Severity.MEDIUM,
    # sqlfluff 2.x+ rule prefixes
    "AM": Severity.MEDIUM,   # ambiguous
    "CP": Severity.LOW,      # capitalisation
    "CV": Severity.MEDIUM,   # convention
    "JJ": Severity.MEDIUM,   # jinja
    "LT": Severity.LOW,      # layout
    "RF": Severity.MEDIUM,   # references
    "ST": Severity.HIGH,     # structure
    "TQ": Severity.MEDIUM,   # tsql
    "AL": Severity.LOW,      # aliasing
    "PRS": Severity.HIGH,    # parsing
}


def _code_to_severity(code: str) -> Severity:
    """Map a sqlfluff rule code to a severity level."""
    # Try 3-char prefix first (e.g. L00, L01), then 2-char (e.g. AM, ST)
    prefix3 = code[:3] if len(code) >= 3 else code
    if prefix3 in _PREFIX_SEVERITY:
        return _PREFIX_SEVERITY[prefix3]

    prefix2 = code[:2] if len(code) >= 2 else code
    if prefix2 in _PREFIX_SEVERITY:
        return _PREFIX_SEVERITY[prefix2]

    return Severity.MEDIUM


class SqlfluffNormaliser(BaseNormaliser):
    tool_name = "sqlfluff"

    def normalise(self, raw_data: Any) -> list[Finding]:
        """Parse sqlfluff JSON lint output.

        Expected format (sqlfluff lint --format json):
        [
            {
                "filepath": "path/to/file.sql",
                "violations": [
                    {
                        "code": "L001",
                        "line_no": 5,
                        "line_pos": 10,
                        "description": "Unnecessary trailing whitespace",
                        "name": "layout.trailing_whitespace"
                    },
                    ...
                ]
            },
            ...
        ]
        """
        findings: list[Finding] = []

        file_results: list[dict] = []
        if isinstance(raw_data, list):
            file_results = raw_data
        elif isinstance(raw_data, dict):
            # Single file result or wrapper
            if "filepath" in raw_data:
                file_results = [raw_data]
            else:
                file_results = raw_data.get("files", raw_data.get("results", []))

        for file_result in file_results:
            if not isinstance(file_result, dict):
                continue

            filepath = file_result.get("filepath", "unknown")
            violations = file_result.get("violations", [])

            for v in violations:
                if not isinstance(v, dict):
                    continue

                code = v.get("code", "unknown")
                severity = _code_to_severity(code)
                description = v.get("description", v.get("message", f"SQL lint: {code}"))
                rule_name = v.get("name", code)

                findings.append(Finding(
                    tool=self.tool_name,
                    severity=severity,
                    category=Category.DATABASE,
                    file=filepath,
                    line=v.get("line_no"),
                    col=v.get("line_pos"),
                    rule_id=code,
                    rule_name=rule_name,
                    message=description,
                    blocks_deploy=False,
                    effort=Effort.TRIVIAL if severity <= Severity.LOW else Effort.LOW,
                    fix_hint=v.get("fix", None),
                    docs_url=f"https://docs.sqlfluff.com/en/stable/rules.html#{code}",
                    raw=v,
                ))

        return findings
