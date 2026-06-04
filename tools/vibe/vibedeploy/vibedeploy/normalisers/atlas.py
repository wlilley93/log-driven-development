"""Normaliser for Atlas lint JSON output — schema migration linting."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser

# Atlas diagnostic code → (severity, blocks_deploy, effort, fix_hint)
_DIAG_MAP: dict[str, tuple[Severity, bool, Effort, str]] = {
    # Destructive changes
    "DS101": (Severity.CRITICAL, True, Effort.HIGH, "Dropping a schema destroys all contained objects"),
    "DS102": (Severity.CRITICAL, True, Effort.HIGH, "Dropping a table destroys data; archive or rename instead"),
    "DS103": (Severity.CRITICAL, True, Effort.HIGH, "Dropping a column destroys data; use a multi-step migration"),
    # Data-dependent changes
    "MF101": (Severity.HIGH, False, Effort.MEDIUM, "Adding a NOT NULL column without default may fail on existing data"),
    "MF102": (Severity.HIGH, False, Effort.HIGH, "Changing column type may cause data loss or table locks"),
    "MF103": (Severity.HIGH, False, Effort.MEDIUM, "Adding a unique constraint may fail if duplicates exist"),
    # Naming conventions
    "NM101": (Severity.LOW, False, Effort.TRIVIAL, "Table name does not follow naming convention"),
    "NM102": (Severity.LOW, False, Effort.TRIVIAL, "Column name does not follow naming convention"),
    # Backward compatibility
    "BC101": (Severity.HIGH, False, Effort.MEDIUM, "Renaming table may break existing queries"),
    "BC102": (Severity.HIGH, False, Effort.MEDIUM, "Renaming column may break existing queries"),
    # Locking
    "LK101": (Severity.HIGH, False, Effort.LOW, "Adding index without CONCURRENTLY locks the table"),
    # Diagnostics
    "DG101": (Severity.INFO, False, Effort.TRIVIAL, "Detected duplicate index definition"),
}


class AtlasNormaliser(BaseNormaliser):
    tool_name = "atlas"

    def normalise(self, raw_data: Any) -> list[Finding]:
        """Parse atlas lint JSON output.

        Expected format (atlas migrate lint --format json):
        {
            "steps": [
                {
                    "Name": "migration_file.sql",
                    "Text": "ALTER TABLE ...",
                    "Error": null,
                    "Result": {
                        "Diagnostics": [
                            {
                                "Pos": 10,
                                "Text": "Dropping table ...",
                                "Code": "DS102"
                            }
                        ]
                    }
                }
            ],
            "Diagnostics": [...]   // top-level diagnostics
        }
        """
        findings: list[Finding] = []

        if not isinstance(raw_data, dict):
            return findings

        # Process top-level diagnostics
        top_diags = raw_data.get("Diagnostics", raw_data.get("diagnostics", []))
        findings.extend(self._process_diagnostics(top_diags, "schema"))

        # Process step-level diagnostics
        steps = raw_data.get("steps", raw_data.get("Steps", []))
        for step in steps:
            if not isinstance(step, dict):
                continue
            file_name = step.get("Name", step.get("name", "unknown"))
            result = step.get("Result", step.get("result", {}))
            if isinstance(result, dict):
                diags = result.get("Diagnostics", result.get("diagnostics", []))
                findings.extend(self._process_diagnostics(diags, file_name))

            # Step-level error
            error = step.get("Error", step.get("error"))
            if error:
                findings.append(Finding(
                    tool=self.tool_name,
                    severity=Severity.CRITICAL,
                    category=Category.DATABASE,
                    file=file_name,
                    rule_id="atlas-error",
                    rule_name="Migration error",
                    message=str(error)[:300],
                    blocks_deploy=True,
                    effort=Effort.MEDIUM,
                ))

        # Also handle flat "files" format some atlas versions produce
        files = raw_data.get("files", [])
        for f in files:
            if not isinstance(f, dict):
                continue
            file_name = f.get("Name", f.get("name", "unknown"))
            reports = f.get("Reports", f.get("reports", []))
            for report in reports:
                if isinstance(report, dict):
                    diags = report.get("Diagnostics", report.get("diagnostics", []))
                    findings.extend(self._process_diagnostics(diags, file_name))

        return findings

    def _process_diagnostics(self, diagnostics: list, file_path: str) -> list[Finding]:
        """Convert a list of atlas diagnostics into findings."""
        findings: list[Finding] = []

        if not isinstance(diagnostics, list):
            return findings

        for diag in diagnostics:
            if not isinstance(diag, dict):
                continue

            code = diag.get("Code", diag.get("code", "unknown"))
            text = diag.get("Text", diag.get("text", diag.get("message", "")))
            pos = diag.get("Pos", diag.get("pos"))

            severity, blocks, effort, hint = _DIAG_MAP.get(
                code,
                (Severity.MEDIUM, False, Effort.MEDIUM, "Review atlas diagnostic"),
            )

            findings.append(Finding(
                tool=self.tool_name,
                severity=severity,
                category=Category.DATABASE,
                file=file_path,
                line=int(pos) if pos is not None else None,
                rule_id=f"atlas-{code}",
                rule_name=f"Atlas: {code}",
                message=text[:300] if text else f"Atlas diagnostic: {code}",
                blocks_deploy=blocks,
                effort=effort,
                fix_hint=hint,
                docs_url=f"https://atlasgo.io/lint/analyzers#{code}",
                raw=diag,
            ))

        return findings
