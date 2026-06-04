"""Runner for hyperfine — command-line benchmarking tool."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.hyperfine import HyperfineNormaliser
from viberapid.runners.base import AsyncToolRunner


class HyperfineRunner(AsyncToolRunner):
    """Run hyperfine to benchmark CLI commands (startup time, build time, etc.)."""

    name = "hyperfine"

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "hyperfine not found (install via viberapid install)"
            return False

        # Must have a command to benchmark (from tool config)
        tc = self.tool_config
        command = tc.get("command") or tc.get("commands")
        if not command:
            self.skip_reason = "no command configured for hyperfine (set tools.hyperfine.command in .viberapid.yml)"
            return False

        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        tc = self.tool_config
        bin_path = self.bin_path

        # Get command(s) to benchmark
        commands = tc.get("commands") or tc.get("command")
        if isinstance(commands, str):
            commands = [commands]
        if not isinstance(commands, list) or not commands:
            return self._make_error_result(
                "No command configured for hyperfine benchmark."
            )

        output_file = None

        try:
            with tempfile.NamedTemporaryFile(
                prefix="viberapid-hyperfine-",
                suffix=".json",
                delete=False,
            ) as of:
                output_file = of.name

            cmd = [
                bin_path,
                "--export-json", output_file,
            ]

            # Optional: warmup runs
            warmup = tc.get("warmup", 1)
            cmd.extend(["--warmup", str(warmup)])

            # Optional: number of runs
            runs = tc.get("runs") or tc.get("min-runs")
            if runs and isinstance(runs, int):
                cmd.extend(["--min-runs", str(runs)])

            # Optional: prepare command (run before each benchmark)
            prepare = tc.get("prepare")
            if prepare and isinstance(prepare, str):
                cmd.extend(["--prepare", prepare])

            # Add benchmark commands
            for bench_cmd in commands:
                cmd.append(bench_cmd)

            result = self._exec(cmd, cwd=self.target)

            # Parse JSON output
            output_path = Path(output_file)
            if not output_path.exists() or output_path.stat().st_size == 0:
                return self._make_error_result(
                    f"hyperfine did not produce output. "
                    f"exit code: {result.returncode}, "
                    f"stderr: {result.stderr[:500]}"
                )

            with open(output_path) as f:
                data = json.load(f)

            normaliser = HyperfineNormaliser()
            findings = normaliser.normalise(data)

            # Extract summary metrics
            bench_results = data.get("results", [])
            metrics: dict = {
                "commands": commands,
                "benchmarks": [],
            }
            for bench in bench_results:
                if isinstance(bench, dict):
                    metrics["benchmarks"].append({
                        "command": bench.get("command"),
                        "mean_s": bench.get("mean"),
                        "median_s": bench.get("median"),
                        "stddev_s": bench.get("stddev"),
                        "min_s": bench.get("min"),
                        "max_s": bench.get("max"),
                    })

            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS,
                findings=findings,
                metrics=metrics,
            )

        except Exception as exc:
            return self._make_error_result(f"hyperfine failed: {exc}")

        finally:
            if output_file:
                Path(output_file).unlink(missing_ok=True)
