"""Detect missing health check endpoint in Python web apps."""

from __future__ import annotations

import re
from pathlib import Path

from vibedeploy.models import Category, Effort, Finding, Severity


class MissingHealthCheckRule:
    """Flag Python web apps without a /health or /healthz route."""

    rule_id = "py-no-health-check"
    rule_name = "Missing Health Check"
    file_patterns = ("*.py",)

    _FRAMEWORK_MARKERS = [
        "flask", "Flask", "fastapi", "FastAPI", "django", "Django",
        "from starlette", "from sanic", "from aiohttp",
    ]

    _HEALTH_PATTERNS = [
        re.compile(r'["\'/]health["\']'),
        re.compile(r'["\'/]healthz["\']'),
        re.compile(r'["\'/]readiness["\']'),
        re.compile(r'["\'/]liveness["\']'),
        re.compile(r'["\'/]ping["\']'),
        re.compile(r'health_check'),
        re.compile(r'healthcheck'),
    ]

    def scan(self, target: str) -> list[Finding]:
        is_web_app = False
        has_health_check = False
        web_framework_file = ""

        for py_file in Path(target).rglob("*.py"):
            rel = str(py_file.relative_to(target))
            if any(skip in rel for skip in ("venv", "node_modules", ".git", "test")):
                continue

            try:
                content = py_file.read_text(errors="replace")
            except OSError:
                continue

            # Check if this is a web framework app
            if not is_web_app:
                for marker in self._FRAMEWORK_MARKERS:
                    if marker in content:
                        is_web_app = True
                        web_framework_file = rel
                        break

            # Check for health check endpoints
            if not has_health_check:
                for pattern in self._HEALTH_PATTERNS:
                    if pattern.search(content):
                        has_health_check = True
                        break

            if is_web_app and has_health_check:
                break

        if is_web_app and not has_health_check:
            return [Finding(
                tool="ast",
                severity=Severity.HIGH,
                category=Category.AST,
                file=web_framework_file,
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                message="Python web app detected but no /health or /healthz endpoint found",
                blocks_deploy=True,
                effort=Effort.LOW,
                fix_hint="Add a /health endpoint that returns 200 OK",
                docs_url="https://12factor.net/admin-processes",
            )]

        return []
