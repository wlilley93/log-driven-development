"""Runner for stylelint — performance-focused CSS linting."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.stylelint_perf import StylelintPerfNormaliser
from viberapid.runners.base import AsyncToolRunner

# Performance-focused stylelint config that flags expensive CSS patterns.
# These rules target selectors and properties known to hurt rendering performance.
_PERF_CONFIG = {
    "rules": {
        "selector-max-compound-selectors": [3, {"severity": "warning"}],
        "selector-max-id": [0, {"severity": "warning"}],
        "selector-max-universal": [0, {"severity": "warning"}],
        "selector-no-qualifying-type": [True, {"severity": "warning"}],
        "max-nesting-depth": [3, {"severity": "warning"}],
        "selector-max-specificity": ["0,4,0", {"severity": "warning"}],
        "no-descending-specificity": [True, {"severity": "warning"}],
        "declaration-no-important": [True, {"severity": "warning"}],
    }
}


class StylelintPerfRunner(AsyncToolRunner):
    """Run stylelint with a performance-focused configuration to flag
    expensive CSS selectors such as deep nesting, universal selectors,
    ID selectors, and overly specific rules."""

    name = "stylelint-perf"
    requires_node = True

    def should_run(self) -> bool:
        css_files = self._glob_files("*.css", "*.scss", "*.less")
        css_files = [
            f for f in css_files
            if "node_modules" not in str(f)
            and ".next" not in str(f)
            and "vendor" not in str(f)
        ]
        if not css_files:
            self.skip_reason = "no CSS/SCSS/LESS files found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        css_files = self._glob_files("*.css", "*.scss", "*.less")
        css_files = [
            f for f in css_files
            if "node_modules" not in str(f)
            and ".next" not in str(f)
            and "vendor" not in str(f)
        ]

        if not css_files:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS,
                findings=[],
                metrics={"css_files_checked": 0},
            )

        npx = self._npx_path()

        with tempfile.TemporaryDirectory(prefix="viberapid-stylelint-") as tmp_dir:
            # Write the performance-focused config
            config_path = Path(tmp_dir) / ".stylelintrc.json"
            config_path.write_text(json.dumps(_PERF_CONFIG))

            # Build file list (limit to 50 files)
            file_paths = [str(f) for f in css_files[:50]]

            cmd = [
                npx, "stylelint",
                *file_paths,
                "--config", str(config_path),
                "--formatter", "json",
                "--allow-empty-input",
            ]

            result = self._exec(cmd, timeout=60)

            # stylelint returns exit code 2 for lint errors, which is expected
            stdout = result.stdout.strip()
            if not stdout:
                return ToolResult(
                    tool=self.name,
                    status=ToolStatus.SUCCESS,
                    findings=[],
                    metrics={"css_files_checked": len(file_paths)},
                )

            try:
                data = json.loads(stdout)
            except json.JSONDecodeError:
                return self._make_error_result(
                    f"stylelint produced non-JSON output. stderr: {result.stderr.strip()[:500]}"
                )

        # Convert absolute paths to relative
        for entry in data:
            if isinstance(entry, dict) and "source" in entry:
                try:
                    entry["source"] = str(
                        Path(entry["source"]).relative_to(self.target)
                    )
                except ValueError:
                    pass  # Keep absolute if not under target

        normaliser = StylelintPerfNormaliser()
        findings = normaliser.normalise(data)

        total_warnings = sum(
            len(entry.get("warnings", []))
            for entry in data
            if isinstance(entry, dict)
        )

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "css_files_checked": len(file_paths),
                "total_warnings": total_warnings,
            },
        )
