"""kube-score runner — static analysis of Kubernetes object definitions."""

from __future__ import annotations

import json

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner


# Map kube-score grade to severity
_GRADE_SEVERITY = {
    "CRITICAL": Severity.CRITICAL,
    "WARNING": Severity.HIGH,
    "OK": Severity.INFO,
    "SKIPPED": Severity.INFO,
}


class KubeScoreRunner(AsyncToolRunner):
    name = "kube_score"
    requires_k8s = True

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "kube-score not installed"
            return False
        k8s_files = self._scan_files("*.yaml", "*.yml")
        if not k8s_files:
            self.skip_reason = "no Kubernetes YAML files found"
            return False
        return super().should_run()

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        yaml_files = self._scan_files("*.yaml", "*.yml")
        if not yaml_files:
            return ToolResult(tool=self.name, status=ToolStatus.SKIPPED)

        file_args = [str(f) for f in yaml_files]
        cmd = [self.bin_path, "score", "--output-format", "json"] + file_args
        result = self._exec(cmd, timeout=60)

        findings = []

        # kube-score outputs JSON array — may exit non-zero if issues found
        stdout = result.stdout.strip()
        if not stdout:
            if result.returncode != 0:
                return self._make_error_result(
                    f"kube-score failed: {result.stderr[:200]}"
                )
            return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=[])

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return self._make_error_result("kube-score returned invalid JSON")

        if not isinstance(data, list):
            data = [data]

        for scored_object in data:
            object_name = scored_object.get("object_name", "unknown")
            type_meta = scored_object.get("type_meta", {})
            kind = type_meta.get("kind", "unknown")
            file_name = scored_object.get("file_name", f"{kind}/{object_name}")

            checks = scored_object.get("checks", [])
            for check in checks:
                check_name = check.get("check", {}).get("name", "unknown")
                check_id = check.get("check", {}).get("id", check_name)
                comment = check.get("check", {}).get("comment", "")
                grade = check.get("grade", 0)

                # Grade: 10 = critical, 7 = warning, 1 = ok, 0 = skipped
                if grade == 10:
                    severity = Severity.CRITICAL
                    blocks = True
                elif grade == 7:
                    severity = Severity.HIGH
                    blocks = False
                elif grade == 5:
                    severity = Severity.MEDIUM
                    blocks = False
                elif grade == 1 or grade == 0:
                    continue  # Skip OK/SKIPPED
                else:
                    severity = Severity.MEDIUM
                    blocks = False

                # kube-score sometimes nests messages in "comments"
                comments = check.get("comments", [])
                if comments:
                    for c in comments:
                        path = c.get("path", "")
                        summary = c.get("summary", "")
                        description = c.get("description", "")
                        message = summary or description or comment or check_name
                        if path:
                            message = f"[{path}] {message}"

                        findings.append(Finding(
                            tool=self.name,
                            severity=severity,
                            category=Category.KUBERNETES,
                            file=file_name,
                            rule_id=f"kube-score-{check_id}",
                            rule_name=check_name,
                            message=f"{kind}/{object_name}: {message}",
                            blocks_deploy=blocks,
                            effort=Effort.LOW,
                            fix_hint=description or f"Address {check_name} for {kind}/{object_name}",
                            raw={"check": check, "object": object_name, "kind": kind},
                        ))
                else:
                    findings.append(Finding(
                        tool=self.name,
                        severity=severity,
                        category=Category.KUBERNETES,
                        file=file_name,
                        rule_id=f"kube-score-{check_id}",
                        rule_name=check_name,
                        message=f"{kind}/{object_name}: {comment or check_name}",
                        blocks_deploy=blocks,
                        effort=Effort.LOW,
                        fix_hint=f"Address {check_name} for {kind}/{object_name}",
                        raw={"check": check, "object": object_name, "kind": kind},
                    ))

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
        )
