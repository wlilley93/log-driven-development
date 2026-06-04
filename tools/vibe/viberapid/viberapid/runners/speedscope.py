"""Runner for speedscope — flamegraph viewer that ingests profiler outputs."""

from __future__ import annotations

import json
from pathlib import Path

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.speedscope import SpeedscopeNormaliser
from viberapid.runners.base import AsyncToolRunner


class SpeedscopeRunner(AsyncToolRunner):
    """Import and analyse speedscope JSON profile files from various profilers.

    speedscope is primarily a viewer, but its JSON format is a common interchange
    format for profiler data (py-spy, node --prof, Chrome DevTools). This runner
    reads existing speedscope JSON files and normalises their data into findings.
    """

    name = "speedscope"
    requires_node = True

    def should_run(self) -> bool:
        profile_path = self.tool_config.get("profile")
        profile_dir = self.tool_config.get("profile_dir")

        if not profile_path and not profile_dir:
            # Auto-detect: look for speedscope JSON files in the project
            found = self._glob_files(
                "*.speedscope.json", "*.cpuprofile",
                "**/.clinic/**/*.json", "**/profiles/*.json",
            )
            if not found:
                self.skip_reason = (
                    "no profile file configured and no speedscope JSON files found — "
                    "set tools.speedscope.profile or tools.speedscope.profile_dir "
                    "in .viberapid.yml"
                )
                return False
            return True

        if profile_path:
            path = Path(self.target) / profile_path
            if not path.exists():
                self.skip_reason = f"profile file not found: {profile_path}"
                return False

        if profile_dir:
            dir_path = Path(self.target) / profile_dir
            if not dir_path.exists():
                self.skip_reason = f"profile directory not found: {profile_dir}"
                return False

        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        profile_files = self._collect_profile_files()

        if not profile_files:
            return self._make_error_result("no speedscope-compatible profile files found")

        all_findings = []
        profiles_parsed = 0

        normaliser = SpeedscopeNormaliser()

        for profile_file in profile_files:
            try:
                with open(profile_file) as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                continue

            findings = normaliser.normalise(data)
            all_findings.extend(findings)
            profiles_parsed += 1

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS if profiles_parsed > 0 else ToolStatus.PARTIAL,
            findings=all_findings,
            metrics={
                "profile_files_found": len(profile_files),
                "profiles_parsed": profiles_parsed,
                "hotspots_found": len(all_findings),
            },
        )

    def _collect_profile_files(self) -> list[Path]:
        """Collect all speedscope-compatible profile files."""
        profile_path = self.tool_config.get("profile")
        profile_dir = self.tool_config.get("profile_dir")

        files: list[Path] = []

        if profile_path:
            path = Path(self.target) / profile_path
            if path.exists():
                files.append(path)

        if profile_dir:
            dir_path = Path(self.target) / profile_dir
            if dir_path.exists():
                for pattern in ("*.json", "*.cpuprofile", "*.speedscope.json"):
                    files.extend(dir_path.glob(pattern))

        if not files:
            # Auto-detect
            files = self._glob_files(
                "*.speedscope.json", "*.cpuprofile",
            )
            # Limit to avoid processing too many files
            files = files[:10]

        return files
