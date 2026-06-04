"""Runner for py-spy — sampling profiler that produces flamegraphs and speedscope JSON."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.py_spy import PySpyNormaliser
from viberapid.runners.base import AsyncToolRunner


class PySpyRunner(AsyncToolRunner):
    """Run py-spy to sample a Python process and identify CPU hotspots."""

    name = "py-spy"
    requires_python = True

    def should_run(self) -> bool:
        entry = self.tool_config.get("entry")
        pid = self.tool_config.get("pid")

        if not entry and not pid:
            self.skip_reason = (
                "no entry script or PID configured — set tools.py-spy.entry "
                "or tools.py-spy.pid in .viberapid.yml"
            )
            return False

        if entry:
            entry_path = Path(self.target) / entry
            if not entry_path.exists():
                self.skip_reason = f"entry script not found: {entry}"
                return False

        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        entry = self.tool_config.get("entry")
        pid = self.tool_config.get("pid")
        duration = self.tool_config.get("duration", 10)
        rate = self.tool_config.get("rate", 100)
        bin_path = self.bin_path

        # Output to a temp file in speedscope JSON format
        with tempfile.NamedTemporaryFile(
            prefix="viberapid-pyspy-",
            suffix=".json",
            delete=False,
        ) as tmp:
            output_path = tmp.name

        try:
            if pid:
                # Attach to a running process
                cmd = [
                    bin_path, "record",
                    "--format", "speedscope",
                    "--output", output_path,
                    "--duration", str(duration),
                    "--rate", str(rate),
                    "--pid", str(pid),
                ]
            else:
                # Run a script and profile it
                cmd = [
                    bin_path, "record",
                    "--format", "speedscope",
                    "--output", output_path,
                    "--duration", str(duration),
                    "--rate", str(rate),
                    "--", "python", entry,
                ]

            try:
                self._exec(cmd, timeout=int(duration) + 30)
            except Exception as exc:
                return self._make_error_result(f"py-spy execution failed: {exc}")

            report = Path(output_path)
            if not report.exists() or report.stat().st_size == 0:
                return self._make_error_result(
                    "py-spy did not produce output — ensure sufficient permissions "
                    "(may require sudo on Linux)"
                )

            with open(report) as f:
                data = json.load(f)

            normaliser = PySpyNormaliser()
            findings = normaliser.normalise(data)

            # Extract metrics from speedscope data
            num_profiles = len(data.get("profiles", []))
            num_frames = 0
            for profile in data.get("profiles", []):
                if isinstance(profile, dict):
                    num_frames += len(profile.get("frames", []))

            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS,
                findings=findings,
                metrics={
                    "mode": "attach" if pid else "record",
                    "duration_seconds": duration,
                    "sample_rate_hz": rate,
                    "profiles_collected": num_profiles,
                    "unique_frames": num_frames,
                    "hotspots_found": len(findings),
                },
            )

        except json.JSONDecodeError:
            return self._make_error_result("py-spy output was not valid JSON")

        finally:
            Path(output_path).unlink(missing_ok=True)
