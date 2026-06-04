"""Runner for autocannon — fast HTTP benchmarking tool for Node.js."""

from __future__ import annotations

import re

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.autocannon import AutocannonNormaliser
from viberapid.runners.base import AsyncToolRunner


def _parse_duration(duration_str: str) -> int:
    """Parse a duration string like '30s', '5m', '1h' to seconds."""
    match = re.match(r"^(\d+)(s|m|h)$", duration_str.strip())
    if not match:
        return 30
    value = int(match.group(1))
    unit = match.group(2)
    if unit == "m":
        return value * 60
    if unit == "h":
        return value * 3600
    return value


class AutocannonRunner(AsyncToolRunner):
    """Run autocannon HTTP benchmark against a URL."""

    name = "autocannon"
    is_load_tester = True
    requires_url = True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        npx = self._npx_path()
        url = self.config.url
        tc = self.tool_config

        duration_s = _parse_duration(self.config.load_duration)
        connections = tc.get("connections", self.config.load_vus)

        cmd = [
            npx, "autocannon",
            "-j",                       # JSON output
            "-d", str(duration_s),      # duration in seconds
            "-c", str(connections),     # number of concurrent connections
            url,
        ]

        # Optional: pipelining factor
        pipelining = tc.get("pipelining")
        if pipelining and isinstance(pipelining, int):
            cmd.extend(["-p", str(pipelining)])

        # Optional: request method
        method = tc.get("method")
        if method and isinstance(method, str):
            cmd.extend(["-m", method.upper()])

        data, stderr = self._exec_json(cmd, cwd="/tmp")

        if data is None:
            return self._make_error_result(
                f"autocannon did not produce valid JSON. stderr: {stderr[:500]}"
            )

        normaliser = AutocannonNormaliser()
        findings = normaliser.normalise(data)

        # Extract summary metrics
        latency = data.get("latency", {})
        requests = data.get("requests", {})

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "url": url,
                "connections": connections,
                "duration_s": duration_s,
                "p50_ms": latency.get("p50"),
                "p99_ms": latency.get("p99"),
                "avg_latency_ms": latency.get("average"),
                "rps": requests.get("average"),
                "total_requests": requests.get("total"),
                "errors": data.get("errors", 0),
                "timeouts": data.get("timeouts", 0),
                "non2xx": data.get("non2xx", 0),
            },
        )
