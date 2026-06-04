"""kubectl-neat runner — clean up Kubernetes YAML by removing clutter fields."""

from __future__ import annotations

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner


class KubectlNeatRunner(AsyncToolRunner):
    name = "kubectl_neat"
    requires_k8s = True

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "kubectl-neat not installed"
            return False
        return super().should_run()

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        yaml_files = self._scan_files("*.yaml", "*.yml")
        if not yaml_files:
            return ToolResult(tool=self.name, status=ToolStatus.SKIPPED)

        findings = []

        for yaml_file in yaml_files:
            try:
                original_content = yaml_file.read_text(errors="replace")
                rel_path = str(yaml_file.relative_to(self.target))

                # Run kubectl-neat on the file to get cleaned output
                result = self._exec(
                    [self.bin_path, "-f", str(yaml_file)],
                    timeout=30,
                )

                if result.returncode != 0:
                    continue

                cleaned_content = result.stdout

                if not cleaned_content.strip():
                    continue

                # Compare line counts to gauge clutter
                original_lines = len(original_content.strip().split("\n"))
                cleaned_lines = len(cleaned_content.strip().split("\n"))
                removed_lines = original_lines - cleaned_lines

                if removed_lines > 0:
                    clutter_pct = (removed_lines / original_lines) * 100 if original_lines > 0 else 0

                    # Only report if significant clutter detected
                    if clutter_pct >= 10:
                        findings.append(Finding(
                            tool=self.name,
                            severity=Severity.INFO,
                            category=Category.KUBERNETES,
                            file=rel_path,
                            rule_id="kubectl-neat-clutter",
                            rule_name="YAML Clutter",
                            message=(
                                f"{rel_path} contains {removed_lines} unnecessary lines "
                                f"({clutter_pct:.0f}% clutter) — status fields, "
                                f"managedFields, or default values that can be removed"
                            ),
                            blocks_deploy=False,
                            effort=Effort.TRIVIAL,
                            fix_hint=f"Run 'kubectl neat -f {rel_path}' to clean up the manifest",
                            fix_command=f"kubectl neat -f {rel_path} > {rel_path}.clean && mv {rel_path}.clean {rel_path}",
                            raw={
                                "original_lines": original_lines,
                                "cleaned_lines": cleaned_lines,
                                "removed_lines": removed_lines,
                                "clutter_pct": round(clutter_pct, 1),
                            },
                        ))
            except Exception:
                continue

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
        )
