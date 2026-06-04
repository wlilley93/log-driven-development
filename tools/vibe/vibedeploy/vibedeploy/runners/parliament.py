"""parliament runner — lint AWS IAM policies for misconfigurations."""

from __future__ import annotations

import json
from pathlib import Path

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner

_ISSUE_SEVERITY = {
    "CRITICAL": Severity.CRITICAL,
    "HIGH": Severity.HIGH,
    "MEDIUM": Severity.MEDIUM,
    "LOW": Severity.LOW,
    "INFO": Severity.INFO,
    "WARNING": Severity.HIGH,
    "ERROR": Severity.CRITICAL,
}


class ParliamentRunner(AsyncToolRunner):
    name = "parliament"
    requires_cloud = True

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "parliament not installed"
            return False
        return super().should_run()

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        findings: list[Finding] = []

        # Scan for IAM policy JSON files in the project
        policy_files = self._scan_files("*policy*.json", "*iam*.json", "*role*.json")
        if not policy_files:
            # Try scanning common IaC locations
            for subdir in ("iam", "policies", "terraform", "cloudformation"):
                target = Path(self.target) / subdir
                if target.exists():
                    policy_files.extend(target.rglob("*.json"))

        if not policy_files:
            return ToolResult(tool=self.name, status=ToolStatus.SKIPPED)

        for policy_file in policy_files:
            try:
                content = policy_file.read_text(errors="replace")
                data = json.loads(content)
            except (json.JSONDecodeError, OSError):
                continue

            # Only lint files that look like IAM policies
            if not isinstance(data, dict):
                continue
            if "Statement" not in data and "Version" not in data:
                continue

            rel_path = str(policy_file.relative_to(self.target))

            # Run parliament on the policy file
            cmd = [self.bin_path, "--string", content]
            result = self._exec(cmd, timeout=30)

            if result.stdout.strip():
                for line in result.stdout.strip().split("\n"):
                    line = line.strip()
                    if not line:
                        continue

                    # Parliament output format: "ISSUE_TYPE - TITLE - DETAIL"
                    # or JSON-formatted output
                    try:
                        issue = json.loads(line)
                        self._process_json_issue(issue, rel_path, findings)
                    except json.JSONDecodeError:
                        self._process_text_issue(line, rel_path, findings)

        status = ToolStatus.SUCCESS if not findings else ToolStatus.PARTIAL
        return ToolResult(tool=self.name, status=status, findings=findings)

    def _process_json_issue(
        self, issue: dict, file_path: str, findings: list[Finding]
    ) -> None:
        """Process a JSON-formatted parliament issue."""
        issue_type = issue.get("issue", issue.get("type", "unknown"))
        title = issue.get("title", issue_type)
        detail = issue.get("detail", issue.get("message", ""))
        sev_text = issue.get("severity", "MEDIUM").upper()

        severity = _ISSUE_SEVERITY.get(sev_text, Severity.MEDIUM)
        blocks = severity in (Severity.CRITICAL, Severity.HIGH)

        findings.append(Finding(
            tool=self.name,
            severity=severity,
            category=Category.CLOUD,
            file=file_path,
            rule_id=f"parliament-{issue_type}",
            rule_name=title,
            message=detail or f"IAM policy issue: {title}",
            blocks_deploy=blocks,
            effort=Effort.MEDIUM,
            fix_hint="Review and fix the IAM policy according to AWS best practices",
            raw=issue,
        ))

    def _process_text_issue(
        self, line: str, file_path: str, findings: list[Finding]
    ) -> None:
        """Process a text-formatted parliament issue."""
        # Common format: "ISSUE_TYPE - TITLE - DETAIL"
        parts = [p.strip() for p in line.split(" - ", 2)]
        issue_type = parts[0] if parts else "unknown"
        title = parts[1] if len(parts) > 1 else issue_type
        detail = parts[2] if len(parts) > 2 else line

        # Infer severity from issue type keywords
        severity = Severity.MEDIUM
        if any(kw in issue_type.upper() for kw in ("RESOURCE_STAR", "PRIVILEGE_ESCALATION", "CREDENTIALS")):
            severity = Severity.CRITICAL
        elif any(kw in issue_type.upper() for kw in ("WILDCARD", "OVERLY_PERMISSIVE")):
            severity = Severity.HIGH

        blocks = severity in (Severity.CRITICAL, Severity.HIGH)

        findings.append(Finding(
            tool=self.name,
            severity=severity,
            category=Category.CLOUD,
            file=file_path,
            rule_id=f"parliament-{issue_type.lower().replace(' ', '_')}",
            rule_name=title,
            message=detail,
            blocks_deploy=blocks,
            effort=Effort.MEDIUM,
            fix_hint="Review and restrict the IAM policy permissions",
        ))
