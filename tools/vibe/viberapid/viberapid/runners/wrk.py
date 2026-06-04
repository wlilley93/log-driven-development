"""Runner for wrk — modern HTTP benchmarking tool."""

from __future__ import annotations

import re

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.wrk import WrkNormaliser
from viberapid.runners.base import AsyncToolRunner


def _parse_duration(duration_str: str) -> str:
    """Normalise a duration string to wrk format (e.g. '30s', '5m')."""
    match = re.match(r"^(\d+)(s|m|h)$", duration_str.strip())
    if not match:
        return "30s"
    return duration_str.strip()


def _parse_time_to_ms(time_str: str) -> float | None:
    """Parse wrk time strings like '1.20ms', '45.67us', '2.34s' to milliseconds."""
    match = re.match(r"([\d.]+)(us|ms|s|m|h)", time_str.strip())
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2)
    if unit == "us":
        return value / 1000
    if unit == "ms":
        return value
    if unit == "s":
        return value * 1000
    if unit == "m":
        return value * 60_000
    if unit == "h":
        return value * 3_600_000
    return None


def _parse_size_to_bytes(size_str: str) -> float | None:
    """Parse wrk size strings like '1.50KB', '2.34MB', '345B' to bytes."""
    match = re.match(r"([\d.]+)(B|KB|MB|GB)", size_str.strip())
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2)
    multipliers = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}
    return value * multipliers.get(unit, 1)


def _parse_wrk_output(stdout: str) -> dict | None:
    """Parse wrk's text output into a structured dict.

    Example wrk output:
    Running 30s test @ http://localhost:3000
      4 threads and 50 connections
      Thread Stats   Avg      Stdev     Max   +/- Stdev
        Latency    45.20ms   12.30ms 200.00ms   78.50%
        Req/Sec   166.50      5.20   180.00     90.00%
      5000 requests in 30.00s, 14.65MB read
      Socket errors: connect 0, read 2, write 0, timeout 1
      Non-2xx or 3xx responses: 5
    Requests/sec:    166.67
    Transfer/sec:      0.49MB
    """
    if not stdout or not stdout.strip():
        return None

    result: dict = {}

    # Latency line
    latency_match = re.search(
        r"Latency\s+([\d.]+\w+)\s+([\d.]+\w+)\s+([\d.]+\w+)\s+([\d.]+%)",
        stdout,
    )
    if latency_match:
        result["latency_avg_ms"] = _parse_time_to_ms(latency_match.group(1))
        result["latency_stdev_ms"] = _parse_time_to_ms(latency_match.group(2))
        result["latency_max_ms"] = _parse_time_to_ms(latency_match.group(3))
        result["latency_stdev_pct"] = latency_match.group(4)

    # Req/Sec line
    rps_match = re.search(
        r"Req/Sec\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+%)",
        stdout,
    )
    if rps_match:
        result["req_sec_avg"] = float(rps_match.group(1))
        result["req_sec_stdev"] = float(rps_match.group(2))
        result["req_sec_max"] = float(rps_match.group(3))

    # Total requests and duration
    total_match = re.search(r"(\d+)\s+requests?\s+in\s+([\d.]+\w+)", stdout)
    if total_match:
        result["total_requests"] = int(total_match.group(1))
        duration_ms = _parse_time_to_ms(total_match.group(2))
        if duration_ms:
            result["duration_s"] = duration_ms / 1000

    # Transfer
    transfer_match = re.search(r"(\d+)\s+requests?\s+in\s+[\d.]+\w+,\s+([\d.]+\w+)\s+read", stdout)
    if transfer_match:
        result["transfer_bytes"] = _parse_size_to_bytes(transfer_match.group(2))

    # Requests/sec summary
    rps_summary_match = re.search(r"Requests/sec:\s+([\d.]+)", stdout)
    if rps_summary_match:
        result["rps"] = float(rps_summary_match.group(1))

    # Socket errors
    errors_match = re.search(
        r"Socket errors:\s+connect\s+(\d+),\s+read\s+(\d+),\s+write\s+(\d+),\s+timeout\s+(\d+)",
        stdout,
    )
    if errors_match:
        result["errors_connect"] = int(errors_match.group(1))
        result["errors_read"] = int(errors_match.group(2))
        result["errors_write"] = int(errors_match.group(3))
        result["errors_timeout"] = int(errors_match.group(4))
    else:
        result["errors_connect"] = 0
        result["errors_read"] = 0
        result["errors_write"] = 0
        result["errors_timeout"] = 0

    # Non-2xx/3xx responses
    non2xx_match = re.search(r"Non-2xx or 3xx responses:\s+(\d+)", stdout)
    if non2xx_match:
        result["non_2xx_3xx"] = int(non2xx_match.group(1))
    else:
        result["non_2xx_3xx"] = 0

    return result if result else None


class WrkRunner(AsyncToolRunner):
    """Run wrk HTTP benchmark against a URL."""

    name = "wrk"
    is_load_tester = True
    requires_url = True

    def should_run(self) -> bool:
        if not super().should_run():
            return False
        if not self._tool_exists():
            self.skip_reason = "wrk not found on PATH (install via brew/apt)"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        url = self.config.url
        tc = self.tool_config

        duration = _parse_duration(self.config.load_duration)
        connections = tc.get("connections", self.config.load_vus)
        threads = tc.get("threads", 4)

        cmd = [
            self.bin_path,
            f"-t{threads}",
            f"-c{connections}",
            f"-d{duration}",
            url,
        ]

        # Optional: lua script
        script = tc.get("script")
        if script:
            cmd.extend(["-s", script])

        result = self._exec(cmd, cwd="/tmp")

        # Parse text output
        parsed = _parse_wrk_output(result.stdout)

        if parsed is None:
            return self._make_error_result(
                f"wrk did not produce parseable output. "
                f"stdout: {result.stdout[:300]}, "
                f"stderr: {result.stderr[:300]}"
            )

        normaliser = WrkNormaliser()
        findings = normaliser.normalise(parsed)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "url": url,
                "threads": threads,
                "connections": connections,
                "duration": duration,
                "avg_latency_ms": parsed.get("latency_avg_ms"),
                "max_latency_ms": parsed.get("latency_max_ms"),
                "rps": parsed.get("rps"),
                "total_requests": parsed.get("total_requests"),
            },
        )
