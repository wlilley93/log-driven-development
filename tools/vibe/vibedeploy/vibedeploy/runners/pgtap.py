"""pgtap runner — run PostgreSQL test framework via pg_prove."""

from __future__ import annotations

import re

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner


class PgtapRunner(AsyncToolRunner):
    name = "pgtap"

    def should_run(self) -> bool:
        # pg_prove is the test runner for pgTAP
        result = self._exec(["pg_prove", "--version"], timeout=5)
        if result.returncode != 0:
            self.skip_reason = "pg_prove not installed (required for pgTAP tests)"
            return False
        # Look for pgTAP test files (.sql files in test/ or t/ directories)
        test_files = self._scan_files(
            "t/*.sql",
            "test/*.sql",
            "tests/*.sql",
            "t/**/*.sql",
            "test/**/*.sql",
            "tests/**/*.sql",
        )
        if not test_files:
            self.skip_reason = "no pgTAP test files found (t/*.sql, test/*.sql)"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        tool_cfg = self.tool_config

        # Build pg_prove command
        cmd = ["pg_prove"]

        # Database connection
        db_name = tool_cfg.get("dbname", tool_cfg.get("database"))
        if db_name:
            cmd.extend(["-d", db_name])

        db_user = tool_cfg.get("username", tool_cfg.get("user"))
        if db_user:
            cmd.extend(["-U", db_user])

        db_host = tool_cfg.get("host")
        if db_host:
            cmd.extend(["-h", db_host])

        db_port = tool_cfg.get("port")
        if db_port:
            cmd.extend(["-p", str(db_port)])

        # Verbosity and output
        cmd.append("--verbose")

        # Add test directories
        test_dirs_found = False
        for test_dir in ("t", "test", "tests"):
            if self._file_exists(test_dir):
                cmd.append(test_dir)
                test_dirs_found = True

        if not test_dirs_found:
            # Fall back to individual files
            test_files = self._scan_files("t/*.sql", "test/*.sql", "tests/*.sql")
            cmd.extend(str(f) for f in test_files[:50])

        try:
            result = self._exec(cmd, timeout=self.config.timeout * 2)
        except Exception as exc:
            return self._make_error_result(f"pg_prove execution failed: {str(exc)[:200]}")

        findings = self._parse_tap_output(result.stdout, result.stderr)

        if result.returncode != 0 and not findings:
            # General failure without specific test failures
            findings.append(Finding(
                tool=self.name,
                severity=Severity.HIGH,
                category=Category.DATABASE,
                file="pgTAP",
                rule_id="pgtap-suite-failed",
                rule_name="Test suite failed",
                message=f"pgTAP test suite failed: {result.stderr.strip()[:200] or 'unknown error'}",
                blocks_deploy=True,
                effort=Effort.MEDIUM,
                fix_hint="Review pgTAP test failures and fix schema or test expectations",
            ))

        status = ToolStatus.SUCCESS if result.returncode == 0 else ToolStatus.PARTIAL

        return ToolResult(tool=self.name, status=status, findings=findings)

    def _parse_tap_output(self, stdout: str, stderr: str) -> list[Finding]:
        """Parse TAP (Test Anything Protocol) output for failures."""
        findings: list[Finding] = []

        # TAP format:
        # ok 1 - test description
        # not ok 2 - test description
        # # Failed test ...
        not_ok_pattern = re.compile(r"^not ok\s+(\d+)\s*-?\s*(.*)", re.MULTILINE)
        file_pattern = re.compile(r"^#\s+(?:in\s+)?(\S+\.sql)", re.MULTILINE)

        current_file = "pgTAP"
        for line in (stdout + "\n" + stderr).split("\n"):
            # Track current file context
            file_match = file_pattern.match(line)
            if file_match:
                current_file = file_match.group(1)

            not_ok_match = not_ok_pattern.match(line)
            if not_ok_match:
                test_num = not_ok_match.group(1)
                description = not_ok_match.group(2).strip() or f"Test #{test_num}"

                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.HIGH,
                    category=Category.DATABASE,
                    file=current_file,
                    line=int(test_num),
                    rule_id=f"pgtap-fail-{test_num}",
                    rule_name="Test failure",
                    message=f"pgTAP test failed: {description}",
                    blocks_deploy=True,
                    effort=Effort.MEDIUM,
                    fix_hint="Fix the failing database test or update expectations",
                ))

        return findings
