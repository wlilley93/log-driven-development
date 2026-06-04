"""aws-vault runner — check AWS credential management configuration."""

from __future__ import annotations

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner


class AwsVaultRunner(AsyncToolRunner):
    name = "aws_vault"
    requires_cloud = True

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "aws-vault not installed"
            return False
        return super().should_run()

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        findings: list[Finding] = []

        # Check if aws-vault is configured with any profiles
        result = self._exec([self.bin_path, "list"], timeout=30)

        if result.returncode != 0:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.MEDIUM,
                category=Category.CLOUD,
                file="aws-vault",
                rule_id="aws-vault-not-configured",
                rule_name="AWS Vault Not Configured",
                message="aws-vault is installed but not configured — credentials may not be secured",
                blocks_deploy=False,
                effort=Effort.LOW,
                fix_hint="Configure aws-vault with your AWS profiles: aws-vault add <profile>",
                docs_url="https://github.com/99designs/aws-vault",
            ))
            return ToolResult(tool=self.name, status=ToolStatus.PARTIAL, findings=findings)

        # Parse list output to check for stale sessions or missing MFA
        profiles_seen = set()
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("Profile") or line.startswith("="):
                continue

            parts = line.split()
            if parts:
                profile = parts[0]
                profiles_seen.add(profile)

        if not profiles_seen:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.MEDIUM,
                category=Category.CLOUD,
                file="aws-vault",
                rule_id="aws-vault-no-profiles",
                rule_name="No AWS Vault Profiles",
                message="aws-vault has no configured profiles — credentials are unmanaged",
                blocks_deploy=False,
                effort=Effort.LOW,
                fix_hint="Add profiles to aws-vault: aws-vault add <profile>",
            ))

        # Check for plaintext AWS credentials that should use aws-vault instead
        cred_files = self._scan_files(".aws/credentials", "**/.aws/credentials")
        for cred_file in cred_files:
            content = self._read_file(cred_file)
            if "aws_access_key_id" in content.lower() and "aws_secret_access_key" in content.lower():
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.HIGH,
                    category=Category.CLOUD,
                    file=str(cred_file.relative_to(self.target)) if cred_file.is_relative_to(self.target) else str(cred_file),
                    rule_id="aws-vault-plaintext-creds",
                    rule_name="Plaintext AWS Credentials",
                    message="Plaintext AWS credentials found — use aws-vault for secure credential storage",
                    blocks_deploy=True,
                    effort=Effort.LOW,
                    fix_hint="Migrate credentials to aws-vault and remove plaintext keys",
                ))

        return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=findings)
