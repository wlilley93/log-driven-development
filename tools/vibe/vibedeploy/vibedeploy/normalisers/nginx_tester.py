"""Normaliser for nginx -t output."""

from __future__ import annotations

import re
from typing import Any

from vibedeploy.models import Category, Effort, Finding, Severity
from vibedeploy.normalisers.base import BaseNormaliser

# nginx error patterns
NGINX_ERROR = re.compile(
    r"""nginx:\s+\[(?P<level>emerg|alert|crit|error|warn|notice|info)\]\s+(?P<message>.+?)(?:\s+in\s+(?P<file>[^:]+):(?P<line>\d+))?$"""
)
NGINX_FAILED = re.compile(r"""nginx:.*configuration.*failed""", re.IGNORECASE)
NGINX_OK = re.compile(r"""nginx:.*syntax is ok""", re.IGNORECASE)


class NginxTesterNormaliser(BaseNormaliser):
    tool_name = "nginx_tester"

    def normalise(self, raw_data: Any) -> list[Finding]:
        findings: list[Finding] = []
        output = raw_data.get("output", "")
        returncode = raw_data.get("returncode", 1)
        config_file = raw_data.get("config_file", "nginx.conf")

        for line in output.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            match = NGINX_ERROR.match(line)
            if match:
                level = match.group("level")
                message = match.group("message")
                file_path = match.group("file") or config_file
                line_num = int(match.group("line")) if match.group("line") else None

                severity = self._level_to_severity(level)

                findings.append(Finding(
                    tool=self.tool_name,
                    severity=severity,
                    category=Category.WEB_SERVER,
                    file=file_path,
                    line=line_num,
                    rule_id=f"nginx-{level}",
                    rule_name=f"nginx {level}",
                    message=message,
                    effort=Effort.LOW,
                    blocks_deploy=severity in (Severity.CRITICAL, Severity.HIGH),
                ))

        # If nginx -t completely failed and no specific errors parsed
        if returncode != 0 and not findings:
            findings.append(Finding(
                tool=self.tool_name,
                severity=Severity.CRITICAL,
                category=Category.WEB_SERVER,
                file=config_file,
                rule_id="nginx-config-invalid",
                rule_name="Invalid nginx Configuration",
                message=f"nginx configuration test failed: {output[:300]}",
                effort=Effort.MEDIUM,
                blocks_deploy=True,
            ))

        return findings

    @staticmethod
    def _level_to_severity(level: str) -> Severity:
        mapping = {
            "emerg": Severity.CRITICAL,
            "alert": Severity.CRITICAL,
            "crit": Severity.CRITICAL,
            "error": Severity.HIGH,
            "warn": Severity.MEDIUM,
            "notice": Severity.LOW,
            "info": Severity.INFO,
        }
        return mapping.get(level, Severity.MEDIUM)
