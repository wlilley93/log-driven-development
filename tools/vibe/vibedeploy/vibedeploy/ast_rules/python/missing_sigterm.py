"""Detect missing SIGTERM handler in Python apps."""

from __future__ import annotations

import re
from pathlib import Path

from vibedeploy.models import Category, Effort, Finding, Severity


class MissingSigtermRule:
    """Flag Python apps without signal.signal(SIGTERM) handler."""

    rule_id = "py-no-sigterm"
    rule_name = "Missing SIGTERM Handler"
    file_patterns = ("*.py",)

    _SERVER_MARKERS = [
        "uvicorn", "gunicorn", "flask", "django", "fastapi",
        "http.server", "HTTPServer", "celery", "dramatiq",
    ]

    _SIGTERM_PATTERNS = [
        re.compile(r'signal\.signal\s*\(\s*signal\.SIGTERM'),
        re.compile(r'signal\.signal\s*\(\s*SIGTERM'),
        re.compile(r'atexit\.register'),
        re.compile(r'shutdown_event'),
        re.compile(r'on_shutdown'),
        re.compile(r'@app\.on_event\s*\(\s*["\']shutdown["\']'),
        re.compile(r'lifespan'),
    ]

    def scan(self, target: str) -> list[Finding]:
        is_server_app = False
        has_sigterm = False
        server_file = ""

        for py_file in Path(target).rglob("*.py"):
            rel = str(py_file.relative_to(target))
            if any(skip in rel for skip in ("venv", "node_modules", ".git", "test")):
                continue

            try:
                content = py_file.read_text(errors="replace")
            except OSError:
                continue

            if not is_server_app:
                for marker in self._SERVER_MARKERS:
                    if marker in content:
                        is_server_app = True
                        server_file = rel
                        break

            if not has_sigterm:
                for pattern in self._SIGTERM_PATTERNS:
                    if pattern.search(content):
                        has_sigterm = True
                        break

            if is_server_app and has_sigterm:
                break

        if is_server_app and not has_sigterm:
            return [Finding(
                tool="ast",
                severity=Severity.HIGH,
                category=Category.AST,
                file=server_file,
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                message="Server app detected but no SIGTERM handler found — may not shut down gracefully",
                effort=Effort.MEDIUM,
                fix_hint="Add signal.signal(signal.SIGTERM, handler) for graceful shutdown",
            )]

        return []
