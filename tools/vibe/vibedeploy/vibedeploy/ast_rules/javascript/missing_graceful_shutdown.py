"""Detect missing graceful shutdown handler in Node.js apps."""

from __future__ import annotations

import re
from pathlib import Path

from vibedeploy.models import Category, Effort, Finding, Severity


class MissingGracefulShutdownRule:
    """Flag Node.js server apps without SIGTERM handler."""

    rule_id = "js-no-graceful-shutdown"
    rule_name = "Missing Graceful Shutdown"
    file_patterns = ("*.js", "*.ts", "*.mjs", "*.cjs")

    _SERVER_PATTERNS = [
        re.compile(r'\.listen\s*\('),
        re.compile(r'createServer\s*\('),
        re.compile(r'''require\s*\(\s*['"]express['"]\s*\)'''),
        re.compile(r'''from\s+['"]express['"]'''),
        re.compile(r'''require\s*\(\s*['"]fastify['"]\s*\)'''),
        re.compile(r'''from\s+['"]fastify['"]'''),
        re.compile(r'''require\s*\(\s*['"]koa['"]\s*\)'''),
    ]

    _SHUTDOWN_PATTERNS = [
        re.compile(r'''process\.on\s*\(\s*['"]SIGTERM['"]'''),
        re.compile(r'''process\.on\s*\(\s*['"]SIGINT['"]'''),
        re.compile(r'gracefulShutdown'),
        re.compile(r'graceful.*shutdown', re.IGNORECASE),
        re.compile(r'server\.close\s*\('),
    ]

    def scan(self, target: str) -> list[Finding]:
        has_server = False
        has_shutdown = False
        server_file = ""

        for ext in self.file_patterns:
            for js_file in Path(target).rglob(ext):
                rel = str(js_file.relative_to(target))
                if any(skip in rel for skip in ("node_modules", ".git", "test", "dist")):
                    continue

                try:
                    content = js_file.read_text(errors="replace")
                except OSError:
                    continue

                if not has_server:
                    for pattern in self._SERVER_PATTERNS:
                        if pattern.search(content):
                            has_server = True
                            server_file = rel
                            break

                if not has_shutdown:
                    for pattern in self._SHUTDOWN_PATTERNS:
                        if pattern.search(content):
                            has_shutdown = True
                            break

                if has_server and has_shutdown:
                    break
            if has_server and has_shutdown:
                break

        if has_server and not has_shutdown:
            return [Finding(
                tool="ast",
                severity=Severity.HIGH,
                category=Category.AST,
                file=server_file,
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                message="Node.js server without SIGTERM handler — may not shut down gracefully",
                effort=Effort.LOW,
                fix_hint="Add process.on('SIGTERM', () => { server.close(); process.exit(0); })",
            )]

        return []
