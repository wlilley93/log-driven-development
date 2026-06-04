"""npm_audit_prod runner — audit npm production dependencies for vulnerabilities."""

from __future__ import annotations

import json
import shutil

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.npm_audit_prod import NpmAuditProdNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class NpmAuditProdRunner(AsyncToolRunner):
    name = "npm_audit_prod"

    def should_run(self) -> bool:
        if not shutil.which("npm"):
            self.skip_reason = "npm not installed"
            return False
        if not self._file_exists("package-lock.json"):
            self.skip_reason = "no package-lock.json found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        cmd = ["npm", "audit", "--production", "--json"]

        try:
            result = self._exec(cmd, timeout=self.config.timeout * 2)
        except Exception as e:
            return self._make_error_result(f"npm audit execution failed: {e}")

        if result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                normaliser = NpmAuditProdNormaliser()
                findings = normaliser.normalise(data)
                return ToolResult(
                    tool=self.name,
                    status=ToolStatus.SUCCESS,
                    findings=findings,
                )
            except json.JSONDecodeError:
                pass

        # npm audit returns various exit codes for vulnerability levels
        if result.returncode not in (0, 1, 2):
            stderr = result.stderr[:300] if result.stderr else "unknown error"
            return self._make_error_result(
                f"npm audit exited with code {result.returncode}: {stderr}"
            )

        return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=[])
