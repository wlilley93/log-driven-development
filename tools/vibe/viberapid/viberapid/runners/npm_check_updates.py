"""Runner for npm-check-updates — finds outdated npm dependencies."""

from __future__ import annotations

import json
from pathlib import Path

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.npm_check_updates import NpmCheckUpdatesNormaliser
from viberapid.runners.base import AsyncToolRunner


class NpmCheckUpdatesRunner(AsyncToolRunner):
    """Run npm-check-updates to find outdated dependencies."""

    name = "npm-check-updates"
    requires_node = True

    def should_run(self) -> bool:
        if not self._file_exists("package.json"):
            self.skip_reason = "no package.json found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        npx = self._npx_path()
        cmd = [npx, "npm-check-updates", "--jsonUpgraded"]

        data, stderr = self._exec_json(cmd)

        if data is None:
            # ncu exits 0 even when nothing to update; empty output means up-to-date
            if "All dependencies match" in (stderr or ""):
                return ToolResult(
                    tool=self.name,
                    status=ToolStatus.SUCCESS,
                    findings=[],
                    metrics={"outdated_packages": 0},
                )
            return self._make_error_result(
                f"npm-check-updates failed to produce JSON output. stderr: {stderr[:500]}"
            )

        # Read current versions from package.json
        pkg_path = Path(self.target) / "package.json"
        current_versions: dict[str, str] = {}
        try:
            pkg_data = json.loads(pkg_path.read_text())
            current_versions.update(pkg_data.get("dependencies", {}))
            current_versions.update(pkg_data.get("devDependencies", {}))
        except (json.JSONDecodeError, OSError):
            pass

        enriched_data = {
            "upgrades": data if isinstance(data, dict) else {},
            "current": current_versions,
        }

        normaliser = NpmCheckUpdatesNormaliser()
        findings = normaliser.normalise(enriched_data)

        upgrades = data if isinstance(data, dict) else {}
        major_count = 0
        minor_count = 0
        patch_count = 0
        for finding in findings:
            update_type = finding.raw.get("update_type", "unknown")
            if update_type == "major":
                major_count += 1
            elif update_type == "minor":
                minor_count += 1
            else:
                patch_count += 1

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "outdated_packages": len(upgrades),
                "major_updates": major_count,
                "minor_updates": minor_count,
                "patch_updates": patch_count,
            },
        )
