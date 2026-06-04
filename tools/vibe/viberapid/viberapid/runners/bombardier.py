"""Runner for Bombardier — fast cross-platform HTTP benchmarking tool."""

from __future__ import annotations

import re

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.bombardier import BombardierNormaliser
from viberapid.runners.base import AsyncToolRunner


def _parse_duration(duration_str: str) -> str:
    """Normalise a duration string to bombardier format (e.g. '30s', '5m')."""
    match = re.match(r"^(\d+)(s|m|h)$", duration_str.strip())
    if not match:
        return "30s"
    return duration_str.strip()


class BombardierRunner(AsyncToolRunner):
    """Run Bombardier HTTP benchmark against a URL."""

    name = "bombardier"
    is_load_tester = True
    requires_url = True

    def should_run(self) -> bool:
        if not super().should_run():
            return False
        if not self._tool_exists():
            self.skip_reason = "bombardier not found (install via viberapid install)"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        url = self.config.url
        tc = self.tool_config
        bin_path = self.bin_path

        duration = _parse_duration(self.config.load_duration)
        connections = tc.get("connections", self.config.load_vus)

        cmd = [
            bin_path,
            "-c", str(connections),
            "-d", duration,
            "-p", "r",              # print result only
            "--print", "result",
            "--format", "json",
            url,
        ]

        # Optional: HTTP method
        method = tc.get("method")
        if method and isinstance(method, str):
            cmd.extend(["-m", method.upper()])

        # Optional: request body
        body = tc.get("body")
        if body and isinstance(body, str):
            cmd.extend(["-b", body])

        # Optional: headers
        headers = tc.get("headers", {})
        if isinstance(headers, dict):
            for key, value in headers.items():
                cmd.extend(["-H", f"{key}: {value}"])

        # Optional: timeout per request
        req_timeout = tc.get("timeout", "30s")
        cmd.extend(["--timeout", req_timeout])

        data, stderr = self._exec_json(cmd, cwd="/tmp")

        if data is None:
            return self._make_error_result(
                f"Bombardier did not produce valid JSON. stderr: {stderr[:500]}"
            )

        normaliser = BombardierNormaliser()
        findings = normaliser.normalise(data)

        # Extract summary metrics
        result_data = data.get("result", data)
        latency = result_data.get("latency", {})
        percentiles = latency.get("percentiles", {})
        rps_data = result_data.get("rps", {})

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "url": url,
                "connections": connections,
                "duration": duration,
                "p50_ms": (percentiles.get("50") or 0) / 1_000_000 if percentiles.get("50") else None,
                "p95_ms": (percentiles.get("95") or 0) / 1_000_000 if percentiles.get("95") else None,
                "p99_ms": (percentiles.get("99") or 0) / 1_000_000 if percentiles.get("99") else None,
                "mean_latency_ms": (latency.get("mean") or 0) / 1_000_000 if latency.get("mean") else None,
                "rps": rps_data.get("mean"),
                "req_2xx": result_data.get("req2xx", 0),
                "req_5xx": result_data.get("req5xx", 0),
            },
        )
