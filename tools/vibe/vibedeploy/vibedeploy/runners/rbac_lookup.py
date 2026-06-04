"""rbac-lookup runner — audit Kubernetes RBAC for overly permissive roles."""

from __future__ import annotations

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner


class RbacLookupRunner(AsyncToolRunner):
    name = "rbac_lookup"
    requires_k8s = True

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "rbac-lookup not installed"
            return False
        return super().should_run()

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        cmd = [self.bin_path, "--output", "wide"]
        result = self._exec(cmd, timeout=60)

        if result.returncode != 0:
            return self._make_error_result(
                f"rbac-lookup failed: {result.stderr[:200]}"
            )

        findings = []
        output = result.stdout.strip()

        if not output:
            return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=[])

        # Parse tabular output: SUBJECT  SCOPE  NAMESPACE  ROLE
        overly_permissive_roles = {"cluster-admin", "admin", "edit"}
        wildcard_indicators = {"*"}

        for line in output.split("\n"):
            line = line.strip()
            if not line or line.startswith("SUBJECT"):
                continue

            parts = line.split()
            if len(parts) < 3:
                continue

            subject = parts[0]
            scope = parts[1] if len(parts) > 1 else ""
            role = parts[-1] if len(parts) > 2 else ""

            # Flag cluster-admin bindings
            if role.lower() in overly_permissive_roles:
                severity = Severity.HIGH if role.lower() == "cluster-admin" else Severity.MEDIUM
                findings.append(Finding(
                    tool=self.name,
                    severity=severity,
                    category=Category.KUBERNETES,
                    file=f"rbac/{subject}",
                    rule_id=f"rbac-overly-permissive-{role.lower()}",
                    rule_name=f"Overly Permissive Role: {role}",
                    message=(
                        f"Subject '{subject}' has '{role}' role "
                        f"({scope} scope) — consider least-privilege"
                    ),
                    blocks_deploy=False,
                    effort=Effort.MEDIUM,
                    fix_hint=(
                        f"Replace '{role}' with a more restrictive role for '{subject}'. "
                        "Use custom RBAC roles that grant only the permissions needed."
                    ),
                    raw={"subject": subject, "scope": scope, "role": role},
                ))

            # Flag wildcard subjects or unusual patterns
            if any(w in subject for w in wildcard_indicators):
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.CRITICAL,
                    category=Category.KUBERNETES,
                    file=f"rbac/{subject}",
                    rule_id="rbac-wildcard-subject",
                    rule_name="Wildcard RBAC Subject",
                    message=f"Wildcard subject '{subject}' with role '{role}' — extremely permissive",
                    blocks_deploy=True,
                    effort=Effort.MEDIUM,
                    fix_hint="Remove wildcard RBAC bindings and assign roles to specific subjects",
                    raw={"subject": subject, "scope": scope, "role": role},
                ))

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
        )
