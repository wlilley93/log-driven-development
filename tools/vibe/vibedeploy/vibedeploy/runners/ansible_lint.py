"""ansible-lint runner — lint Ansible playbooks and roles."""

from __future__ import annotations

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.ansible_lint import AnsibleLintNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class AnsibleLintRunner(AsyncToolRunner):
    name = "ansible_lint"

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "ansible-lint not installed"
            return False
        has_ansible = (
            self._file_exists("playbook.yml", "playbook.yaml", "ansible.cfg", "site.yml", "site.yaml")
            or bool(self._scan_files("playbook*.yml"))
            or bool(self._scan_files("playbook*.yaml"))
            or self._file_exists("roles")
        )
        if not has_ansible:
            self.skip_reason = "no Ansible playbooks or ansible.cfg found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        cmd = [self.bin_path, "--format", "json", "-q", self.target]
        data, stderr = self._exec_json(cmd)

        if data is None:
            # ansible-lint exits non-zero when findings exist
            result = self._exec(cmd)
            import json
            try:
                data = json.loads(result.stdout)
            except (json.JSONDecodeError, ValueError):
                return self._make_error_result(f"ansible-lint failed: {stderr[:200] if stderr else 'no output'}")

        normaliser = AnsibleLintNormaliser()
        findings = normaliser.normalise(data)
        status = ToolStatus.SUCCESS if not findings else ToolStatus.PARTIAL
        return ToolResult(tool=self.name, status=status, findings=findings)
