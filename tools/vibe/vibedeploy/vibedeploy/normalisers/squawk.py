"""Normaliser for squawk JSON output — SQL migration linting."""

from __future__ import annotations

from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser

# Squawk rule → (severity, blocks_deploy, effort, fix_hint)
_RULE_MAP: dict[str, tuple[Severity, bool, Effort, str]] = {
    "ban-drop-table": (
        Severity.CRITICAL,
        True,
        Effort.HIGH,
        "Never drop tables in production migrations; rename or archive instead",
    ),
    "ban-drop-column": (
        Severity.CRITICAL,
        True,
        Effort.HIGH,
        "Use a multi-step migration: stop reading the column, deploy, then drop",
    ),
    "ban-drop-database": (
        Severity.CRITICAL,
        True,
        Effort.HIGH,
        "Never drop a database in a migration",
    ),
    "ban-drop-not-null": (
        Severity.HIGH,
        False,
        Effort.MEDIUM,
        "Dropping NOT NULL can cause data integrity issues; validate first",
    ),
    "ban-char-field": (
        Severity.LOW,
        False,
        Effort.TRIVIAL,
        "Use varchar or text instead of char for variable-length data",
    ),
    "adding-serial-primary-key": (
        Severity.MEDIUM,
        False,
        Effort.MEDIUM,
        "Prefer BIGINT GENERATED ALWAYS AS IDENTITY or UUIDs over serial",
    ),
    "adding-primary-key-constraint": (
        Severity.MEDIUM,
        False,
        Effort.MEDIUM,
        "Add primary key constraints using CREATE UNIQUE INDEX CONCURRENTLY, then ALTER TABLE ... ADD CONSTRAINT ... USING INDEX",
    ),
    "adding-foreign-key-constraint": (
        Severity.HIGH,
        False,
        Effort.MEDIUM,
        "Add foreign keys with NOT VALID first, then VALIDATE CONSTRAINT separately",
    ),
    "adding-not-nullable-field": (
        Severity.HIGH,
        False,
        Effort.MEDIUM,
        "Add column as nullable first, backfill, then set NOT NULL with a CHECK constraint",
    ),
    "changing-column-type": (
        Severity.HIGH,
        False,
        Effort.HIGH,
        "Changing column type locks the table; use a multi-step migration",
    ),
    "renaming-column": (
        Severity.HIGH,
        False,
        Effort.MEDIUM,
        "Renaming columns breaks running queries; use a view or add-then-migrate pattern",
    ),
    "renaming-table": (
        Severity.HIGH,
        False,
        Effort.MEDIUM,
        "Renaming tables breaks running queries; use a view or add-then-migrate pattern",
    ),
    "disallowed-unique-constraint": (
        Severity.MEDIUM,
        False,
        Effort.MEDIUM,
        "Create unique index concurrently instead of adding a unique constraint",
    ),
    "require-concurrent-index-creation": (
        Severity.HIGH,
        False,
        Effort.LOW,
        "Use CREATE INDEX CONCURRENTLY to avoid table locks",
    ),
    "require-concurrent-index-deletion": (
        Severity.MEDIUM,
        False,
        Effort.LOW,
        "Use DROP INDEX CONCURRENTLY to avoid table locks",
    ),
    "prefer-big-int": (
        Severity.LOW,
        False,
        Effort.TRIVIAL,
        "Use BIGINT instead of INT to avoid overflow on high-volume tables",
    ),
    "prefer-identity": (
        Severity.LOW,
        False,
        Effort.TRIVIAL,
        "Use GENERATED ALWAYS AS IDENTITY instead of serial",
    ),
    "prefer-text-field": (
        Severity.LOW,
        False,
        Effort.TRIVIAL,
        "Use text instead of varchar for unconstrained strings",
    ),
    "prefer-robust-stmts": (
        Severity.LOW,
        False,
        Effort.TRIVIAL,
        "Use IF EXISTS / IF NOT EXISTS for idempotent migrations",
    ),
}

# Default for unknown rules
_DEFAULT_RULE = (Severity.MEDIUM, False, Effort.MEDIUM, "Review migration safety")


class SquawkNormaliser(BaseNormaliser):
    tool_name = "squawk"

    def normalise(self, raw_data: Any) -> list[Finding]:
        """Parse squawk JSON output.

        raw_data is expected to be a list of violation objects, each with:
            file, line, column, level, rule_name, messages
        Or a dict with 'violations' key containing a list.
        """
        findings: list[Finding] = []

        violations: list[dict] = []
        if isinstance(raw_data, list):
            violations = raw_data
        elif isinstance(raw_data, dict):
            violations = raw_data.get("violations", raw_data.get("results", []))
            # Single violation passed directly
            if "rule_name" in raw_data:
                violations = [raw_data]

        for v in violations:
            if not isinstance(v, dict):
                continue

            rule = v.get("rule_name", v.get("rule", "unknown"))
            severity, blocks, effort, hint = _RULE_MAP.get(rule, _DEFAULT_RULE)

            # Extract message — squawk uses 'messages' array or 'message' string
            messages = v.get("messages", [])
            if isinstance(messages, list) and messages:
                message_parts = []
                for m in messages:
                    if isinstance(m, dict):
                        message_parts.append(m.get("Note", m.get("note", m.get("message", str(m)))))
                    else:
                        message_parts.append(str(m))
                message = "; ".join(filter(None, message_parts))
            else:
                message = v.get("message", f"SQL migration lint: {rule}")

            file_path = v.get("file", v.get("filename", "unknown"))
            line_num = v.get("line", v.get("line_number"))

            findings.append(Finding(
                tool=self.tool_name,
                severity=severity,
                category=Category.DATABASE,
                file=file_path,
                line=int(line_num) if line_num is not None else None,
                col=int(v["column"]) if v.get("column") is not None else None,
                rule_id=rule,
                rule_name=rule,
                message=message or f"Migration safety issue: {rule}",
                blocks_deploy=blocks,
                effort=effort,
                fix_hint=hint,
                docs_url=f"https://squawkhq.com/docs/rules/{rule}",
                raw=v,
            ))

        return findings
