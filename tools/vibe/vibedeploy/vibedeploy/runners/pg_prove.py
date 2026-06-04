"""pg_prove runner — PostgreSQL test runner for pgTAP tests.

This is an alternative entry point that mirrors the pgtap runner,
using pg_prove directly as the tool name for projects that reference
it explicitly in their configuration.
"""

from __future__ import annotations

import re

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner


class PgProveRunner(AsyncToolRunner):
    name = "pg_prove"

    def should_run(self) -> bool:
        result = self._exec(["pg_prove", "--version"], timeout=5)
        if result.returncode != 0:
            self.skip_reason = "pg_prove not installed"
            return False
        # Look for test files
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

        cmd = ["pg_prove"]

        # Database connection options
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

        cmd.append("--verbose")

        # Collect test files
        test_files = self._scan_files(
            "t/*.sql",
            "test/*.sql",
            "tests/*.sql",
            "t/**/*.sql",
            "test/**/*.sql",
            "tests/**/*.sql",
        )
        if not test_files:
            return ToolResult(tool=self.name, status=ToolStatus.SKIPPED)

        cmd.extend(str(f) for f in test_files[:100])

        try:
            result = self._exec(cmd, timeout=self.config.timeout * 2)
        except Exception as exc:
            return self._make_error_result(f"pg_prove failed: {str(exc)[:200]}")

        findings = self._parse_results(result.stdout, result.stderr)

        if result.returncode != 0 and not findings:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.HIGH,
                category=Category.DATABASE,
                file="pg_prove",
                rule_id="pg-prove-failed",
                rule_name="Test suite failed",
                message=f"pg_prove test suite failed: {result.stderr.strip()[:200] or 'unknown error'}",
                blocks_deploy=True,
                effort=Effort.MEDIUM,
                fix_hint="Review and fix failing database tests",
            ))

        status = ToolStatus.SUCCESS if result.returncode == 0 else ToolStatus.PARTIAL

        return ToolResult(tool=self.name, status=status, findings=findings)

    def _parse_results(self, stdout: str, stderr: str) -> list[Finding]:
        """Parse TAP output for test failures."""
        findings: list[Finding] = []
        combined = stdout + "\n" + stderr

        not_ok_re = re.compile(r"^not ok\s+(\d+)\s*-?\s*(.*)", re.MULTILINE)
        file_re = re.compile(r"^(\S+\.sql)\s*\.\.", re.MULTILINE)

        current_file = "pg_prove"

        for line in combined.split("\n"):
            file_match = file_re.match(line)
            if file_match:
                current_file = file_match.group(1)

            not_ok_match = not_ok_re.match(line)
            if not_ok_match:
                test_num = not_ok_match.group(1)
                desc = not_ok_match.group(2).strip() or f"Test #{test_num}"

                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.HIGH,
                    category=Category.DATABASE,
                    file=current_file,
                    line=int(test_num),
                    rule_id=f"pg-prove-fail-{test_num}",
                    rule_name="Test failure",
                    message=f"Database test failed: {desc}",
                    blocks_deploy=True,
                    effort=Effort.MEDIUM,
                    fix_hint="Fix the failing database test or update expectations",
                ))

        # Parse summary line for total failures
        summary_re = re.compile(r"^Result:\s+FAIL", re.MULTILINE)
        failed_re = re.compile(r"Failed\s+(\d+)/(\d+)\s+subtests", re.MULTILINE)
        failed_match = failed_re.search(combined)

        if failed_match and not findings:
            failed_count = failed_match.group(1)
            total_count = failed_match.group(2)
            findings.append(Finding(
                tool=self.name,
                severity=Severity.HIGH,
                category=Category.DATABASE,
                file="pg_prove",
                rule_id="pg-prove-summary-fail",
                rule_name="Test suite partial failure",
                message=f"{failed_count}/{total_count} subtests failed",
                blocks_deploy=True,
                effort=Effort.MEDIUM,
            ))

        return findings
