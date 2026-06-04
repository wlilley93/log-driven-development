"""Runner for npm-check — finds outdated, unused, and mismatched packages."""

from __future__ import annotations

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.npm_check import NpmCheckNormaliser
from viberapid.runners.base import AsyncToolRunner


class NpmCheckRunner(AsyncToolRunner):
    """Run npm-check to find outdated, unused, and mismatched packages.

    npm-check analyses the project's package.json and node_modules to detect:
    - Packages with newer versions available
    - Packages that are installed but not used in the codebase
    - Packages where the installed version mismatches package.json
    """

    name = "npm-check"
    requires_node = True

    def should_run(self) -> bool:
        if not self._file_exists("package.json"):
            self.skip_reason = "no package.json found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        npx = self._npx_path()

        # npm-check exits with code 1 when issues are found, so we
        # cannot rely on returncode for success/failure
        cmd = [npx, "npm-check", "--json", "--skip-unused"]
        data_with_unused, stderr_with_unused = self._exec_json(
            [npx, "npm-check", "--json"]
        )

        # If the full run failed, try without unused detection
        data = data_with_unused
        stderr = stderr_with_unused

        if data is None:
            # npm-check may exit non-zero and still produce JSON on stdout.
            # Try running the command and manually parsing.
            result = self._exec([npx, "npm-check", "--json"])
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()

            if stdout:
                import json
                try:
                    data = json.loads(stdout)
                except json.JSONDecodeError:
                    pass

        if data is None:
            return self._make_error_result(
                f"npm-check failed to produce JSON output. stderr: {stderr[:500]}"
            )

        # npm-check --json returns an array of package objects
        if not isinstance(data, list):
            # Some versions wrap in an object
            if isinstance(data, dict):
                data = data.get("packages", data.get("results", []))
            if not isinstance(data, list):
                return self._make_error_result(
                    "npm-check returned unexpected data format"
                )

        normaliser = NpmCheckNormaliser()
        findings = normaliser.normalise(data)

        # Compute metrics
        unused_count = sum(
            1 for p in data
            if isinstance(p, dict) and p.get("unused", False)
        )
        outdated_count = sum(
            1 for p in data
            if isinstance(p, dict) and p.get("latest")
            and p.get("latest") != p.get("installed")
            and not p.get("unused", False)
        )
        mismatch_count = sum(
            1 for p in data
            if isinstance(p, dict) and p.get("mismatch", False)
        )
        major_count = sum(
            1 for p in data
            if isinstance(p, dict) and p.get("bump") == "major"
        )

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "packages_checked": len(data),
                "unused_packages": unused_count,
                "outdated_packages": outdated_count,
                "mismatched_packages": mismatch_count,
                "major_updates_available": major_count,
                "total_findings": len(findings),
            },
        )
