"""Runner for hstspreload — HSTS header validation for preload list eligibility."""

from __future__ import annotations

import json
from urllib.parse import urlparse

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.hstspreload import HSTSPreloadNormaliser
from viberapid.runners.base import AsyncToolRunner


class HSTSPreloadRunner(AsyncToolRunner):
    """Run hstspreload-cli via npx to validate HSTS configuration
    and check eligibility for the HSTS Preload List."""

    name = "hstspreload"
    requires_url = True
    requires_node = True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        npx = self._npx_path()
        url = self.config.url

        # Extract the domain from the URL for hstspreload
        parsed = urlparse(url)
        domain = parsed.hostname or parsed.netloc or url
        # hstspreload expects a bare domain, not a full URL
        domain = domain.strip("/")

        try:
            # hstspreload-cli checks a domain against the HSTS preload requirements
            cmd = [
                npx, "hstspreload", domain,
            ]

            result = self._exec(cmd, cwd="/tmp")

            # hstspreload-cli outputs JSON to stdout
            raw_output = result.stdout.strip()
            stderr_output = result.stderr.strip()

            if not raw_output:
                # Try to parse meaningful error from stderr
                if stderr_output:
                    return self._make_error_result(
                        f"hstspreload did not produce output. stderr: {stderr_output[:500]}"
                    )
                return self._make_error_result(
                    "hstspreload did not produce output."
                )

            try:
                data = json.loads(raw_output)
            except json.JSONDecodeError:
                # hstspreload may output non-JSON status messages;
                # try to parse structured info from text output
                data = self._parse_text_output(raw_output, domain)

            # Ensure domain is included in the data for the normaliser
            if isinstance(data, dict) and "domain" not in data:
                data["domain"] = domain

            normaliser = HSTSPreloadNormaliser()
            findings = normaliser.normalise(data)

            # Extract summary for metrics
            issues = data.get("issues", []) if isinstance(data, dict) else []
            warnings = data.get("warnings", []) if isinstance(data, dict) else []
            status = data.get("status", "unknown") if isinstance(data, dict) else "unknown"

            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS if not issues else ToolStatus.PARTIAL,
                findings=findings,
                metrics={
                    "url": url,
                    "domain": domain,
                    "preload_status": status,
                    "issue_count": len(issues),
                    "warning_count": len(warnings),
                },
            )

        except Exception as exc:
            return self._make_error_result(f"hstspreload failed: {exc}")

    @staticmethod
    def _parse_text_output(output: str, domain: str) -> dict:
        """Fallback parser for non-JSON hstspreload output."""
        issues: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        status = "unknown"

        lines = output.strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue

            lower = line.lower()

            # Detect status
            if "eligible" in lower and "not" not in lower:
                status = "eligible"
            elif "not eligible" in lower or "ineligible" in lower:
                status = "not_eligible"
            elif "already preloaded" in lower or "preloaded" in lower:
                status = "preloaded"

            # Detect issues and warnings
            if lower.startswith("error") or lower.startswith("issue"):
                issues.append({"code": "parse-error", "message": line})
            elif lower.startswith("warning") or lower.startswith("warn"):
                warnings.append({"code": "parse-warning", "message": line})
            elif "missing" in lower or "invalid" in lower or "must" in lower:
                issues.append({"code": "parse-issue", "message": line})

        return {
            "domain": domain,
            "status": status,
            "issues": issues,
            "warnings": warnings,
        }
