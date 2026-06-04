"""Detect Express apps without helmet() middleware."""

from __future__ import annotations

import re
from pathlib import Path

from vibedeploy.models import Category, Effort, Finding, Severity


class MissingHelmetRule:
    """Flag Express apps that don't use helmet() for security headers."""

    rule_id = "js-no-helmet"
    rule_name = "Missing Helmet"
    file_patterns = ("*.js", "*.ts", "*.mjs", "*.cjs")

    _EXPRESS_PATTERNS = [
        re.compile(r'''require\s*\(\s*['"]express['"]\s*\)'''),
        re.compile(r'''from\s+['"]express['"]'''),
        re.compile(r'''express\s*\(\s*\)'''),
    ]

    _HELMET_PATTERNS = [
        re.compile(r'helmet\s*\('),
        re.compile(r'''require\s*\(\s*['"]helmet['"]\s*\)'''),
        re.compile(r'''from\s+['"]helmet['"]'''),
    ]

    def scan(self, target: str) -> list[Finding]:
        has_express = False
        has_helmet = False
        express_file = ""

        for ext in self.file_patterns:
            for js_file in Path(target).rglob(ext):
                rel = str(js_file.relative_to(target))
                if any(skip in rel for skip in ("node_modules", ".git", "test", "dist")):
                    continue

                try:
                    content = js_file.read_text(errors="replace")
                except OSError:
                    continue

                if not has_express:
                    for pattern in self._EXPRESS_PATTERNS:
                        if pattern.search(content):
                            has_express = True
                            express_file = rel
                            break

                if not has_helmet:
                    for pattern in self._HELMET_PATTERNS:
                        if pattern.search(content):
                            has_helmet = True
                            break

                if has_express and has_helmet:
                    break
            if has_express and has_helmet:
                break

        if has_express and not has_helmet:
            return [Finding(
                tool="ast",
                severity=Severity.HIGH,
                category=Category.AST,
                file=express_file,
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                message="Express app without helmet() — missing security headers",
                effort=Effort.TRIVIAL,
                fix_hint="npm install helmet && app.use(helmet())",
                fix_command="npm install helmet",
            )]

        return []
