"""Runner for scalene — CPU and memory profiler for Python."""

from __future__ import annotations

from pathlib import Path

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.scalene import ScaleneNormaliser
from viberapid.runners.base import AsyncToolRunner


class ScaleneRunner(AsyncToolRunner):
    """Run scalene to profile Python CPU and memory usage."""

    name = "scalene"
    requires_python = True

    def should_run(self) -> bool:
        entry = self.tool_config.get("entry")
        if not entry:
            self.skip_reason = (
                "no entry script configured — set tools.scalene.entry in .viberapid.yml"
            )
            return False

        entry_path = Path(self.target) / entry
        if not entry_path.exists():
            self.skip_reason = f"entry script not found: {entry}"
            return False

        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        entry = self.tool_config.get("entry")
        if not entry:
            return self._make_error_result("no entry script configured")

        profile_time = self.tool_config.get("profile_time_seconds", 10)
        bin_path = self.bin_path

        cmd = [
            bin_path,
            "--json",
            "--cpu-only",
            "--reduced-profile",
            "--profile-interval", str(profile_time),
            entry,
        ]

        data, stderr = self._exec_json(cmd, timeout=int(profile_time) + 30)

        if data is None:
            # scalene may write JSON to stderr or to a file; try to recover
            return self._make_error_result(
                f"scalene failed to produce JSON output. stderr: {stderr[:500]}"
            )

        normaliser = ScaleneNormaliser()
        findings = normaliser.normalise(data)

        # Extract summary metrics
        files_profiled = 0
        total_functions = 0
        if isinstance(data, dict):
            files = data.get("files", {})
            files_profiled = len(files)
            for file_data in files.values():
                lines = file_data.get("lines", [])
                total_functions += len(
                    {l.get("function") for l in lines if isinstance(l, dict) and l.get("function")}
                )

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "entry_script": entry,
                "profile_time_seconds": profile_time,
                "files_profiled": files_profiled,
                "functions_analysed": total_functions,
            },
        )
