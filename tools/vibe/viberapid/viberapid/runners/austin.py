"""Runner for austin — frame stack sampler with near-zero overhead."""

from __future__ import annotations

import tempfile
from pathlib import Path

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.austin import AustinNormaliser
from viberapid.runners.base import AsyncToolRunner


class AustinRunner(AsyncToolRunner):
    """Run austin to sample Python frame stacks with near-zero overhead.

    austin attaches to a running process or spawns a new one, sampling the
    call stack at a configurable interval. Output is a collapsed stack format
    (one stack per line, semicolon-separated frames, followed by a sample count).
    """

    name = "austin"
    requires_python = True

    def should_run(self) -> bool:
        entry = self.tool_config.get("entry")
        pid = self.tool_config.get("pid")

        if not entry and not pid:
            self.skip_reason = (
                "no entry script or PID configured — set tools.austin.entry "
                "or tools.austin.pid in .viberapid.yml"
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
        interval = self.tool_config.get("interval", 100)  # microseconds
        bin_path = self.bin_path

        with tempfile.NamedTemporaryFile(
            prefix="viberapid-austin-",
            suffix=".out",
            delete=False,
        ) as tmp:
            output_path = tmp.name

        try:
            cmd = [
                bin_path,
                "-i", str(interval),
                "-t", str(duration),
                "-o", output_path,
                "-s",  # sleepless mode: only sample on-CPU frames
            ]

            if pid:
                cmd.extend(["-p", str(pid)])
            else:
                cmd.extend(["python", entry])

            try:
                self._exec(cmd, timeout=int(duration) + 30)
            except Exception as exc:
                return self._make_error_result(f"austin execution failed: {exc}")

            output_file = Path(output_path)
            if not output_file.exists() or output_file.stat().st_size == 0:
                return self._make_error_result(
                    "austin did not produce output — ensure sufficient permissions "
                    "(may require sudo or SYS_PTRACE capability)"
                )

            text = output_file.read_text(errors="replace")

            data = self._parse_collapsed_stacks(text)

            normaliser = AustinNormaliser()
            findings = normaliser.normalise(data)

            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS,
                findings=findings,
                metrics={
                    "mode": "attach" if pid else "record",
                    "duration_seconds": duration,
                    "interval_microseconds": interval,
                    "total_samples": data.get("total_samples", 0),
                    "unique_frames": len(data.get("frames", {})),
                    "hotspots_found": len(findings),
                },
            )

        finally:
            Path(output_path).unlink(missing_ok=True)

    def _parse_collapsed_stacks(self, text: str) -> dict:
        """Parse austin collapsed-stack output into structured data.

        Austin output format (one per line):
            P<pid>;T<tid>;file.py:func:42;other.py:bar:10 <count>

        Or with memory mode (-m):
            P<pid>;T<tid>;file.py:func:42 <bytes>

        We aggregate sample counts per frame to find hotspots.
        """
        frame_samples: dict[str, _FrameAccum] = {}
        total_samples = 0

        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Split on last space to separate stack from count
            parts = line.rsplit(" ", 1)
            if len(parts) != 2:
                continue

            stack_str = parts[0]
            try:
                count = int(parts[1])
            except ValueError:
                continue

            total_samples += count

            # Parse individual frames from the stack
            frames = stack_str.split(";")
            seen: set[str] = set()

            for frame in frames:
                # Skip process/thread markers
                if frame.startswith("P") or frame.startswith("T"):
                    # Check if it's a simple marker like "P123" or "T456"
                    if ":" not in frame:
                        continue

                # Expected format: "file.py:function_name:line_no"
                frame_parts = frame.rsplit(":", 2)
                if len(frame_parts) < 2:
                    continue

                if len(frame_parts) == 3:
                    filepath = frame_parts[0]
                    function = frame_parts[1]
                    try:
                        line_no = int(frame_parts[2])
                    except ValueError:
                        line_no = None
                elif len(frame_parts) == 2:
                    filepath = frame_parts[0]
                    function = frame_parts[1]
                    line_no = None
                else:
                    continue

                key = f"{filepath}:{function}"
                if key in seen:
                    continue
                seen.add(key)

                if key not in frame_samples:
                    frame_samples[key] = _FrameAccum(
                        filepath=filepath,
                        function=function,
                        line=line_no,
                    )

                frame_samples[key].inclusive_samples += count
                # Update line number if we have one
                if line_no is not None:
                    frame_samples[key].line = line_no

        # Convert to serialisable format
        frames_list = []
        for accum in frame_samples.values():
            pct = (accum.inclusive_samples / total_samples * 100) if total_samples > 0 else 0
            frames_list.append({
                "file": accum.filepath,
                "function": accum.function,
                "line": accum.line,
                "inclusive_samples": accum.inclusive_samples,
                "percent": round(pct, 2),
            })

        # Sort by samples descending
        frames_list.sort(key=lambda x: x["inclusive_samples"], reverse=True)

        return {
            "total_samples": total_samples,
            "frames": frames_list,
        }


class _FrameAccum:
    """Accumulator for per-frame sample counts."""

    __slots__ = ("filepath", "function", "line", "inclusive_samples")

    def __init__(self, filepath: str, function: str, line: int | None):
        self.filepath = filepath
        self.function = function
        self.line = line
        self.inclusive_samples = 0
