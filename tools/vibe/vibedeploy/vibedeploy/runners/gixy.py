"""gixy runner — nginx configuration security analyzer."""

from __future__ import annotations

import json

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner


class GixyRunner(AsyncToolRunner):
    name = "gixy"

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "gixy not installed"
            return False
        if not self._file_exists("nginx.conf", "conf/nginx.conf", "etc/nginx/nginx.conf"):
            nginx_files = self._scan_files("**/*.conf")
            has_nginx_conf = any("nginx" in str(f).lower() for f in nginx_files)
            if not has_nginx_conf:
                self.skip_reason = "no nginx configuration found"
                return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        # Find the nginx config file
        config_file = None
        for candidate in ("nginx.conf", "conf/nginx.conf", "etc/nginx/nginx.conf"):
            if self._file_exists(candidate):
                config_file = candidate
                break

        if not config_file:
            nginx_files = self._scan_files("**/*.conf")
            for f in nginx_files:
                if "nginx" in str(f).lower():
                    try:
                        config_file = str(f.relative_to(self.target))
                    except ValueError:
                        config_file = str(f)
                    break

        if not config_file:
            return ToolResult(tool=self.name, status=ToolStatus.SKIPPED)

        cmd = [self.bin_path, "--format", "json", config_file]

        try:
            result = self._exec(cmd, timeout=60)
        except Exception as e:
            return self._make_error_result(f"gixy execution failed: {e}")

        findings: list[Finding] = []

        if result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                findings = self._parse_results(data, config_file)
            except json.JSONDecodeError:
                # gixy may output non-JSON, try line-by-line parsing
                pass

        if result.returncode not in (0, 1) and not findings:
            return self._make_error_result(
                f"gixy exited with code {result.returncode}: {result.stderr[:300]}"
            )

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
        )

    def _parse_results(self, data: list | dict, config_file: str) -> list[Finding]:
        findings: list[Finding] = []

        issues = data if isinstance(data, list) else data.get("issues", [])

        for issue in issues:
            if not isinstance(issue, dict):
                continue

            plugin = issue.get("plugin", "unknown")
            severity_text = issue.get("severity", "medium")
            summary = issue.get("summary", "")
            description = issue.get("description", "")
            help_url = issue.get("help_url", None)
            config = issue.get("config", [])

            severity = self._map_severity(severity_text)

            # Build file/line from config references
            file_path = config_file
            line_num = None
            if config and isinstance(config, list) and isinstance(config[0], dict):
                file_path = config[0].get("file", config_file)
                line_num = config[0].get("line", None)

            message = summary or description
            if summary and description and summary != description:
                message = f"{summary}: {description}"

            findings.append(Finding(
                tool=self.name,
                severity=severity,
                category=Category.WEB_SERVER,
                file=file_path,
                line=line_num,
                rule_id=f"gixy-{plugin}",
                rule_name=plugin,
                message=message[:500],
                docs_url=help_url,
                effort=Effort.LOW,
                blocks_deploy=severity in (Severity.CRITICAL, Severity.HIGH),
                raw=issue,
            ))

        return findings

    @staticmethod
    def _map_severity(text: str) -> Severity:
        mapping = {
            "critical": Severity.CRITICAL,
            "high": Severity.HIGH,
            "medium": Severity.MEDIUM,
            "low": Severity.LOW,
            "info": Severity.INFO,
            "warning": Severity.MEDIUM,
        }
        return mapping.get(text.lower(), Severity.MEDIUM)
