"""Detect CORS wildcard origin in JavaScript/TypeScript."""

from __future__ import annotations

import re
from pathlib import Path

from vibedeploy.models import Category, Effort, Finding, Severity


class CorsWildcardRule:
    """Flag origin: '*' in CORS configuration."""

    rule_id = "js-cors-wildcard"
    rule_name = "CORS Wildcard Origin"
    file_patterns = ("*.js", "*.ts", "*.mjs", "*.cjs", "*.tsx", "*.jsx")

    _PATTERNS = [
        re.compile(r'''origin\s*:\s*['"]?\*['"]?'''),
        re.compile(r'''Access-Control-Allow-Origin['"]\s*,\s*['"]?\*['"]?'''),
        re.compile(r'''cors\s*\(\s*\)'''),  # cors() with no config = wildcard
        re.compile(r'''allowedOrigins?\s*:\s*\[\s*['"]?\*['"]?\s*\]'''),
    ]

    def scan(self, target: str) -> list[Finding]:
        findings = []

        for ext in self.file_patterns:
            for js_file in Path(target).rglob(ext):
                rel = str(js_file.relative_to(target))
                if any(skip in rel for skip in ("node_modules", ".git", "test", "dist", "build")):
                    continue

                try:
                    content = js_file.read_text(errors="replace")
                except OSError:
                    continue

                for i, line in enumerate(content.split("\n"), 1):
                    stripped = line.strip()
                    if stripped.startswith("//") or stripped.startswith("*"):
                        continue

                    for pattern in self._PATTERNS:
                        if pattern.search(line):
                            findings.append(Finding(
                                tool="ast",
                                severity=Severity.HIGH,
                                category=Category.AST,
                                file=rel,
                                line=i,
                                rule_id=self.rule_id,
                                rule_name=self.rule_name,
                                message="CORS wildcard origin (*) allows any domain — restrict to specific origins in production",
                                blocks_deploy=True,
                                effort=Effort.LOW,
                                fix_hint="Set origin to specific allowed domains",
                            ))
                            break  # one finding per line

        return findings
