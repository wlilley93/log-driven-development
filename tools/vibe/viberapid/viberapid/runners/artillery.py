"""Runner for Artillery — cloud-scale load testing tool."""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

import yaml

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.artillery import ArtilleryNormaliser
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


class ArtilleryRunner(AsyncToolRunner):
    """Run Artillery load test against a URL."""

    name = "artillery"
    is_load_tester = True
    requires_url = True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        npx = self._npx_path()
        url = self.config.url
        tc = self.tool_config

        duration_s = _parse_duration(self.config.load_duration)
        vus = self.config.load_vus

        # Calculate arrival rate: spread VUs over the duration
        # Use a ramp-up phase then sustain
        ramp_duration = min(duration_s // 4, 10) or 1
        sustain_duration = duration_s - ramp_duration

        # Build Artillery config
        config = {
            "config": {
                "target": url,
                "phases": [
                    {
                        "duration": ramp_duration,
                        "arrivalRate": max(1, vus // 4),
                        "rampTo": vus,
                        "name": "Ramp up",
                    },
                    {
                        "duration": sustain_duration,
                        "arrivalRate": vus,
                        "name": "Sustained load",
                    },
                ],
            },
            "scenarios": [
                {
                    "name": "Load test",
                    "flow": [
                        {"get": {"url": "/"}},
                    ],
                }
            ],
        }

        # Allow custom scenarios from tool config
        custom_scenarios = tc.get("scenarios")
        if custom_scenarios and isinstance(custom_scenarios, list):
            config["scenarios"] = custom_scenarios

        config_file = None
        output_file = None

        try:
            # Write config YAML
            with tempfile.NamedTemporaryFile(
                prefix="viberapid-artillery-config-",
                suffix=".yml",
                mode="w",
                delete=False,
            ) as cf:
                yaml.dump(config, cf, default_flow_style=False)
                config_file = cf.name

            # Output JSON report
            with tempfile.NamedTemporaryFile(
                prefix="viberapid-artillery-report-",
                suffix=".json",
                delete=False,
            ) as of:
                output_file = of.name

            cmd = [
                npx, "artillery", "run",
                "--output", output_file,
                config_file,
            ]

            result = self._exec(cmd, cwd="/tmp")

            # Parse output
            output_path = Path(output_file)
            if not output_path.exists() or output_path.stat().st_size == 0:
                return self._make_error_result(
                    f"Artillery did not produce output. "
                    f"exit code: {result.returncode}, "
                    f"stderr: {result.stderr[:500]}"
                )

            with open(output_path) as f:
                data = json.load(f)

            normaliser = ArtilleryNormaliser()
            findings = normaliser.normalise(data)

            # Extract summary metrics
            aggregate = data.get("aggregate", {})
            summaries = aggregate.get("summaries", {})
            response_time = summaries.get("http.response_time", {})
            counters = aggregate.get("counters", {})
            rates = aggregate.get("rates", {})

            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS,
                findings=findings,
                metrics={
                    "url": url,
                    "vus": vus,
                    "duration": self.config.load_duration,
                    "p50_ms": response_time.get("p50") or response_time.get("median"),
                    "p95_ms": response_time.get("p95"),
                    "p99_ms": response_time.get("p99"),
                    "rps": rates.get("http.request_rate"),
                    "total_requests": counters.get("http.requests"),
                    "vusers_created": counters.get("vusers.created"),
                    "vusers_failed": counters.get("vusers.failed"),
                },
            )

        except Exception as exc:
            return self._make_error_result(f"Artillery failed: {exc}")

        finally:
            if config_file:
                Path(config_file).unlink(missing_ok=True)
            if output_file:
                Path(output_file).unlink(missing_ok=True)
