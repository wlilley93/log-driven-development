"""Runner for memray — memory profiler detecting allocation hotspots and peak usage."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.memray import MemrayNormaliser
from viberapid.runners.base import AsyncToolRunner


class MemrayRunner(AsyncToolRunner):
    """Run memray to profile Python memory allocations and identify high-allocation functions."""

    name = "memray"
    requires_python = True

    def should_run(self) -> bool:
        entry = self.tool_config.get("entry")
        if not entry:
            self.skip_reason = (
                "no entry script configured — set tools.memray.entry in .viberapid.yml"
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

        # memray writes a binary capture file, then we run stats/flamegraph on it
        with tempfile.NamedTemporaryFile(
            prefix="viberapid-memray-",
            suffix=".bin",
            delete=False,
        ) as tmp:
            capture_path = tmp.name

        stats_path = capture_path + ".stats.json"

        try:
            # Step 1: record allocations
            record_cmd = [
                bin_path, "run",
                "--output", capture_path,
                "--force",
                entry,
            ]

            try:
                self._exec(record_cmd, timeout=60)
            except Exception as exc:
                return self._make_error_result(f"memray recording failed: {exc}")

            capture = Path(capture_path)
            if not capture.exists() or capture.stat().st_size == 0:
                return self._make_error_result("memray did not produce a capture file")

            # Step 2: extract stats as text (memray stats outputs a table)
            stats_cmd = [bin_path, "stats", capture_path]

            try:
                stats_result = self._exec(stats_cmd, timeout=30)
            except Exception as exc:
                return self._make_error_result(f"memray stats failed: {exc}")

            stats_text = stats_result.stdout.strip() if stats_result.stdout else ""

            # Step 3: also try to get flamegraph data for richer analysis
            flamegraph_data = None
            try:
                flamegraph_cmd = [
                    bin_path, "flamegraph",
                    "--output", stats_path,
                    "--format", "json",
                    capture_path,
                ]
                fg_result = self._exec(flamegraph_cmd, timeout=30)
                fg_path = Path(stats_path)
                if fg_path.exists():
                    with open(fg_path) as f:
                        flamegraph_data = json.load(f)
            except Exception:
                pass  # flamegraph JSON is optional

            # Parse the stats text output into structured data
            data = self._parse_stats_output(stats_text)
            if flamegraph_data:
                data["flamegraph"] = flamegraph_data

            normaliser = MemrayNormaliser()
            findings = normaliser.normalise(data)

            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS,
                findings=findings,
                metrics={
                    "entry_script": entry,
                    "hotspots_found": len(findings),
                    "has_flamegraph": flamegraph_data is not None,
                },
            )

        except Exception as exc:
            return self._make_error_result(f"memray analysis failed: {exc}")

        finally:
            Path(capture_path).unlink(missing_ok=True)
            Path(stats_path).unlink(missing_ok=True)

    def _parse_stats_output(self, text: str) -> dict:
        """Parse memray stats text output into structured data.

        memray stats output looks like:
        Total allocations: 12345
        Total memory allocated: 256.5MB
        Peak memory usage: 128.3MB

        Top allocators by size:
            file.py:42  func_name  64.2MB  (50.0%)
            file.py:78  other_func 32.1MB  (25.0%)
        ...

        Top allocators by count:
            file.py:42  func_name  5000  (40.0%)
        """
        result: dict = {
            "total_allocations": 0,
            "total_memory_mb": 0.0,
            "peak_memory_mb": 0.0,
            "top_by_size": [],
            "top_by_count": [],
        }

        if not text:
            return result

        lines = text.splitlines()
        section = None

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            lower = stripped.lower()

            # Parse summary lines
            if lower.startswith("total allocations"):
                result["total_allocations"] = _extract_int(stripped)
            elif lower.startswith("total memory allocated"):
                result["total_memory_mb"] = _extract_mb(stripped)
            elif lower.startswith("peak memory"):
                result["peak_memory_mb"] = _extract_mb(stripped)
            elif "top" in lower and "by size" in lower:
                section = "size"
            elif "top" in lower and "by count" in lower:
                section = "count"
            elif section and ":" in stripped:
                entry = self._parse_allocator_line(stripped)
                if entry:
                    if section == "size":
                        result["top_by_size"].append(entry)
                    else:
                        result["top_by_count"].append(entry)

        return result

    def _parse_allocator_line(self, line: str) -> dict | None:
        """Parse a single allocator line from memray stats output."""
        # Expected format: "file.py:42  func_name  64.2MB  (50.0%)"
        parts = line.split()
        if len(parts) < 3:
            return None

        location = parts[0]
        filepath = location
        line_no = None

        if ":" in location:
            loc_parts = location.rsplit(":", 1)
            filepath = loc_parts[0]
            try:
                line_no = int(loc_parts[1])
            except ValueError:
                pass

        function = parts[1] if len(parts) > 1 else "<unknown>"

        # Try to extract size/count and percentage
        size_str = parts[2] if len(parts) > 2 else "0"
        pct = 0.0
        for part in parts:
            if "%" in part:
                pct = _extract_pct(part)
                break

        size_mb = _extract_mb(size_str) if "b" in size_str.lower() else 0.0
        count = _extract_int(size_str) if size_mb == 0.0 else 0

        return {
            "file": filepath,
            "line": line_no,
            "function": function,
            "size_mb": size_mb,
            "count": count,
            "percent": pct,
        }


def _extract_int(s: str) -> int:
    """Extract the first integer from a string."""
    import re
    match = re.search(r"[\d,]+", s)
    if match:
        return int(match.group().replace(",", ""))
    return 0


def _extract_mb(s: str) -> float:
    """Extract a memory size in MB from a string like '256.5MB' or '1.2GB'."""
    import re
    match = re.search(r"([\d.]+)\s*(GB|MB|KB|B)", s, re.IGNORECASE)
    if not match:
        return 0.0
    value = float(match.group(1))
    unit = match.group(2).upper()
    if unit == "GB":
        return value * 1024
    if unit == "KB":
        return value / 1024
    if unit == "B":
        return value / (1024 * 1024)
    return value  # MB


def _extract_pct(s: str) -> float:
    """Extract a percentage value from a string like '(50.0%)'."""
    import re
    match = re.search(r"([\d.]+)%", s)
    if match:
        return float(match.group(1))
    return 0.0
