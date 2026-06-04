"""Normaliser for migra text diff output — unsafe schema change detection."""

from __future__ import annotations

import re
from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser

# Pattern → (severity, blocks_deploy, effort, fix_hint)
_OP_PATTERNS: list[tuple[re.Pattern, Severity, bool, Effort, str, str]] = [
    (
        re.compile(r"^\s*DROP\s+TABLE", re.IGNORECASE),
        Severity.CRITICAL,
        True,
        Effort.HIGH,
        "drop-table",
        "Dropping tables destroys data; rename or archive instead",
    ),
    (
        re.compile(r"^\s*DROP\s+COLUMN", re.IGNORECASE),
        Severity.CRITICAL,
        True,
        Effort.HIGH,
        "drop-column",
        "Dropping columns destroys data; use a multi-step migration",
    ),
    (
        re.compile(r"^\s*DROP\s+INDEX", re.IGNORECASE),
        Severity.HIGH,
        False,
        Effort.LOW,
        "drop-index",
        "Dropping indexes may degrade query performance; verify before applying",
    ),
    (
        re.compile(r"^\s*DROP\s+SCHEMA", re.IGNORECASE),
        Severity.CRITICAL,
        True,
        Effort.HIGH,
        "drop-schema",
        "Dropping schemas destroys all contained objects",
    ),
    (
        re.compile(r"^\s*DROP\s+TYPE", re.IGNORECASE),
        Severity.HIGH,
        True,
        Effort.MEDIUM,
        "drop-type",
        "Dropping types may break dependent columns and functions",
    ),
    (
        re.compile(r"^\s*DROP\s+FUNCTION", re.IGNORECASE),
        Severity.HIGH,
        False,
        Effort.MEDIUM,
        "drop-function",
        "Dropping functions may break dependent triggers or queries",
    ),
    (
        re.compile(r"^\s*DROP\s+VIEW", re.IGNORECASE),
        Severity.HIGH,
        False,
        Effort.MEDIUM,
        "drop-view",
        "Dropping views may break application queries",
    ),
    (
        re.compile(r"^\s*ALTER\s+TABLE\s+.*\s+DROP\s+", re.IGNORECASE),
        Severity.CRITICAL,
        True,
        Effort.HIGH,
        "alter-drop",
        "ALTER TABLE ... DROP destroys data; use a multi-step migration",
    ),
    (
        re.compile(r"^\s*ALTER\s+TABLE\s+.*\s+ALTER\s+COLUMN\s+.*\s+TYPE\s+", re.IGNORECASE),
        Severity.HIGH,
        False,
        Effort.HIGH,
        "alter-column-type",
        "Changing column types requires a table rewrite and lock; use add-migrate-drop pattern",
    ),
    (
        re.compile(r"^\s*ALTER\s+TABLE\s+.*\s+SET\s+NOT\s+NULL", re.IGNORECASE),
        Severity.HIGH,
        False,
        Effort.MEDIUM,
        "set-not-null",
        "Setting NOT NULL requires a full table scan; add a CHECK constraint first",
    ),
    (
        re.compile(r"^\s*ALTER\s+TABLE\s+.*\s+RENAME", re.IGNORECASE),
        Severity.HIGH,
        False,
        Effort.MEDIUM,
        "rename",
        "Renaming tables/columns breaks running queries; use a view-based migration",
    ),
    (
        re.compile(r"^\s*ALTER\s+", re.IGNORECASE),
        Severity.MEDIUM,
        False,
        Effort.MEDIUM,
        "alter-generic",
        "Review ALTER statement for production safety",
    ),
    (
        re.compile(r"^\s*CREATE\s+", re.IGNORECASE),
        Severity.INFO,
        False,
        Effort.TRIVIAL,
        "create",
        "New objects being created — verify naming and permissions",
    ),
    (
        re.compile(r"^\s*GRANT\s+", re.IGNORECASE),
        Severity.LOW,
        False,
        Effort.TRIVIAL,
        "grant",
        "Permission change — verify principle of least privilege",
    ),
    (
        re.compile(r"^\s*REVOKE\s+", re.IGNORECASE),
        Severity.MEDIUM,
        False,
        Effort.LOW,
        "revoke",
        "Permission revocation — verify it does not break application access",
    ),
]


class MigraNormaliser(BaseNormaliser):
    tool_name = "migra"

    def normalise(self, raw_data: Any) -> list[Finding]:
        """Parse migra text diff into findings.

        raw_data is expected to be a dict with:
            output: str — the full migra diff text
            file: str (optional) — source identifier
        """
        findings: list[Finding] = []

        if isinstance(raw_data, str):
            output = raw_data
            file_path = "schema-diff"
        elif isinstance(raw_data, dict):
            output = raw_data.get("output", "")
            file_path = raw_data.get("file", "schema-diff")
        else:
            return findings

        if not output.strip():
            return findings

        # Split into individual statements (semicolon-terminated)
        statements = [s.strip() for s in output.split(";") if s.strip()]

        for idx, stmt in enumerate(statements, start=1):
            matched = False
            for pattern, severity, blocks, effort, rule_id, hint in _OP_PATTERNS:
                if pattern.search(stmt):
                    # Extract first line as summary
                    first_line = stmt.split("\n")[0].strip()
                    findings.append(Finding(
                        tool=self.tool_name,
                        severity=severity,
                        category=Category.DATABASE,
                        file=file_path,
                        line=idx,
                        rule_id=f"migra-{rule_id}",
                        rule_name=f"Schema diff: {rule_id}",
                        message=first_line[:200],
                        blocks_deploy=blocks,
                        effort=effort,
                        fix_hint=hint,
                        raw={"statement": stmt[:500]},
                    ))
                    matched = True
                    break

            if not matched and stmt.strip():
                # Catch-all for unmatched statements
                first_line = stmt.split("\n")[0].strip()
                findings.append(Finding(
                    tool=self.tool_name,
                    severity=Severity.LOW,
                    category=Category.DATABASE,
                    file=file_path,
                    line=idx,
                    rule_id="migra-unclassified",
                    rule_name="Schema diff: unclassified",
                    message=first_line[:200],
                    effort=Effort.UNKNOWN,
                    raw={"statement": stmt[:500]},
                ))

        return findings
