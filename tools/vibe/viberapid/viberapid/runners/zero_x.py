"""Runner for 0x — single-command flamegraph profiler for Node.js."""

from __future__ import annotations

import json
from pathlib import Path

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.zero_x import ZeroXNormaliser
from viberapid.runners.base import AsyncToolRunner


class ZeroXRunner(AsyncToolRunner):
    """Run 0x to generate a flamegraph for a Node.js application.

    0x wraps the V8 profiler and automatically generates interactive flamegraphs.
    It outputs a directory containing the flamegraph HTML and the raw profiler data.
    """

    name = "0x"
    requires_node = True

    def should_run(self) -> bool:
        if not self._file_exists("package.json"):
            self.skip_reason = "no package.json found"
            return False

        entry = self.tool_config.get("entry")
        if not entry:
            self.skip_reason = (
                "no entry script configured — set tools.0x.entry in .viberapid.yml"
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

        npx = self._npx_path()
        duration = self.tool_config.get("duration", 10)
        output_dir = self.tool_config.get("output_dir")

        cmd = [npx, "0x", "--collect-only"]

        if output_dir:
            cmd.extend(["--output-dir", output_dir])

        # 0x runs the target script and profiles it
        cmd.extend(["--", "node", entry])

        try:
            result = self._exec(cmd, timeout=int(duration) + 60)
        except Exception as exc:
            return self._make_error_result(f"0x execution failed: {exc}")

        stderr = result.stderr.strip() if result.stderr else ""
        stdout = result.stdout.strip() if result.stdout else ""

        # 0x outputs the path to the generated profile directory
        profile_dir = self._find_profile_dir(stdout, stderr, output_dir)

        if profile_dir is None:
            return self._make_error_result(
                f"0x did not produce a profile directory. stderr: {stderr[:500]}"
            )

        # Parse the stacks file from the profile directory
        data = self._parse_profile_data(profile_dir)

        if data is None:
            return self._make_error_result(
                "0x profile directory found but no parseable data"
            )

        normaliser = ZeroXNormaliser()
        findings = normaliser.normalise(data)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "entry_script": entry,
                "profile_dir": str(profile_dir),
                "total_samples": data.get("total_samples", 0),
                "hotspots_found": len(findings),
            },
        )

    def _find_profile_dir(
        self, stdout: str, stderr: str, configured_dir: str | None
    ) -> Path | None:
        """Find the 0x profile output directory."""
        # Check configured output directory
        if configured_dir:
            path = Path(self.target) / configured_dir
            if path.exists():
                return path

        # 0x prints the output path to stdout/stderr
        combined = (stdout or "") + "\n" + (stderr or "")
        for line in combined.splitlines():
            line = line.strip()
            # 0x outputs lines like "Flamegraph generated in /path/to/profile.0x"
            if ".0x" in line:
                # Extract the path
                for word in line.split():
                    if ".0x" in word:
                        candidate = Path(word)
                        if candidate.exists():
                            return candidate
                        # Try relative to target
                        candidate = Path(self.target) / word
                        if candidate.exists():
                            return candidate

        # Look for any .0x directories in the target
        target = Path(self.target)
        ox_dirs = sorted(target.glob("*.0x"), key=lambda p: p.stat().st_mtime, reverse=True)
        if ox_dirs:
            return ox_dirs[0]

        return None

    def _parse_profile_data(self, profile_dir: Path) -> dict | None:
        """Parse 0x profile data from the output directory.

        0x generates several files:
        - stacks.<pid>.out — collapsed stacks (one per line: "frame;frame count")
        - meta.json — metadata about the profile
        """
        # Try to read meta.json for context
        meta = {}
        meta_file = profile_dir / "meta.json"
        if meta_file.exists():
            try:
                with open(meta_file) as f:
                    meta = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

        # Parse collapsed stacks
        stacks_files = list(profile_dir.glob("stacks.*.out")) + list(
            profile_dir.glob("*.stacks")
        )

        if not stacks_files:
            # Try any .out file
            stacks_files = list(profile_dir.glob("*.out"))

        if not stacks_files:
            return None

        frame_samples: dict[str, _FrameAccum] = {}
        total_samples = 0

        for stacks_file in stacks_files:
            try:
                text = stacks_file.read_text(errors="replace")
            except OSError:
                continue

            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # Format: "frame1;frame2;frame3 count"
                parts = line.rsplit(" ", 1)
                if len(parts) != 2:
                    continue

                stack_str = parts[0]
                try:
                    count = int(parts[1])
                except ValueError:
                    continue

                total_samples += count
                frames = stack_str.split(";")

                seen: set[str] = set()
                for frame in frames:
                    if frame in seen:
                        continue
                    seen.add(frame)

                    # Parse "functionName (file:line)" or just "functionName"
                    name, filepath, line_no = _parse_frame(frame)

                    key = f"{filepath}:{name}"
                    if key not in frame_samples:
                        frame_samples[key] = _FrameAccum(
                            name=name, filepath=filepath, line=line_no
                        )
                    frame_samples[key].inclusive_samples += count

        if total_samples == 0:
            return None

        frames_list = []
        for accum in frame_samples.values():
            pct = (accum.inclusive_samples / total_samples) * 100
            frames_list.append({
                "name": accum.name,
                "file": accum.filepath,
                "line": accum.line,
                "inclusive_samples": accum.inclusive_samples,
                "percent": round(pct, 2),
            })

        frames_list.sort(key=lambda x: x["inclusive_samples"], reverse=True)

        return {
            "total_samples": total_samples,
            "frames": frames_list,
            "meta": meta,
        }


class _FrameAccum:
    """Accumulator for per-frame sample counts."""

    __slots__ = ("name", "filepath", "line", "inclusive_samples")

    def __init__(self, name: str, filepath: str, line: int | None):
        self.name = name
        self.filepath = filepath
        self.line = line
        self.inclusive_samples = 0


def _parse_frame(frame: str) -> tuple[str, str, int | None]:
    """Parse a stack frame string into (name, file, line).

    Handles formats:
    - "functionName (file.js:42:10)"
    - "functionName file.js:42"
    - "functionName"
    """
    import re

    # Try "name (file:line:col)" pattern
    match = re.match(r"(.+?)\s+\((.+?):(\d+)(?::\d+)?\)", frame)
    if match:
        return match.group(1).strip(), match.group(2), int(match.group(3))

    # Try "name file:line" pattern
    match = re.match(r"(.+?)\s+(.+?):(\d+)", frame)
    if match:
        return match.group(1).strip(), match.group(2), int(match.group(3))

    return frame.strip(), "<unknown>", None
