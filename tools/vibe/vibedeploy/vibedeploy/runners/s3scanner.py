"""s3scanner runner — detect publicly accessible S3 buckets."""

from __future__ import annotations

import json

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner


class S3ScannerRunner(AsyncToolRunner):
    name = "s3scanner"
    requires_cloud = True

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "s3scanner not installed"
            return False
        return super().should_run()

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        findings: list[Finding] = []

        # Build bucket list from config or scan for bucket references in code
        buckets = self._discover_buckets()
        if not buckets:
            return ToolResult(tool=self.name, status=ToolStatus.SKIPPED)

        for bucket in buckets:
            cmd = [self.bin_path, "scan", "--bucket", bucket, "--json"]
            result = self._exec(cmd, timeout=60)

            if result.stdout.strip():
                for line in result.stdout.strip().split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        self._process_bucket_result(data, bucket, findings)
                    except (json.JSONDecodeError, Exception):
                        continue

        status = ToolStatus.SUCCESS if not findings else ToolStatus.PARTIAL
        return ToolResult(tool=self.name, status=status, findings=findings)

    def _discover_buckets(self) -> list[str]:
        """Discover S3 bucket names from config or source code."""
        buckets: list[str] = []

        # Check tool config for explicit bucket list
        configured = self.tool_config.get("buckets", [])
        if isinstance(configured, list):
            buckets.extend(configured)

        if buckets:
            return buckets

        # Scan source for S3 bucket references
        import re
        s3_pattern = re.compile(
            r'(?:s3://|\.s3\.amazonaws\.com|S3_BUCKET["\s:=]+["\']?)([a-zA-Z0-9.\-_]+)',
            re.IGNORECASE,
        )
        env_pattern = re.compile(
            r'(?:S3_BUCKET|AWS_BUCKET|BUCKET_NAME)["\s:=]+["\']?([a-zA-Z0-9.\-_]+)',
            re.IGNORECASE,
        )

        # Scan common config files
        scan_patterns = ["*.env*", "*.yml", "*.yaml", "*.json", "*.tf", "*.py", "*.js", "*.ts"]
        for pat in scan_patterns:
            for f in self._scan_files(pat):
                try:
                    content = f.read_text(errors="replace")
                    for match in s3_pattern.finditer(content):
                        bucket = match.group(1).strip("'\"")
                        if bucket and bucket not in buckets:
                            buckets.append(bucket)
                    for match in env_pattern.finditer(content):
                        bucket = match.group(1).strip("'\"")
                        if bucket and bucket not in buckets:
                            buckets.append(bucket)
                except OSError:
                    continue

        return buckets[:20]  # Cap at 20 buckets to avoid excessive scanning

    def _process_bucket_result(
        self, data: dict, bucket: str, findings: list[Finding]
    ) -> None:
        """Process a single s3scanner result for a bucket."""
        bucket_name = data.get("bucket", data.get("name", bucket))
        exists = data.get("exists", data.get("bucket_exists", True))
        is_public = data.get("public", data.get("is_public", False))
        permissions = data.get("permissions", data.get("acl", {}))
        objects_listed = data.get("objects_listed", data.get("list_objects", False))

        if not exists:
            return

        if is_public or objects_listed:
            # Public S3 with sensitive data is CRITICAL and blocks deploy
            findings.append(Finding(
                tool=self.name,
                severity=Severity.CRITICAL,
                category=Category.CLOUD,
                file=f"s3://{bucket_name}",
                rule_id="s3-public-bucket",
                rule_name="Public S3 Bucket",
                message=f"S3 bucket '{bucket_name}' is publicly accessible — data may be exposed",
                blocks_deploy=True,
                effort=Effort.LOW,
                fix_hint=(
                    f"Block public access on S3 bucket '{bucket_name}': "
                    "aws s3api put-public-access-block --bucket <name> "
                    "--public-access-block-configuration "
                    "BlockPublicAcls=true,IgnorePublicAcls=true,"
                    "BlockPublicPolicy=true,RestrictPublicBuckets=true"
                ),
                docs_url="https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-control-block-public-access.html",
            ))

        # Check for permissive ACLs
        if isinstance(permissions, dict):
            for grantee, perms in permissions.items():
                if "AllUsers" in str(grantee) or "AuthenticatedUsers" in str(grantee):
                    findings.append(Finding(
                        tool=self.name,
                        severity=Severity.HIGH,
                        category=Category.CLOUD,
                        file=f"s3://{bucket_name}",
                        rule_id="s3-permissive-acl",
                        rule_name="Permissive S3 ACL",
                        message=f"S3 bucket '{bucket_name}' has permissive ACL granting access to {grantee}",
                        blocks_deploy=True,
                        effort=Effort.LOW,
                        fix_hint="Remove public/authenticated-users ACL grants from the bucket",
                    ))
