"""Normaliser for jscpd output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser


class JscpdNormaliser(BaseNormaliser):
    """Convert jscpd JSON output to Finding objects.

    jscpd JSON shape (from jscpd-report.json):
    {
      "statistics": {
        "total": {"lines": 5000, "sources": 120, "clones": 8, "duplicatedLines": 150, "percentage": 3.0}
      },
      "duplicates": [
        {
          "format": "typescript",
          "lines": 25,
          "tokens": 100,
          "firstFile": {"name": "src/a.ts", "start": 10, "end": 35, "startLoc": {"line": 10, "column": 0}},
          "secondFile": {"name": "src/b.ts", "start": 50, "end": 75, "startLoc": {"line": 50, "column": 0}},
          "fragment": "..."
        }
      ]
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        findings: list[Finding] = []

        stats = raw_data.get("statistics", {}).get("total", {})
        overall_pct = stats.get("percentage", 0)
        total_lines = stats.get("lines", 0)
        duplicated_lines = stats.get("duplicatedLines", 0)

        # Overall duplication summary
        if overall_pct > 0:
            severity = Severity.MEDIUM if overall_pct > 5 else Severity.LOW
            findings.append(Finding(
                tool="jscpd",
                severity=severity,
                category=Category.CODE,
                file="<project>",
                rule_id="overall-duplication",
                rule_name="Code duplication percentage",
                message=(
                    f"Project has {overall_pct:.1f}% code duplication "
                    f"({duplicated_lines} duplicated lines out of {total_lines} total)."
                ),
                metric="duplication_pct",
                current_value=overall_pct,
                target_value=5.0,
                fix_hint=(
                    "Extract duplicated code into shared utility functions or modules. "
                    "Consider using higher-order functions or composition patterns."
                ),
                saving_estimate=f"~{duplicated_lines} lines could be consolidated",
                effort=Effort.MEDIUM,
                raw={"statistics": stats},
            ))

        # Individual duplicate blocks
        for dup in raw_data.get("duplicates", []):
            first = dup.get("firstFile", {})
            second = dup.get("secondFile", {})
            lines = dup.get("lines", 0)
            first_name = first.get("name", "unknown")
            second_name = second.get("name", "unknown")
            first_start = first.get("start", 0)
            second_start = second.get("start", 0)

            severity = Severity.MEDIUM if lines > 20 else Severity.LOW

            findings.append(Finding(
                tool="jscpd",
                severity=severity,
                category=Category.CODE,
                file=first_name,
                rule_id="duplicate-block",
                rule_name="Duplicated code block",
                message=(
                    f"{lines}-line duplicate found between "
                    f"'{first_name}' (line {first_start}) and "
                    f"'{second_name}' (line {second_start})."
                ),
                line=first_start,
                fix_hint=(
                    f"Extract the shared {lines} lines into a common function "
                    f"and import it in both '{first_name}' and '{second_name}'."
                ),
                saving_estimate=f"~{lines} lines of duplicated code",
                effort=Effort.MEDIUM if lines > 30 else Effort.LOW,
                raw=dup,
            ))

        return findings
