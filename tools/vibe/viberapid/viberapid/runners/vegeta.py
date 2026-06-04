"""Runner for Vegeta — versatile HTTP load testing tool."""

from __future__ import annotations

import json
import re
import subprocess

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.vegeta import VegetaNormaliser
from viberapid.runners.base import AsyncToolRunner


def _parse_duration(duration_str: str) -> str:
    """Normalise a duration string to Go format (e.g. '30s', '5m')."""
    match = re.match(r"^(\d+)(s|m|h)$", duration_str.strip())
    if not match:
        return "30s"
    return duration_str.strip()


class VegetaRunner(AsyncToolRunner):
    """Run Vegeta load test against a URL using piped commands.

    Pipeline: echo "GET <url>" | vegeta attack ... | vegeta report -type=json
    """

    name = "vegeta"
    is_load_tester = True
    requires_url = True

    def should_run(self) -> bool:
        if not super().should_run():
            return False
        if not self._tool_exists():
            self.skip_reason = "vegeta not found (install via viberapid install)"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        import os

        url = self.config.url
        tc = self.tool_config
        bin_path = self.bin_path

        duration = _parse_duration(self.config.load_duration)

        # Rate: requests per second (default: VUs as a rough proxy)
        rate = tc.get("rate", self.config.load_vus)

        # Build the target specification
        method = tc.get("method", "GET")
        target_line = f"{method} {url}"

        # Optional: headers
        headers = tc.get("headers", {})
        if isinstance(headers, dict):
            for key, value in headers.items():
                target_line += f"\n{key}: {value}"

        # Use subprocess.Popen for the pipeline:
        # echo "<targets>" | vegeta attack -duration=<dur> -rate=<rate> | vegeta report -type=json
        run_env = os.environ.copy()

        effective_timeout = max(self.config.timeout, self.config.load_timeout)

        try:
            # Stage 1: echo targets
            echo_proc = subprocess.Popen(
                ["echo", target_line],
                stdout=subprocess.PIPE,
                env=run_env,
            )

            # Stage 2: vegeta attack
            attack_cmd = [
                bin_path, "attack",
                f"-duration={duration}",
                f"-rate={rate}",
            ]

            # Optional: max connections
            max_connections = tc.get("max_connections")
            if max_connections:
                attack_cmd.append(f"-max-connections={max_connections}")

            # Optional: timeout per request
            req_timeout = tc.get("timeout", "30s")
            attack_cmd.append(f"-timeout={req_timeout}")

            attack_proc = subprocess.Popen(
                attack_cmd,
                stdin=echo_proc.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=run_env,
            )

            # Allow echo_proc to receive SIGPIPE if attack_proc exits
            if echo_proc.stdout:
                echo_proc.stdout.close()

            # Stage 3: vegeta report
            report_proc = subprocess.Popen(
                [bin_path, "report", "-type=json"],
                stdin=attack_proc.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=run_env,
            )

            if attack_proc.stdout:
                attack_proc.stdout.close()

            stdout, stderr = report_proc.communicate(timeout=effective_timeout)

            # Wait for upstream processes to finish
            echo_proc.wait(timeout=5)
            attack_proc.wait(timeout=5)

        except subprocess.TimeoutExpired:
            # Kill all processes in the pipeline
            for proc in [echo_proc, attack_proc, report_proc]:
                try:
                    proc.kill()
                except OSError:
                    pass
            return self._make_error_result(
                f"Vegeta pipeline timed out after {effective_timeout}s"
            )
        except Exception as exc:
            return self._make_error_result(f"Vegeta pipeline failed: {exc}")

        # Parse JSON report
        stdout_str = stdout.decode("utf-8", errors="replace").strip()
        if not stdout_str:
            stderr_str = stderr.decode("utf-8", errors="replace").strip()
            return self._make_error_result(
                f"Vegeta did not produce output. stderr: {stderr_str[:500]}"
            )

        try:
            data = json.loads(stdout_str)
        except json.JSONDecodeError:
            return self._make_error_result(
                f"Vegeta output is not valid JSON. stdout: {stdout_str[:300]}"
            )

        normaliser = VegetaNormaliser()
        findings = normaliser.normalise(data)

        # Extract metrics
        latencies = data.get("latencies", {})

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "url": url,
                "rate": rate,
                "duration": duration,
                "mean_latency_ms": (latencies.get("mean") or 0) / 1_000_000,
                "p50_ms": (latencies.get("50th") or 0) / 1_000_000,
                "p95_ms": (latencies.get("95th") or 0) / 1_000_000,
                "p99_ms": (latencies.get("99th") or 0) / 1_000_000,
                "max_ms": (latencies.get("max") or 0) / 1_000_000,
                "success_ratio": data.get("success"),
                "total_requests": data.get("requests"),
                "throughput": data.get("throughput"),
            },
        )
