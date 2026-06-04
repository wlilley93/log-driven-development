"""Runner for sitespeed.io — web performance metrics and budget checking."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.sitespeed import SitespeedNormaliser
from viberapid.runners.base import AsyncToolRunner


class SitespeedRunner(AsyncToolRunner):
    """Run sitespeed.io against a URL to collect performance metrics and check budgets."""

    name = "sitespeed"
    requires_url = True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        npx = self._npx_path()
        url = self.config.url
        tc = self.tool_config

        output_dir = tempfile.mkdtemp(prefix="viberapid-sitespeed-")

        try:
            cmd = [
                npx, "sitespeed.io", url,
                "-n", "1",
                "--outputFolder", output_dir,
            ]

            # Optional: budget config file
            budget_file = tc.get("budget") or self.config.budget_file
            if budget_file and Path(budget_file).exists():
                cmd.extend(["--budget.configPath", budget_file])

            # Optional: browser (default: chrome headless)
            browser = tc.get("browser", "chrome")
            cmd.extend(["--browser", browser])

            # Headless by default
            if tc.get("headless", True):
                cmd.append("--browsertime.headless")

            result = self._exec(cmd)

            # Collect output data
            combined_data: dict = {}

            # Look for budget results
            budget_path = Path(output_dir) / "budget.json"
            if budget_path.exists():
                with open(budget_path) as f:
                    budget_data = json.load(f)
                combined_data["budget"] = budget_data if isinstance(budget_data, list) else budget_data.get("budget", [])

            # Look for pages summary data
            # sitespeed.io puts data in pages/<domain>/<path>/data/
            pages_dir = Path(output_dir) / "pages"
            if pages_dir.exists():
                for summary_file in pages_dir.rglob("*.json"):
                    if "browsertime.summary" in summary_file.name:
                        try:
                            with open(summary_file) as f:
                                summary = json.load(f)
                            if isinstance(summary, list) and summary:
                                combined_data["statistics"] = summary[0].get("statistics", {})
                            elif isinstance(summary, dict):
                                combined_data["statistics"] = summary.get("statistics", {})
                        except (json.JSONDecodeError, KeyError):
                            continue
                        break

            normaliser = SitespeedNormaliser()
            findings = normaliser.normalise(combined_data)

            budget_violations = len(combined_data.get("budget", []))

            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS,
                findings=findings,
                metrics={
                    "url": url,
                    "budget_violations": budget_violations,
                    "output_dir": output_dir,
                },
            )

        except Exception as exc:
            return self._make_error_result(f"sitespeed.io failed: {exc}")

        finally:
            # Clean up output directory
            import shutil
            shutil.rmtree(output_dir, ignore_errors=True)
