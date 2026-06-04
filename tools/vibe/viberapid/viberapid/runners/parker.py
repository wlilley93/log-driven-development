"""Runner for parker — CSS stylesheet analysis."""

from __future__ import annotations

import json
from typing import Any

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.parker import ParkerNormaliser
from viberapid.runners.base import AsyncToolRunner


class ParkerRunner(AsyncToolRunner):
    """Run parker to analyse CSS complexity and specificity metrics."""

    name = "parker"
    requires_node = True

    def should_run(self) -> bool:
        css_files = self._glob_files("*.css")
        css_files = [
            f for f in css_files
            if "node_modules" not in str(f)
            and ".next" not in str(f)
            and "vendor" not in str(f)
        ]
        if not css_files:
            self.skip_reason = "no CSS files found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        css_files = self._glob_files("*.css")
        css_files = [
            f for f in css_files
            if "node_modules" not in str(f)
            and ".next" not in str(f)
            and "vendor" not in str(f)
        ]

        if not css_files:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS,
                findings=[],
                metrics={"css_files_checked": 0},
            )

        npx = self._npx_path()
        results: list[dict[str, Any]] = []

        # parker can process one file at a time; run per file
        for css_file in css_files[:30]:  # limit to 30 files
            cmd = [npx, "parker", str(css_file)]
            result = self._exec(cmd, timeout=30)

            # parker outputs JSON-like metrics to stdout
            stdout = result.stdout.strip()
            if not stdout:
                continue

            try:
                metrics = json.loads(stdout)
            except json.JSONDecodeError:
                # parker may output non-JSON; try to parse structured text
                metrics = self._parse_parker_text(stdout)
                if not metrics:
                    continue

            relative_path = str(css_file.relative_to(self.target))
            results.append({
                "file": relative_path,
                "metrics": metrics,
            })

        normaliser = ParkerNormaliser()
        findings = normaliser.normalise(results)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={"css_files_checked": len(results)},
        )

    @staticmethod
    def _parse_parker_text(text: str) -> dict[str, Any] | None:
        """Parse parker's text output format into a dict.

        Parker text output looks like:
        Total Stylesheets: 1
        Total Stylesheet Size: 45000
        Total Rules: 320
        ...
        """
        metrics: dict[str, Any] = {}
        key_map = {
            "total stylesheets": "total-stylesheets",
            "total stylesheet size": "total-stylesheet-size",
            "total rules": "total-rules",
            "total selectors": "total-selectors",
            "total identifiers": "total-identifiers",
            "total declarations": "total-declarations",
            "selectors per rule": "selectors-per-rule",
            "identifiers per selector": "identifiers-per-selector",
            "specificity per selector": "specificity-per-selector",
            "top selector specificity": "top-selector-specificity",
            "top selector specificity selector": "top-selector-specificity-selector",
            "total id selectors": "total-id-selectors",
            "total unique colours": "total-unique-colors",
            "total unique colors": "total-unique-colors",
            "total important keywords": "total-important-keywords",
            "total media queries": "total-media-queries",
        }

        for line in text.split("\n"):
            if ":" not in line:
                continue
            parts = line.split(":", 1)
            key = parts[0].strip().lower()
            value = parts[1].strip()

            mapped_key = key_map.get(key)
            if mapped_key:
                try:
                    metrics[mapped_key] = float(value) if "." in value else int(value)
                except ValueError:
                    metrics[mapped_key] = value

        return metrics if metrics else None
