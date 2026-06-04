"""procfile_linter — custom runner linting Procfile format."""

from __future__ import annotations

import re
from pathlib import Path

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner

# Valid Procfile process types
VALID_PROCESS_TYPES = {
    "web", "worker", "clock", "release", "urgentworker",
    "scheduler", "console", "redis", "beat",
}

# Pattern for valid Procfile lines: type: command
PROCFILE_LINE = re.compile(r"^([a-zA-Z][a-zA-Z0-9_-]*)\s*:\s*(.+)$")

# Hardcoded port patterns
HARDCODED_PORT = re.compile(r"""-(?:p|port)\s+(\d+)|\bPORT\s*=\s*(\d+)|--port[= ](\d+)|:\d{4,5}\b""")


class ProcfileLinterRunner(AsyncToolRunner):
    name = "procfile_linter"

    def should_run(self) -> bool:
        if not self._file_exists("Procfile"):
            self.skip_reason = "no Procfile found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        findings: list[Finding] = []
        target = Path(self.target)
        procfile = target / "Procfile"

        content = self._read_file(procfile)
        lines = content.split("\n")

        has_web = False
        has_release = False
        process_names: list[str] = []
        has_migration_files = self._file_exists(
            "alembic.ini", "migrations", "db/migrate",
            "prisma/schema.prisma", "knexfile.js",
        )

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Skip empty lines and comments
            if not stripped or stripped.startswith("#"):
                continue

            match = PROCFILE_LINE.match(stripped)
            if not match:
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.HIGH,
                    category=Category.PROCESS,
                    file="Procfile",
                    line=i,
                    rule_id="procfile-invalid-line",
                    rule_name="Invalid Procfile Line",
                    message=f"Line {i} is not valid Procfile format: '{stripped}'",
                    blocks_deploy=True,
                    effort=Effort.TRIVIAL,
                    fix_hint="Procfile format: process_type: command",
                ))
                continue

            process_type = match.group(1)
            command = match.group(2).strip()

            if process_type == "web":
                has_web = True
            if process_type == "release":
                has_release = True

            # Check for duplicate process names
            if process_type in process_names:
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.HIGH,
                    category=Category.PROCESS,
                    file="Procfile",
                    line=i,
                    rule_id="procfile-duplicate-process",
                    rule_name="Duplicate Process Type",
                    message=f"Process type '{process_type}' is defined more than once",
                    blocks_deploy=True,
                    effort=Effort.TRIVIAL,
                    fix_hint=f"Remove duplicate '{process_type}' definition",
                ))
            process_names.append(process_type)

            # Warn on unusual process types
            if process_type.lower() not in VALID_PROCESS_TYPES and process_type not in process_names[:1]:
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.INFO,
                    category=Category.PROCESS,
                    file="Procfile",
                    line=i,
                    rule_id="procfile-unusual-type",
                    rule_name="Unusual Process Type",
                    message=f"Process type '{process_type}' is non-standard",
                    blocks_deploy=False,
                    effort=Effort.TRIVIAL,
                ))

            # Check for hardcoded ports (should use $PORT)
            if process_type == "web" and "$PORT" not in command:
                port_match = HARDCODED_PORT.search(command)
                if port_match:
                    findings.append(Finding(
                        tool=self.name,
                        severity=Severity.MEDIUM,
                        category=Category.PROCESS,
                        file="Procfile",
                        line=i,
                        rule_id="procfile-hardcoded-port",
                        rule_name="Hardcoded Port in Procfile",
                        message=(
                            "Web process has a hardcoded port. Use $PORT environment "
                            "variable for platform compatibility."
                        ),
                        blocks_deploy=False,
                        effort=Effort.TRIVIAL,
                        fix_hint="Replace hardcoded port with $PORT",
                    ))

            # Check for empty commands
            if not command:
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.HIGH,
                    category=Category.PROCESS,
                    file="Procfile",
                    line=i,
                    rule_id="procfile-empty-command",
                    rule_name="Empty Process Command",
                    message=f"Process type '{process_type}' has no command",
                    blocks_deploy=True,
                    effort=Effort.TRIVIAL,
                ))

        # Missing web process
        if not has_web:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.HIGH,
                category=Category.PROCESS,
                file="Procfile",
                rule_id="procfile-no-web",
                rule_name="Missing Web Process",
                message=(
                    "Procfile does not define a 'web' process. Most platforms require "
                    "a web process type to route HTTP traffic."
                ),
                blocks_deploy=True,
                effort=Effort.TRIVIAL,
                fix_hint="Add: web: <your-server-command>",
            ))

        # Suggest release process for migration-capable projects
        if has_migration_files and not has_release:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.LOW,
                category=Category.PROCESS,
                file="Procfile",
                rule_id="procfile-no-release",
                rule_name="No Release Process for Migrations",
                message=(
                    "Project has database migration files but no 'release' process in Procfile. "
                    "A release process runs migrations before the new version starts."
                ),
                blocks_deploy=False,
                effort=Effort.TRIVIAL,
                fix_hint="Add: release: <your-migration-command>",
            ))

        return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=findings)
