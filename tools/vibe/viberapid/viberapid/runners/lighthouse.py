"""Runner for Lighthouse — web performance and best practices audit."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.lighthouse import LighthouseNormaliser
from viberapid.runners.base import AsyncToolRunner


class LighthouseRunner(AsyncToolRunner):
    """Run Lighthouse against a URL and report Core Web Vitals + optimisation opportunities."""

    name = "lighthouse"
    requires_url = True
    requires_node = True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        npx = self._npx_path()
        url = self.config.url
        tc = self.tool_config

        # Output to a temp file so we can reliably parse JSON
        with tempfile.NamedTemporaryFile(
            prefix="viberapid-lighthouse-",
            suffix=".json",
            delete=False,
        ) as tmp:
            output_path = tmp.name

        try:
            cmd = [
                npx, "lighthouse", url,
                "--output", "json",
                "--output-path", output_path,
                '--chrome-flags=--headless --no-sandbox',
            ]

            # Optional: categories to audit
            categories = tc.get("categories")
            if categories and isinstance(categories, list):
                cmd.extend(["--only-categories", ",".join(categories)])

            # Optional: throttling preset
            throttling = tc.get("throttling", "mobile")
            if throttling == "desktop":
                cmd.append("--preset=desktop")
            elif throttling == "none":
                cmd.extend([
                    "--throttling-method=provided",
                    "--screenEmulation.disabled",
                ])
            # Default "mobile" uses Lighthouse defaults

            # Optional: number of runs (takes median)
            runs = tc.get("runs")
            if runs and isinstance(runs, int) and runs > 1:
                cmd.extend(["-n", str(runs)])

            result = self._exec(cmd)

            # Lighthouse may exit non-zero for audit failures but still produce output
            report_path = Path(output_path)
            if not report_path.exists():
                return self._make_error_result(
                    f"Lighthouse did not produce output. stderr: {result.stderr[:500]}"
                )

            with open(report_path) as f:
                data = json.load(f)

            normaliser = LighthouseNormaliser()
            findings = normaliser.normalise(data)

            # Extract top-level performance score for metrics
            perf_score = None
            categories_data = data.get("categories", {})
            perf_cat = categories_data.get("performance", {})
            if perf_cat:
                perf_score = perf_cat.get("score")

            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS,
                findings=findings,
                metrics={
                    "performance_score": perf_score,
                    "url": url,
                    "audits_count": len(data.get("audits", {})),
                },
            )

        except Exception as exc:
            return self._make_error_result(f"Lighthouse failed: {exc}")

        finally:
            # Clean up temp file
            Path(output_path).unlink(missing_ok=True)
