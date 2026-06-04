"""Runner for node --prof — built-in V8 profiler with tick processor analysis."""

from __future__ import annotations

import json
from pathlib import Path

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.node_prof import NodeProfNormaliser
from viberapid.runners.base import AsyncToolRunner


class NodeProfRunner(AsyncToolRunner):
    """Run node --prof to collect V8 profiler ticks and analyse with --prof-process.

    This uses Node.js's built-in V8 profiler, which produces .log files containing
    tick samples. The tick processor converts these into a summary of where time
    is spent (JavaScript, C++, GC, etc.).
    """

    name = "node-prof"
    requires_node = True

    def should_run(self) -> bool:
        if not self._file_exists("package.json"):
            self.skip_reason = "no package.json found"
            return False

        entry = self.tool_config.get("entry")
        if not entry:
            self.skip_reason = (
                "no entry script configured — set tools.node-prof.entry in .viberapid.yml"
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

        import shutil
        node_bin = shutil.which("node") or "node"
        duration = self.tool_config.get("duration", 10)

        # Step 1: Run node with --prof to collect V8 tick samples
        prof_cmd = [node_bin, "--prof", entry]

        try:
            self._exec(prof_cmd, timeout=int(duration) + 30)
        except Exception as exc:
            return self._make_error_result(f"node --prof execution failed: {exc}")

        # Step 2: Find the generated .log file (isolate-*.log)
        log_files = sorted(
            Path(self.target).glob("isolate-*.log"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        if not log_files:
            return self._make_error_result(
                "node --prof did not generate a .log file — "
                "ensure the script runs long enough to produce profiler output"
            )

        log_file = log_files[0]

        try:
            # Step 3: Process the log with --prof-process
            process_cmd = [node_bin, "--prof-process", "--preprocess", str(log_file)]

            try:
                result = self._exec(process_cmd, timeout=60)
            except Exception as exc:
                return self._make_error_result(f"--prof-process failed: {exc}")

            stdout = result.stdout.strip() if result.stdout else ""
            stderr = result.stderr.strip() if result.stderr else ""

            # --prof-process with --preprocess outputs JSON
            data = None
            if stdout:
                try:
                    data = json.loads(stdout)
                except json.JSONDecodeError:
                    # Fall back to text parsing
                    data = self._parse_text_output(stdout)

            if data is None:
                # Try without --preprocess (text output)
                text_cmd = [node_bin, "--prof-process", str(log_file)]
                try:
                    text_result = self._exec(text_cmd, timeout=60)
                    text_out = text_result.stdout.strip() if text_result.stdout else ""
                    if text_out:
                        data = self._parse_text_output(text_out)
                except Exception:
                    pass

            if data is None:
                return self._make_error_result(
                    f"--prof-process produced no parseable output. stderr: {stderr[:500]}"
                )

            normaliser = NodeProfNormaliser()
            findings = normaliser.normalise(data)

            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS,
                findings=findings,
                metrics={
                    "entry_script": entry,
                    "log_file": str(log_file),
                    "hotspots_found": len(findings),
                },
            )

        finally:
            # Clean up generated log file
            log_file.unlink(missing_ok=True)

    def _parse_text_output(self, text: str) -> dict | None:
        """Parse --prof-process text output into structured data.

        The text output has sections like:
        [Summary]:
          ticks  total  nonlib   name
           1234   45.6%   50.2%  JavaScript
            567   21.0%   23.4%  C++
            ...

        [JavaScript]:
          ticks  total  nonlib   name
            456   16.9%   18.8%  LazyCompile: *processData server.js:42:18
            234    8.7%    9.6%  LazyCompile: *handleRequest server.js:15:22
            ...

        [C++]:
          ...
        """
        if not text:
            return None

        sections: dict[str, list[dict]] = {}
        current_section = None
        summary: dict[str, dict] = {}

        lines = text.splitlines()
        for line in lines:
            stripped = line.strip()

            # Detect section headers
            if stripped.startswith("[") and stripped.endswith("]:"):
                current_section = stripped[1:-2]
                continue

            if not stripped or stripped.startswith("ticks"):
                continue

            if current_section == "Summary":
                # Parse summary line: "1234   45.6%   50.2%  JavaScript"
                parts = stripped.split()
                if len(parts) >= 4:
                    try:
                        ticks = int(parts[0])
                        total_pct = float(parts[1].rstrip("%"))
                        name = " ".join(parts[3:])
                        summary[name] = {
                            "ticks": ticks,
                            "total_percent": total_pct,
                        }
                    except (ValueError, IndexError):
                        pass

            elif current_section in ("JavaScript", "C++", "Shared libraries"):
                # Parse function line
                entry = self._parse_function_line(stripped, current_section)
                if entry:
                    if current_section not in sections:
                        sections[current_section] = []
                    sections[current_section].append(entry)

        if not sections and not summary:
            return None

        return {"summary": summary, "sections": sections}

    def _parse_function_line(self, line: str, section: str) -> dict | None:
        """Parse a single function line from --prof-process output.

        Format: "456   16.9%   18.8%  LazyCompile: *processData server.js:42:18"
        """
        import re

        parts = line.split(None, 3)
        if len(parts) < 4:
            return None

        try:
            ticks = int(parts[0])
            total_pct = float(parts[1].rstrip("%"))
            nonlib_pct = float(parts[2].rstrip("%"))
        except (ValueError, IndexError):
            return None

        name_str = parts[3]

        # Extract function name and location
        # "LazyCompile: *processData server.js:42:18"
        function = name_str
        filepath = "<unknown>"
        line_no = None

        # Try to extract file:line from the name
        match = re.search(r"[\s:](\S+\.(?:js|ts|mjs|cjs)):(\d+)(?::\d+)?", name_str)
        if match:
            filepath = match.group(1)
            line_no = int(match.group(2))

        # Clean up function name
        function = re.sub(r"^(LazyCompile|Function|Script):\s*\*?", "", function).strip()
        # Remove file:line from function name if present
        function = re.sub(r"\s+\S+:\d+(?::\d+)?$", "", function).strip()

        return {
            "function": function or name_str,
            "file": filepath,
            "line": line_no,
            "ticks": ticks,
            "total_percent": total_pct,
            "nonlib_percent": nonlib_pct,
            "section": section,
        }
