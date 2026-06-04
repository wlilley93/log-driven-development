"""Runner for react-scan — automatically detects unnecessary React re-renders."""

from __future__ import annotations

import json

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.react_scan import ReactScanNormaliser
from viberapid.runners.base import AsyncToolRunner


class ReactScanRunner(AsyncToolRunner):
    """Run react-scan to detect unnecessary re-renders in a running React application.

    react-scan instruments a React application (via URL) and identifies components
    that re-render unnecessarily, providing component names, render counts, and
    the reason for each render.
    """

    name = "react-scan"
    requires_url = True
    requires_node = True

    def should_run(self) -> bool:
        if not super().should_run():
            return False

        # react-scan requires a URL to inspect
        if not self.config.url:
            self.skip_reason = "no --url provided — react-scan needs a running React app URL"
            return False

        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        npx = self._npx_path()
        url = self.config.url
        duration = self.tool_config.get("duration", 15)

        # react-scan CLI can be run in monitoring mode
        cmd = [
            npx, "react-scan",
            "--url", url,
            "--json",
        ]

        # Optional: duration for monitoring
        scan_timeout = self.tool_config.get("timeout")
        if scan_timeout:
            cmd.extend(["--timeout", str(scan_timeout)])

        try:
            result = self._exec(cmd, timeout=int(duration) + 30)
        except Exception as exc:
            return self._make_error_result(f"react-scan execution failed: {exc}")

        stdout = result.stdout.strip() if result.stdout else ""
        stderr = result.stderr.strip() if result.stderr else ""

        # Try to parse JSON output
        data = None
        if stdout:
            try:
                data = json.loads(stdout)
            except json.JSONDecodeError:
                data = self._parse_text_output(stdout)

        if data is None:
            if result.returncode == 0:
                return ToolResult(
                    tool=self.name,
                    status=ToolStatus.SUCCESS,
                    findings=[],
                    metrics={
                        "url": url,
                        "components_scanned": 0,
                        "rerenders_detected": 0,
                    },
                )
            return self._make_error_result(
                f"react-scan produced no parseable output. stderr: {stderr[:500]}"
            )

        normaliser = ReactScanNormaliser()
        findings = normaliser.normalise(data)

        # Compute metrics
        total_components = 0
        total_rerenders = 0
        if isinstance(data, dict):
            components = data.get("components", data.get("results", []))
            if isinstance(components, list):
                total_components = len(components)
                for comp in components:
                    if isinstance(comp, dict):
                        total_rerenders += comp.get("render_count", comp.get("renderCount", 0))

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "url": url,
                "components_scanned": total_components,
                "rerenders_detected": total_rerenders,
                "issues_found": len(findings),
            },
        )

    def _parse_text_output(self, stdout: str) -> dict | None:
        """Parse react-scan text output into structured data.

        Text output may look like:
        Component: Dashboard (src/components/Dashboard.tsx)
          Renders: 12
          Unnecessary: 8
          Reason: props changed (onClick)

        Or tabular:
        | Component | Renders | Unnecessary | File |
        """
        if not stdout:
            return None

        components: list[dict] = []
        current: dict | None = None

        for line in stdout.splitlines():
            stripped = line.strip()
            if not stripped:
                if current:
                    components.append(current)
                    current = None
                continue

            lower = stripped.lower()

            if lower.startswith("component:") or lower.startswith("component "):
                if current:
                    components.append(current)
                # Parse "Component: Name (file.tsx)"
                rest = stripped.split(":", 1)[-1].strip()
                name = rest
                filepath = "<unknown>"
                if "(" in rest and ")" in rest:
                    name = rest[:rest.index("(")].strip()
                    filepath = rest[rest.index("(") + 1:rest.index(")")].strip()

                current = {
                    "component": name,
                    "file": filepath,
                    "render_count": 0,
                    "unnecessary_count": 0,
                    "reasons": [],
                }

            elif current:
                if lower.startswith("renders:") or lower.startswith("render count:"):
                    try:
                        current["render_count"] = int(stripped.split(":")[-1].strip())
                    except ValueError:
                        pass
                elif lower.startswith("unnecessary:") or lower.startswith("unnecessary renders:"):
                    try:
                        current["unnecessary_count"] = int(stripped.split(":")[-1].strip())
                    except ValueError:
                        pass
                elif lower.startswith("reason:") or lower.startswith("reasons:"):
                    reason = stripped.split(":", 1)[-1].strip()
                    if reason:
                        current["reasons"].append(reason)

        if current:
            components.append(current)

        if not components:
            return None

        return {"components": components}
