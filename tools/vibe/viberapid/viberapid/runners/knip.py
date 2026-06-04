"""Runner for knip — finds unused files, exports, and dependencies."""

from __future__ import annotations

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.knip import KnipNormaliser
from viberapid.runners.base import AsyncToolRunner


class KnipRunner(AsyncToolRunner):
    """Run knip to detect unused code and dependencies."""

    name = "knip"
    requires_node = True

    def should_run(self) -> bool:
        if not self._file_exists("package.json"):
            self.skip_reason = "no package.json found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        npx = self._npx_path()
        cmd = [npx, "knip", "--reporter", "json"]

        data, stderr = self._exec_json(cmd)

        if data is None:
            # knip exits non-zero when it finds issues; try parsing stderr
            return self._make_error_result(
                f"knip failed to produce JSON output. stderr: {stderr[:500]}"
            )

        normaliser = KnipNormaliser()
        findings = normaliser.normalise(data)

        unused_files = len(data.get("files", []))
        issue_count = len(data.get("issues", []))

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "unused_files": unused_files,
                "issues_files": issue_count,
                "total_findings": len(findings),
            },
        )
