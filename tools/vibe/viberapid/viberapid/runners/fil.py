"""Runner for Fil — peak memory profiler for Python, finds one-shot memory spikes."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.fil import FilNormaliser
from viberapid.runners.base import AsyncToolRunner


class FilRunner(AsyncToolRunner):
    """Run Fil to identify peak memory allocations in Python scripts.

    Fil specialises in finding the single call stack responsible for peak memory,
    unlike memray which profiles all allocations over time.
    """

    name = "fil"
    requires_python = True

    def should_run(self) -> bool:
        entry = self.tool_config.get("entry")
        if not entry:
            self.skip_reason = (
                "no entry script configured — set tools.fil.entry in .viberapid.yml"
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

        # Fil writes its report to a directory; use a temp dir
        with tempfile.TemporaryDirectory(prefix="viberapid-fil-") as tmp_dir:
            report_dir = Path(tmp_dir) / "fil-result"

            cmd = [
                bin_path, "run",
                "--output", str(report_dir),
                entry,
            ]

            try:
                result = self._exec(cmd, timeout=120)
            except Exception as exc:
                return self._make_error_result(f"Fil execution failed: {exc}")

            stderr = result.stderr.strip() if result.stderr else ""
            stdout = result.stdout.strip() if result.stdout else ""

            # Fil outputs a peak-memory.svg flamegraph and an index.html report.
            # Try to parse any JSON output first (fil-profile may output JSON).
            data = None
            if stdout:
                try:
                    data = json.loads(stdout)
                except json.JSONDecodeError:
                    pass

            # If no JSON, try to find report files
            if data is None:
                data = self._find_report_data(report_dir)

            # Fall back to parsing text output from stderr/stdout
            if data is None:
                data = self._parse_text_output(stdout, stderr)

            if data is None:
                # Fil ran but gave us nothing parseable
                if result.returncode == 0:
                    return ToolResult(
                        tool=self.name,
                        status=ToolStatus.SUCCESS,
                        findings=[],
                        metrics={"entry_script": entry, "peak_allocations": 0},
                    )
                return self._make_error_result(
                    f"Fil produced no parseable output. stderr: {stderr[:500]}"
                )

            normaliser = FilNormaliser()
            findings = normaliser.normalise(data)

            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS,
                findings=findings,
                metrics={
                    "entry_script": entry,
                    "peak_allocations_found": len(findings),
                },
            )

    def _find_report_data(self, report_dir: Path) -> dict | None:
        """Look for Fil-generated data files in the report directory."""
        if not report_dir.exists():
            return None

        # Check for JSON report files
        for json_file in report_dir.glob("**/*.json"):
            try:
                with open(json_file) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

        # Try to parse the SVG flamegraph for function names and sizes
        for svg_file in report_dir.glob("**/*.svg"):
            svg_data = self._parse_svg_flamegraph(svg_file)
            if svg_data:
                return svg_data

        return None

    def _parse_svg_flamegraph(self, svg_path: Path) -> dict | None:
        """Extract allocation data from Fil's SVG flamegraph.

        The SVG contains <title> elements with 'function (X MiB)' patterns.
        """
        try:
            text = svg_path.read_text(errors="replace")
        except OSError:
            return None

        import re
        # Pattern matches title tags like: "function_name (42.5 MiB)"
        pattern = re.compile(
            r"<title>(.+?)\s+\(([\d.]+)\s*(MiB|KiB|GiB|B)\)</title>"
        )

        allocations = []
        for match in pattern.finditer(text):
            name = match.group(1).strip()
            size = float(match.group(2))
            unit = match.group(3)

            size_mb = _convert_to_mb(size, unit)
            if size_mb < 1.0:
                continue

            # Parse file:line from the function name if present
            filepath = "<unknown>"
            line_no = None
            function = name

            # Fil often formats as "file.py:42 (function_name)"
            file_match = re.match(r"(.+?):(\d+)\s*(?:\((.+?)\))?", name)
            if file_match:
                filepath = file_match.group(1)
                line_no = int(file_match.group(2))
                function = file_match.group(3) or filepath

            allocations.append({
                "function": function,
                "file": filepath,
                "line": line_no,
                "size_mb": round(size_mb, 2),
            })

        if not allocations:
            return None

        # Sort by size descending and take top entries
        allocations.sort(key=lambda x: x["size_mb"], reverse=True)
        return {"peak_allocations": allocations[:20]}

    def _parse_text_output(self, stdout: str, stderr: str) -> dict | None:
        """Parse text output from Fil for allocation information."""
        import re

        combined = (stdout or "") + "\n" + (stderr or "")
        if not combined.strip():
            return None

        allocations = []

        # Look for patterns like "Peak: 128.5 MiB" or "function_name: 42.3 MiB"
        peak_match = re.search(
            r"[Pp]eak(?:\s+memory)?(?:\s+usage)?:?\s*([\d.]+)\s*(MiB|MB|GiB|GB|KiB|KB)",
            combined,
        )

        # Look for allocation lines
        alloc_pattern = re.compile(
            r"(.+?):(\d+)\s+(.+?)\s+([\d.]+)\s*(MiB|MB|GiB|GB|KiB|KB)"
        )
        for match in alloc_pattern.finditer(combined):
            filepath = match.group(1).strip()
            line_no = int(match.group(2))
            function = match.group(3).strip()
            size = float(match.group(4))
            unit = match.group(5)

            allocations.append({
                "function": function,
                "file": filepath,
                "line": line_no,
                "size_mb": round(_convert_to_mb(size, unit), 2),
            })

        if not allocations and not peak_match:
            return None

        result: dict = {"peak_allocations": allocations}
        if peak_match:
            result["peak_memory_mb"] = round(
                _convert_to_mb(float(peak_match.group(1)), peak_match.group(2)), 2
            )

        return result


def _convert_to_mb(size: float, unit: str) -> float:
    """Convert a size value to MB."""
    unit_upper = unit.upper().replace("I", "")
    if unit_upper in ("GB", "GIB"):
        return size * 1024
    if unit_upper in ("KB", "KIB"):
        return size / 1024
    if unit_upper == "B":
        return size / (1024 * 1024)
    return size  # MB or MiB
