"""git-secrets runner — scan git history for secrets."""

from __future__ import annotations
from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner


class GitSecretsRunner(AsyncToolRunner):
    name = "git_secrets"

    def should_run(self) -> bool:
        if not self._file_exists(".git"):
            self.skip_reason = "not a git repository"
            return False
        # Check if git-secrets is configured
        result = self._exec(["git", "secrets", "--list"], timeout=5)
        if result.returncode != 0:
            self.skip_reason = "git-secrets not configured"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        result = self._exec(["git", "secrets", "--scan"])
        findings = []
        if result.returncode != 0 and result.stderr.strip():
            for line in result.stderr.strip().split("\n"):
                if ":" in line:
                    parts = line.split(":", 2)
                    findings.append(Finding(
                        tool=self.name,
                        severity=Severity.CRITICAL,
                        category=Category.ENV_SECRETS,
                        file=parts[0] if len(parts) > 0 else "unknown",
                        line=int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None,
                        rule_id="git-secret",
                        rule_name="Git Secret",
                        message=parts[2].strip() if len(parts) > 2 else "Secret detected in git history",
                        blocks_deploy=True,
                        effort=Effort.MEDIUM,
                        fix_hint="Remove secret from git history using git filter-branch or BFG",
                    ))
        status = ToolStatus.SUCCESS
        return ToolResult(tool=self.name, status=status, findings=findings)
