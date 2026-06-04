"""Runner for clinic — Node.js performance diagnostics (event loop, CPU, memory)."""

from __future__ import annotations

import json
from pathlib import Path

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.clinic import ClinicNormaliser
from viberapid.runners.base import AsyncToolRunner


class ClinicRunner(AsyncToolRunner):
    """Run clinic doctor to diagnose Node.js server performance issues."""

    name = "clinic"
    requires_node = True

    def should_run(self) -> bool:
        if not self._file_exists("package.json"):
            self.skip_reason = "no package.json found"
            return False

        entry = self.tool_config.get("entry")
        if not entry:
            self.skip_reason = (
                "no entry script configured — set tools.clinic.entry in .viberapid.yml"
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

        # clinic doctor runs the server, collects diagnostics, then generates a report.
        # We use --json to get machine-readable output where supported.
        cmd = [
            npx, "clinic", "doctor",
            "--json",
            "--", "node", entry,
        ]

        try:
            result = self._exec(cmd, timeout=60)
        except Exception as exc:
            return self._make_error_result(f"clinic execution failed: {exc}")

        # clinic may write JSON output to stdout or to a .clinic/ directory.
        # Try to parse stdout first, then look for generated data files.
        data = None
        stderr = result.stderr.strip() if result.stderr else ""

        if result.stdout.strip():
            try:
                data = json.loads(result.stdout)
            except json.JSONDecodeError:
                pass

        # If no JSON from stdout, try to find clinic-generated data
        if data is None:
            data = self._find_clinic_data()

        if data is None:
            # Clinic ran but produced no parseable output — still extract what we can
            # from the text output
            data = self._parse_text_output(result.stdout, result.stderr)

        if data is None:
            return self._make_error_result(
                f"clinic produced no parseable output. stderr: {stderr[:500]}"
            )

        normaliser = ClinicNormaliser()
        findings = normaliser.normalise(data)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS if findings else ToolStatus.PARTIAL,
            findings=findings,
            metrics={
                "entry_script": entry,
                "diagnostics_found": len(findings),
            },
        )

    def _find_clinic_data(self) -> dict | None:
        """Look for clinic-generated JSON data files in the .clinic directory."""
        clinic_dir = Path(self.target) / ".clinic"
        if not clinic_dir.exists():
            return None

        # clinic doctor generates files like .clinic/<pid>.clinic-doctor/
        for data_dir in sorted(clinic_dir.iterdir(), reverse=True):
            if not data_dir.is_dir():
                continue
            # Look for the analysis JSON
            for json_file in data_dir.glob("*.json"):
                try:
                    with open(json_file) as f:
                        return json.load(f)
                except (json.JSONDecodeError, OSError):
                    continue
        return None

    def _parse_text_output(self, stdout: str, stderr: str) -> dict | None:
        """Extract diagnostic hints from clinic's text output."""
        combined = (stdout or "") + "\n" + (stderr or "")
        if not combined.strip():
            return None

        diagnostics = []
        combined_lower = combined.lower()

        if "event loop" in combined_lower and ("delay" in combined_lower or "block" in combined_lower):
            diagnostics.append({
                "type": "event-loop-delay",
                "message": "Event loop delays detected — synchronous operations may be blocking the event loop.",
                "severity": "high",
            })

        if "memory" in combined_lower and ("leak" in combined_lower or "grow" in combined_lower):
            diagnostics.append({
                "type": "memory-leak",
                "message": "Potential memory leak detected — memory usage grows over time.",
                "severity": "high",
            })

        if "cpu" in combined_lower and ("high" in combined_lower or "spike" in combined_lower or "100%" in combined):
            diagnostics.append({
                "type": "high-cpu",
                "message": "High CPU usage detected — compute-intensive operations on the main thread.",
                "severity": "medium",
            })

        if "gc" in combined_lower and ("pause" in combined_lower or "frequency" in combined_lower):
            diagnostics.append({
                "type": "gc-pressure",
                "message": "Excessive garbage collection detected — high object allocation rate.",
                "severity": "medium",
            })

        if "handle" in combined_lower and ("leak" in combined_lower or "open" in combined_lower):
            diagnostics.append({
                "type": "handle-leak",
                "message": "Active handle leak detected — connections or file handles not being closed.",
                "severity": "medium",
            })

        if not diagnostics:
            return None

        return {"diagnostics": diagnostics, "raw_output": combined[:2000]}
