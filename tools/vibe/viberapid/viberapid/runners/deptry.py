"""Runner for deptry — detects unused, missing, and transitive Python dependencies."""

from __future__ import annotations

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.deptry import DeptryNormaliser
from viberapid.runners.base import AsyncToolRunner


class DeptryRunner(AsyncToolRunner):
    """Run deptry to find dependency issues in Python projects."""

    name = "deptry"
    requires_python = True

    def should_run(self) -> bool:
        if not self._file_exists("pyproject.toml", "requirements.txt", "setup.py", "setup.cfg"):
            self.skip_reason = "no Python project files found (pyproject.toml, requirements.txt, setup.py)"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        bin_path = self.bin_path

        cmd = [bin_path, ".", "--json-output", "-"]

        data, stderr = self._exec_json(cmd)

        # deptry exits non-zero when it finds issues, which is expected.
        # Only treat as error if there is no parseable output.
        if data is None:
            # deptry may output to a file instead of stdout; try the default output
            return self._make_error_result(
                f"deptry failed to produce JSON output. stderr: {stderr[:500]}"
            )

        normaliser = DeptryNormaliser()
        findings = normaliser.normalise(data)

        # Calculate metrics
        unused = 0
        missing = 0
        transitive = 0
        misplaced = 0

        if isinstance(data, list):
            for issue in data:
                if isinstance(issue, dict):
                    code = issue.get("error", {}).get("code", "") if isinstance(issue.get("error"), dict) else ""
                    if not code:
                        code = issue.get("code", "")
                    if code == "DEP002":
                        unused += 1
                    elif code == "DEP001":
                        missing += 1
                    elif code == "DEP003":
                        transitive += 1
                    elif code == "DEP004":
                        misplaced += 1

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "unused_dependencies": unused,
                "missing_dependencies": missing,
                "transitive_dependencies": transitive,
                "misplaced_dependencies": misplaced,
                "total_issues": len(findings),
            },
        )
