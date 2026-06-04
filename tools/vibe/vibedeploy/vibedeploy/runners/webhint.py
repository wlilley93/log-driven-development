"""webhint runner — runs webhint (hint) via npx for HTTP header and best practice checks."""

from __future__ import annotations

import json
import shutil

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner


class WebhintRunner(AsyncToolRunner):
    name = "webhint"
    requires_url = True

    def should_run(self) -> bool:
        if not self.config.url:
            self.skip_reason = "requires --url"
            return False
        if not shutil.which("npm") and not shutil.which("npx"):
            self.skip_reason = "npm/npx not installed"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        url = self.config.url
        if not url:
            return self._make_error_result("No URL configured")

        if "://" not in url:
            url = f"https://{url}"

        cmd = ["npx", "--yes", "hint", url, "--formatters", "json"]

        try:
            result = self._exec(cmd, timeout=self.config.timeout * 2)
        except Exception as e:
            return self._make_error_result(f"webhint execution failed: {e}")

        findings: list[Finding] = []

        if result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                findings = self._normalise(data, url)
            except json.JSONDecodeError:
                # webhint may output non-JSON content mixed with JSON
                # Try to find JSON array in output
                for line in result.stdout.strip().split("\n"):
                    line = line.strip()
                    if line.startswith("[") or line.startswith("{"):
                        try:
                            data = json.loads(line)
                            findings.extend(self._normalise(data, url))
                        except json.JSONDecodeError:
                            continue

        # webhint returns non-zero when it finds issues
        status = ToolStatus.SUCCESS if result.returncode in (0, 1, 2) else ToolStatus.PARTIAL
        if result.returncode not in (0, 1, 2) and not findings:
            error = result.stderr[:300] if result.stderr else f"exit code {result.returncode}"
            return self._make_error_result(f"webhint failed: {error}")

        return ToolResult(tool=self.name, status=status, findings=findings)

    def _normalise(self, data: list | dict, url: str) -> list[Finding]:
        """Normalise webhint JSON output to findings."""
        findings: list[Finding] = []

        # webhint JSON output is typically an array of problem objects
        items = data if isinstance(data, list) else [data]

        for item in items:
            if not isinstance(item, dict):
                continue

            # webhint can output per-URL results
            problems = item.get("problems", [item])
            resource = item.get("url", url)

            if isinstance(problems, list):
                for problem in problems:
                    if not isinstance(problem, dict):
                        continue

                    hint_id = problem.get("hintId", "") or problem.get("id", "unknown")
                    message = problem.get("message", "")
                    severity_val = problem.get("severity", 2)
                    location = problem.get("location", {}) or {}
                    line = location.get("line")
                    col = location.get("column")
                    problem_resource = problem.get("resource", resource)

                    severity = self._map_severity(severity_val)

                    findings.append(Finding(
                        tool=self.name,
                        severity=severity,
                        category=Category.HTTP_HEADERS,
                        file=problem_resource or url,
                        line=line,
                        col=col,
                        rule_id=f"webhint-{hint_id}",
                        rule_name=hint_id,
                        message=message or f"webhint issue: {hint_id}",
                        effort=Effort.LOW,
                        docs_url=f"https://webhint.io/docs/user-guide/hints/{hint_id}/" if hint_id != "unknown" else None,
                        raw=problem,
                    ))

        return findings

    @staticmethod
    def _map_severity(severity_val: int | str) -> Severity:
        """Map webhint severity to our Severity enum."""
        if isinstance(severity_val, str):
            mapping = {
                "off": Severity.INFO,
                "hint": Severity.INFO,
                "information": Severity.INFO,
                "warning": Severity.MEDIUM,
                "error": Severity.HIGH,
            }
            return mapping.get(severity_val.lower(), Severity.MEDIUM)

        # Numeric: 0=off, 1=hint, 2=warning, 3=error
        if severity_val <= 0:
            return Severity.INFO
        if severity_val == 1:
            return Severity.LOW
        if severity_val == 2:
            return Severity.MEDIUM
        return Severity.HIGH
