"""Runner for pipdeptree — Python dependency tree analyser."""

from __future__ import annotations

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.pipdeptree import PipdeptreeNormaliser
from viberapid.runners.base import AsyncToolRunner


class PipdeptreeRunner(AsyncToolRunner):
    """Run pipdeptree to analyse the Python dependency tree."""

    name = "pipdeptree"
    requires_python = True

    def should_run(self) -> bool:
        if not self._file_exists("requirements.txt", "pyproject.toml", "setup.py", "setup.cfg"):
            self.skip_reason = "no Python project files found (requirements.txt, pyproject.toml, setup.py)"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        bin_path = self.bin_path

        cmd = [bin_path, "--json"]

        data, stderr = self._exec_json(cmd)

        if data is None:
            return self._make_error_result(
                f"pipdeptree failed to produce JSON output. stderr: {stderr[:500]}"
            )

        normaliser = PipdeptreeNormaliser()
        findings = normaliser.normalise(data)

        # Calculate metrics
        total_packages = 0
        max_depth = 0
        conflict_count = 0

        if isinstance(data, list):
            total_packages = len(data)
            for pkg in data:
                if isinstance(pkg, dict):
                    depth = _calc_depth(pkg)
                    max_depth = max(max_depth, depth)

        # Also run with --warn to detect version conflicts
        warn_cmd = [bin_path, "--warn", "all"]
        warn_result = self._exec(warn_cmd)
        if warn_result.stderr:
            conflict_count = warn_result.stderr.count("Warning")

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "total_packages": total_packages,
                "max_dependency_depth": max_depth,
                "version_conflicts": conflict_count,
            },
        )


def _calc_depth(pkg: dict, current: int = 0) -> int:
    """Calculate the maximum dependency depth for a package."""
    deps = pkg.get("dependencies", [])
    if not isinstance(deps, list) or not deps:
        return current

    max_child_depth = current
    for dep in deps:
        if isinstance(dep, dict):
            child_depth = _calc_depth(dep, current + 1)
            max_child_depth = max(max_child_depth, child_depth)

    return max_child_depth
