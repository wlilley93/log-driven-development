"""Runner for depcheck — finds unused and missing npm dependencies."""

from __future__ import annotations

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.depcheck import DepcheckNormaliser
from viberapid.runners.base import AsyncToolRunner


class DepcheckRunner(AsyncToolRunner):
    """Run depcheck to detect unused and missing dependencies."""

    name = "depcheck"
    requires_node = True

    def should_run(self) -> bool:
        if not self._file_exists("package.json"):
            self.skip_reason = "no package.json found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        npx = self._npx_path()
        cmd = [npx, "depcheck", "--json"]

        data, stderr = self._exec_json(cmd)

        if data is None:
            return self._make_error_result(
                f"depcheck failed to produce JSON output. stderr: {stderr[:500]}"
            )

        normaliser = DepcheckNormaliser()
        findings = normaliser.normalise(data)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "unused_dependencies": len(data.get("dependencies", [])),
                "unused_dev_dependencies": len(data.get("devDependencies", [])),
                "missing_dependencies": len(data.get("missing", {})),
            },
        )
