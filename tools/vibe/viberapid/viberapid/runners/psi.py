"""Runner for PageSpeed Insights — CrUX field data and lab performance metrics."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.psi import PSINormaliser
from viberapid.runners.base import AsyncToolRunner


class PSIRunner(AsyncToolRunner):
    """Run PageSpeed Insights (psi npm package) against a URL to collect CrUX field data and lab metrics."""

    name = "psi"
    requires_url = True
    requires_node = True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        npx = self._npx_path()
        url = self.config.url
        tc = self.tool_config

        # Output to a temp file so we can reliably parse JSON
        with tempfile.NamedTemporaryFile(
            prefix="viberapid-psi-",
            suffix=".json",
            delete=False,
        ) as tmp:
            output_path = tmp.name

        try:
            strategy = tc.get("strategy", "mobile")
            cmd = [
                npx, "psi", url,
                "--strategy", strategy,
                "--json",
            ]

            # Optional: API key for higher rate limits
            api_key = tc.get("api_key")
            if api_key and isinstance(api_key, str):
                cmd.extend(["--key", api_key])

            result = self._exec(cmd)

            # psi outputs JSON to stdout when --json is used
            raw_output = result.stdout.strip()
            if not raw_output:
                return self._make_error_result(
                    f"PSI did not produce output. stderr: {result.stderr[:500]}"
                )

            try:
                data = json.loads(raw_output)
            except json.JSONDecodeError:
                return self._make_error_result(
                    f"PSI output is not valid JSON. stderr: {result.stderr[:500]}"
                )

            normaliser = PSINormaliser()
            findings = normaliser.normalise(data)

            # Extract top-level performance score for metrics
            perf_score = None
            categories = data.get("lighthouseResult", {}).get("categories", {})
            perf_cat = categories.get("performance", {})
            if perf_cat:
                perf_score = perf_cat.get("score")

            # Extract CrUX origin summary if available
            origin_summary = data.get("loadingExperience", {})
            overall_category = origin_summary.get("overall_category")

            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS,
                findings=findings,
                metrics={
                    "url": url,
                    "strategy": strategy,
                    "performance_score": perf_score,
                    "crux_overall_category": overall_category,
                },
            )

        except Exception as exc:
            return self._make_error_result(f"PSI failed: {exc}")

        finally:
            Path(output_path).unlink(missing_ok=True)
