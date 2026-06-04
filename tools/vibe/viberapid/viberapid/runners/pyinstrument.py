"""Runner for pyinstrument — statistical profiler for Python call trees."""

from __future__ import annotations

from pathlib import Path

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.pyinstrument import PyinstrumentNormaliser
from viberapid.runners.base import AsyncToolRunner


class PyinstrumentRunner(AsyncToolRunner):
    """Run pyinstrument to identify slow function calls in the call tree."""

    name = "pyinstrument"
    requires_python = True

    def should_run(self) -> bool:
        entry = self.tool_config.get("entry")
        if not entry:
            self.skip_reason = (
                "no entry script configured — set tools.pyinstrument.entry in .viberapid.yml"
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

        bin_path = self.bin_path

        cmd = [
            bin_path,
            "--renderer", "json",
            entry,
        ]

        data, stderr = self._exec_json(cmd, timeout=60)

        if data is None:
            return self._make_error_result(
                f"pyinstrument failed to produce JSON output. stderr: {stderr[:500]}"
            )

        normaliser = PyinstrumentNormaliser()
        findings = normaliser.normalise(data)

        # Extract top-level metrics
        total_duration = 0.0
        if isinstance(data, dict):
            root_frame = data.get("root_frame", data)
            total_duration = _safe_float(root_frame.get("time", 0))

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "entry_script": entry,
                "total_duration_seconds": round(total_duration, 3),
                "slow_calls_found": len(findings),
            },
        )


def _safe_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
