"""liquibase runner — validate database migration changelog."""

from __future__ import annotations

import re

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner


class LiquibaseRunner(AsyncToolRunner):
    name = "liquibase"

    def should_run(self) -> bool:
        result = self._exec(["liquibase", "--version"], timeout=15)
        if result.returncode != 0:
            self.skip_reason = "liquibase not installed"
            return False
        # Check for changelog files
        has_changelog = self._file_exists(
            "changelog.xml", "changelog.yaml", "changelog.yml", "changelog.json", "changelog.sql",
            "db/changelog.xml", "db/changelog.yaml",
            "db.changelog-master.xml", "db.changelog-master.yaml",
        ) or bool(self._scan_files(
            "**/changelog*.xml", "**/changelog*.yaml", "**/changelog*.yml",
            "**/changelog*.sql", "**/changelog*.json",
        ))
        has_config = self._file_exists(
            "liquibase.properties", "liquibase.yml", "liquibase.yaml",
        )
        if not (has_changelog or has_config):
            self.skip_reason = "no liquibase changelog or config found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        tool_cfg = self.tool_config

        cmd = ["liquibase", "validate"]

        # Connection parameters
        url = tool_cfg.get("url", tool_cfg.get("database_url"))
        if url:
            cmd.extend(["--url", url])

        username = tool_cfg.get("username", tool_cfg.get("user"))
        if username:
            cmd.extend(["--username", username])

        password = tool_cfg.get("password")
        if password:
            cmd.extend(["--password", password])

        # Changelog file
        changelog = tool_cfg.get("changelog", tool_cfg.get("changelog_file"))
        if changelog:
            cmd.extend(["--changelog-file", changelog])

        try:
            result = self._exec(cmd, timeout=self.config.timeout)
        except Exception as exc:
            return self._make_error_result(f"liquibase validate failed: {str(exc)[:200]}")

        findings = self._parse_output(result.stdout, result.stderr, result.returncode)

        status = ToolStatus.SUCCESS if result.returncode == 0 else ToolStatus.PARTIAL

        return ToolResult(
            tool=self.name,
            status=status,
            findings=findings,
            error=result.stderr.strip()[:200] if result.returncode != 0 and result.stderr.strip() else None,
        )

    def _parse_output(self, stdout: str, stderr: str, returncode: int) -> list[Finding]:
        """Parse liquibase validate output."""
        findings: list[Finding] = []
        combined = stdout + "\n" + stderr

        if returncode == 0 and "no validation errors" in combined.lower():
            return findings

        # Liquibase validation errors
        error_re = re.compile(
            r"(?:Validation\s+(?:Error|Failed)|ERROR|SEVERE):\s*(.*)",
            re.MULTILINE | re.IGNORECASE,
        )
        for match in error_re.finditer(combined):
            message = match.group(1).strip()
            if not message:
                continue

            rule_id = "liquibase-validation-error"
            severity = Severity.CRITICAL
            blocks = True

            if "checksum" in message.lower():
                rule_id = "liquibase-checksum-mismatch"
            elif "not found" in message.lower() or "missing" in message.lower():
                rule_id = "liquibase-missing-changeset"
            elif "duplicate" in message.lower():
                rule_id = "liquibase-duplicate-changeset"
                severity = Severity.HIGH
            elif "precondition" in message.lower():
                rule_id = "liquibase-precondition-fail"
                severity = Severity.HIGH

            findings.append(Finding(
                tool=self.name,
                severity=severity,
                category=Category.DATABASE,
                file="liquibase",
                rule_id=rule_id,
                rule_name=rule_id.replace("-", " ").title(),
                message=message[:300],
                blocks_deploy=blocks,
                effort=Effort.MEDIUM,
                fix_hint="Review changelog for validation errors and fix before deploying",
                docs_url="https://docs.liquibase.com/commands/utility/validate.html",
            ))

        # Check for changeset parse errors in the full output
        changeset_err_re = re.compile(
            r"ChangeSet\s+(\S+)::\s*(.*?)(?:\n|$)", re.MULTILINE
        )
        for match in changeset_err_re.finditer(combined):
            changeset_id = match.group(1)
            detail = match.group(2).strip()
            if detail and not any(detail in f.message for f in findings):
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.HIGH,
                    category=Category.DATABASE,
                    file="liquibase",
                    rule_id="liquibase-changeset-error",
                    rule_name="Changeset error",
                    message=f"ChangeSet {changeset_id}: {detail[:200]}",
                    blocks_deploy=True,
                    effort=Effort.MEDIUM,
                ))

        # General failure fallback
        if returncode != 0 and not findings:
            error_text = combined.strip()[-300:] if combined.strip() else "Unknown error"
            findings.append(Finding(
                tool=self.name,
                severity=Severity.HIGH,
                category=Category.DATABASE,
                file="liquibase",
                rule_id="liquibase-validate-failed",
                rule_name="Validation failed",
                message=f"Liquibase validate returned error: {error_text}",
                blocks_deploy=True,
                effort=Effort.MEDIUM,
            ))

        return findings
