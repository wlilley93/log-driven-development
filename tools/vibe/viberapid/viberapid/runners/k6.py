"""Runner for k6 — modern load testing tool by Grafana Labs."""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.k6 import K6Normaliser
from viberapid.runners.base import AsyncToolRunner


def _parse_duration(duration_str: str) -> int:
    """Parse a duration string like '30s', '5m', '1h' to seconds."""
    match = re.match(r"^(\d+)(s|m|h)$", duration_str.strip())
    if not match:
        return 30  # default
    value = int(match.group(1))
    unit = match.group(2)
    if unit == "m":
        return value * 60
    if unit == "h":
        return value * 3600
    return value


class K6Runner(AsyncToolRunner):
    """Run k6 load test against a URL."""

    name = "k6"
    is_load_tester = True
    requires_url = True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        url = self.config.url
        tc = self.tool_config

        duration = self.config.load_duration
        vus = self.config.load_vus

        # Build thresholds from tool config
        thresholds = tc.get("thresholds", {})
        thresholds_js = ""
        if thresholds and isinstance(thresholds, dict):
            lines = []
            for metric, conditions in thresholds.items():
                if isinstance(conditions, list):
                    conds_str = ", ".join(f"'{c}'" for c in conditions)
                    lines.append(f"    '{metric}': [{conds_str}]")
                elif isinstance(conditions, str):
                    lines.append(f"    '{metric}': ['{conditions}']")
            if lines:
                thresholds_js = "  thresholds: {\n" + ",\n".join(lines) + "\n  },"
        else:
            # Default thresholds
            thresholds_js = (
                "  thresholds: {\n"
                "    'http_req_duration': ['p(99)<500'],\n"
                "    'http_req_failed': ['rate<0.01'],\n"
                "  },"
            )

        # Generate k6 script
        script_content = f"""import http from 'k6/http';
import {{ check, sleep }} from 'k6';

export const options = {{
  vus: {vus},
  duration: '{duration}',
{thresholds_js}
}};

export default function () {{
  const res = http.get('{url}');
  check(res, {{
    'status is 200': (r) => r.status === 200,
  }});
  sleep(0.1);
}}
"""

        # Write script and output to temp files
        script_file = None
        output_file = None

        try:
            with tempfile.NamedTemporaryFile(
                prefix="viberapid-k6-script-",
                suffix=".js",
                mode="w",
                delete=False,
            ) as sf:
                sf.write(script_content)
                script_file = sf.name

            with tempfile.NamedTemporaryFile(
                prefix="viberapid-k6-output-",
                suffix=".json",
                delete=False,
            ) as of:
                output_file = of.name

            bin_path = self.bin_path
            cmd = [
                bin_path, "run",
                "--summary-export", output_file,
                script_file,
            ]

            result = self._exec(cmd, cwd="/tmp")

            # Parse the summary JSON
            output_path = Path(output_file)
            if not output_path.exists() or output_path.stat().st_size == 0:
                # Try parsing stdout for JSON summary
                if result.stdout.strip():
                    try:
                        data = json.loads(result.stdout)
                    except json.JSONDecodeError:
                        return self._make_error_result(
                            f"k6 did not produce valid summary output. "
                            f"stderr: {result.stderr[:500]}"
                        )
                else:
                    return self._make_error_result(
                        f"k6 did not produce output. "
                        f"exit code: {result.returncode}, "
                        f"stderr: {result.stderr[:500]}"
                    )
            else:
                with open(output_path) as f:
                    data = json.load(f)

            normaliser = K6Normaliser()
            findings = normaliser.normalise(data)

            # Extract summary metrics
            metrics_data = data.get("metrics", {})
            duration_vals = metrics_data.get("http_req_duration", {}).get("values", {})
            reqs_vals = metrics_data.get("http_reqs", {}).get("values", {})
            failed_vals = metrics_data.get("http_req_failed", {}).get("values", {})

            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS,
                findings=findings,
                metrics={
                    "url": url,
                    "vus": vus,
                    "duration": duration,
                    "p50_ms": duration_vals.get("med"),
                    "p95_ms": duration_vals.get("p(95)"),
                    "p99_ms": duration_vals.get("p(99)"),
                    "rps": reqs_vals.get("rate"),
                    "total_requests": reqs_vals.get("count"),
                    "error_rate": failed_vals.get("rate"),
                },
            )

        except Exception as exc:
            return self._make_error_result(f"k6 failed: {exc}")

        finally:
            # Clean up temp files
            if script_file:
                Path(script_file).unlink(missing_ok=True)
            if output_file:
                Path(output_file).unlink(missing_ok=True)
