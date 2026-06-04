"""flyway runner — validate database migration state."""

from __future__ import annotations

import re

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner


class FlywayRunner(AsyncToolRunner):
    name = "flyway"

    def should_run(self) -> bool:
        result = self._exec(["flyway", "--version"], timeout=10)
        if result.returncode != 0:
            self.skip_reason = "flyway not installed"
            return False
        # Check for flyway config or migration directories
        has_config = self._file_exists(
            "flyway.conf", "flyway.toml", "flyway.yml",
            "conf/flyway.conf", "flyway/flyway.conf",
        )
        has_migrations = self._file_exists(
            "sql", "db/migration", "db/migrations",
            "flyway/sql", "migrations",
        )
        has_sql = bool(self._scan_files("V*.sql", "R*.sql", "U*.sql"))
        if not (has_config or has_migrations or has_sql):
            self.skip_reason = "no flyway config or versioned migration files found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        tool_cfg = self.tool_config

        cmd = ["flyway", "validate"]

        # Add connection URL if configured
        url = tool_cfg.get("url", tool_cfg.get("database_url"))
        if url:
            cmd.append(f"-url={url}")

        user = tool_cfg.get("user", tool_cfg.get("username"))
        if user:
            cmd.append(f"-user={user}")

        password = tool_cfg.get("password")
        if password:
            cmd.append(f"-password={password}")

        # Add migration locations
        locations = tool_cfg.get("locations")
        if locations:
            if isinstance(locations, list):
                cmd.append(f"-locations={','.join(locations)}")
            else:
                cmd.append(f"-locations={locations}")

        try:
            result = self._exec(cmd, timeout=self.config.timeout)
        except Exception as exc:
            return self._make_error_result(f"flyway validate failed: {str(exc)[:200]}")

        findings = self._parse_output(result.stdout, result.stderr, result.returncode)

        status = ToolStatus.SUCCESS if result.returncode == 0 else ToolStatus.PARTIAL

        return ToolResult(
            tool=self.name,
            status=status,
            findings=findings,
            error=result.stderr.strip()[:200] if result.returncode != 0 and result.stderr.strip() else None,
        )

    def _parse_output(self, stdout: str, stderr: str, returncode: int) -> list[Finding]:
        """Parse flyway validate output for issues."""
        findings: list[Finding] = []
        combined = stdout + "\n" + stderr

        # Flyway validation errors:
        # ERROR: Validate failed: Detected resolved migration not applied to database: X.Y
        error_re = re.compile(
            r"(?:ERROR|WARN):\s*(.*)", re.MULTILINE
        )
        for match in error_re.finditer(combined):
            message = match.group(1).strip()
            if not message:
                continue

            severity = Severity.CRITICAL if "ERROR" in match.group(0) else Severity.HIGH
            blocks = severity == Severity.CRITICAL

            # Classify the error
            rule_id = "flyway-validate-error"
            if "not applied" in message.lower():
                rule_id = "flyway-pending-migration"
            elif "mismatch" in message.lower() or "checksum" in message.lower():
                rule_id = "flyway-checksum-mismatch"
                severity = Severity.CRITICAL
                blocks = True
            elif "missing" in message.lower():
                rule_id = "flyway-missing-migration"
                severity = Severity.CRITICAL
                blocks = True
            elif "failed" in message.lower():
                rule_id = "flyway-failed-migration"
                severity = Severity.CRITICAL
                blocks = True

            findings.append(Finding(
                tool=self.name,
                severity=severity,
                category=Category.DATABASE,
                file="flyway",
                rule_id=rule_id,
                rule_name=rule_id.replace("-", " ").title(),
                message=message[:300],
                blocks_deploy=blocks,
                effort=Effort.MEDIUM,
                fix_hint="Run 'flyway repair' to fix checksums, or review migration history",
                docs_url="https://documentation.red-gate.com/fd/validate-277579718.html",
            ))

        # Check for pending migrations (not necessarily errors)
        pending_re = re.compile(r"(\d+)\s+pending\s+migration", re.IGNORECASE)
        pending_match = pending_re.search(combined)
        if pending_match and not any(f.rule_id == "flyway-pending-migration" for f in findings):
            count = pending_match.group(1)
            findings.append(Finding(
                tool=self.name,
                severity=Severity.HIGH,
                category=Category.DATABASE,
                file="flyway",
                rule_id="flyway-pending-migration",
                rule_name="Pending migrations",
                message=f"{count} pending migration(s) not yet applied to the database",
                blocks_deploy=True,
                effort=Effort.LOW,
                fix_hint="Run 'flyway migrate' to apply pending migrations before deploy",
            ))

        return findings
