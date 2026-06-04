"""Runner for Yellow Lab Tools — DOM complexity, CSS weight, JS execution audit."""

from __future__ import annotations

import json

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.yellowlab import YellowLabNormaliser
from viberapid.runners.base import AsyncToolRunner


class YellowLabRunner(AsyncToolRunner):
    """Run Yellow Lab Tools (yellowlab-tools) via npx against a URL to report
    DOM complexity, CSS complexity, JavaScript execution issues, and bad practices."""

    name = "yellowlab"
    requires_url = True
    requires_node = True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        npx = self._npx_path()
        url = self.config.url
        tc = self.tool_config

        try:
            cmd = [
                npx, "yellowlab-tools", url,
            ]

            # Optional: device emulation
            device = tc.get("device", "desktop")
            if device and isinstance(device, str):
                cmd.extend(["--device", device])

            # Optional: screenshot (disable to speed up)
            if not tc.get("screenshot", False):
                cmd.append("--no-screenshot")

            result = self._exec(cmd)

            # yellowlab-tools outputs JSON to stdout
            raw_output = result.stdout.strip()
            if not raw_output:
                return self._make_error_result(
                    f"Yellow Lab Tools did not produce output. stderr: {result.stderr[:500]}"
                )

            try:
                data = json.loads(raw_output)
            except json.JSONDecodeError:
                # yellowlab-tools may prefix output with non-JSON log lines
                # Try to find JSON in the output
                for line in raw_output.split("\n"):
                    line = line.strip()
                    if line.startswith("{"):
                        try:
                            data = json.loads(line)
                            break
                        except json.JSONDecodeError:
                            continue
                else:
                    return self._make_error_result(
                        f"Yellow Lab Tools output is not valid JSON. "
                        f"stderr: {result.stderr[:500]}"
                    )

            normaliser = YellowLabNormaliser()
            findings = normaliser.normalise(data)

            # Extract global score for metrics
            scores = data.get("scoreProfiles", {}).get("generic", {}).get("categories", {})
            global_score = data.get("scoreProfiles", {}).get("generic", {}).get("globalScore")

            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS,
                findings=findings,
                metrics={
                    "url": url,
                    "device": device,
                    "global_score": global_score,
                    "category_scores": {
                        cat: info.get("categoryScore")
                        for cat, info in scores.items()
                        if isinstance(info, dict)
                    },
                },
            )

        except Exception as exc:
            return self._make_error_result(f"Yellow Lab Tools failed: {exc}")
