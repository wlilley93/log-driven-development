"""Runner for jscpd — copy/paste detector for source code."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.jscpd import JscpdNormaliser
from viberapid.runners.base import AsyncToolRunner


class JscpdRunner(AsyncToolRunner):
    """Run jscpd to detect duplicated code blocks."""

    name = "jscpd"
    requires_node = True

    def should_run(self) -> bool:
        if not self._file_exists("package.json"):
            self.skip_reason = "no package.json found"
            return False
        # Check there are actual source files to scan
        source_files = self._glob_files("*.ts", "*.tsx", "*.js", "*.jsx", "*.py")
        if not source_files:
            self.skip_reason = "no source files found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        npx = self._npx_path()

        with tempfile.TemporaryDirectory(prefix="viberapid-jscpd-") as tmp_dir:
            cmd = [
                npx, "jscpd",
                "--reporters", "json",
                "--output", tmp_dir,
                self.target,
            ]

            result = self._exec(cmd)

            # jscpd writes to <output>/jscpd-report.json
            report_path = Path(tmp_dir) / "jscpd-report.json"
            if not report_path.exists():
                # Some versions write to a subdirectory
                alt_path = Path(tmp_dir) / "report" / "jscpd-report.json"
                if alt_path.exists():
                    report_path = alt_path

            if not report_path.exists():
                return self._make_error_result(
                    f"jscpd did not produce a report file. "
                    f"stderr: {result.stderr[:500]}"
                )

            try:
                data = json.loads(report_path.read_text())
            except (json.JSONDecodeError, OSError) as exc:
                return self._make_error_result(f"Failed to parse jscpd report: {exc}")

        normaliser = JscpdNormaliser()
        findings = normaliser.normalise(data)

        stats = data.get("statistics", {}).get("total", {})

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "duplication_pct": stats.get("percentage", 0),
                "duplicated_lines": stats.get("duplicatedLines", 0),
                "clones": stats.get("clones", 0),
            },
        )
