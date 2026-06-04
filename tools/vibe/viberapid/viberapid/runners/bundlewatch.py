"""Runner for bundlewatch — checks bundle sizes against configured limits."""

from __future__ import annotations

import json
from pathlib import Path

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.bundlewatch import BundlewatchNormaliser
from viberapid.runners.base import AsyncToolRunner


class BundlewatchRunner(AsyncToolRunner):
    """Run bundlewatch to check bundle file sizes against configured budgets.

    bundlewatch reads configuration from package.json (bundlewatch key)
    or a .bundlewatch.config.js file and checks that output files do not
    exceed the specified maxSize thresholds.
    """

    name = "bundlewatch"
    requires_node = True

    def should_run(self) -> bool:
        if not self._file_exists("package.json"):
            self.skip_reason = "no package.json found"
            return False

        # bundlewatch needs configuration
        if self._file_exists(".bundlewatch.config.js", ".bundlewatch.config.cjs"):
            return True

        # Check package.json for bundlewatch config
        pkg_path = Path(self.target) / "package.json"
        try:
            pkg_data = json.loads(pkg_path.read_text())
            if "bundlewatch" in pkg_data:
                return True
        except (json.JSONDecodeError, OSError):
            pass

        self.skip_reason = (
            "no bundlewatch configuration found "
            "(.bundlewatch.config.js or bundlewatch key in package.json)"
        )
        return False

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        npx = self._npx_path()
        cmd = [npx, "bundlewatch", "--ci"]

        # bundlewatch may output JSON to stdout when using --ci
        data, stderr = self._exec_json(cmd)

        if data is None:
            # Some versions of bundlewatch write non-JSON output to stdout.
            # Try running with explicit --json flag (not all versions support it).
            cmd_json = [npx, "bundlewatch", "--ci", "--json"]
            data, stderr = self._exec_json(cmd_json)

        if data is None:
            # Try to parse structured output from stderr as some versions
            # output JSON to stderr
            if stderr:
                try:
                    data = json.loads(stderr)
                except json.JSONDecodeError:
                    pass

        if data is None:
            return self._make_error_result(
                f"bundlewatch failed to produce JSON output. stderr: {stderr[:500]}"
            )

        normaliser = BundlewatchNormaliser()
        findings = normaliser.normalise(data)

        # Compute metrics
        files = []
        if isinstance(data, dict):
            files = data.get("files", data.get("results", []))
            overall_status = data.get("status", "unknown")
        elif isinstance(data, list):
            files = data
            overall_status = "unknown"
        else:
            overall_status = "unknown"

        pass_count = sum(
            1 for f in files
            if isinstance(f, dict) and f.get("status") == "pass"
        )
        fail_count = sum(
            1 for f in files
            if isinstance(f, dict) and f.get("status") == "fail"
        )

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "files_checked": len(files),
                "pass_count": pass_count,
                "fail_count": fail_count,
                "overall_status": overall_status,
            },
        )
