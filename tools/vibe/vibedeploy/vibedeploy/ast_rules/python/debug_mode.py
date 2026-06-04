"""Detect debug mode enabled in Python source."""

from __future__ import annotations

import re
from pathlib import Path

from vibedeploy.models import Category, Effort, Finding, Severity


class DebugModeRule:
    """Flag DEBUG=True, app.debug=True, FLASK_DEBUG=1 patterns."""

    rule_id = "py-debug-mode"
    rule_name = "Debug Mode Enabled"
    file_patterns = ("*.py",)

    _PATTERNS = [
        (re.compile(r'\bDEBUG\s*=\s*True\b'), "DEBUG=True"),
        (re.compile(r'\bapp\.debug\s*=\s*True\b'), "app.debug=True"),
        (re.compile(r'FLASK_DEBUG\s*=\s*["\']?1["\']?'), "FLASK_DEBUG=1"),
        (re.compile(r'FLASK_ENV\s*=\s*["\']?development["\']?'), "FLASK_ENV=development"),
        (re.compile(r'DJANGO_DEBUG\s*=\s*["\']?True["\']?'), "DJANGO_DEBUG=True"),
    ]

    def scan(self, target: str) -> list[Finding]:
        findings = []

        for py_file in Path(target).rglob("*.py"):
            # Skip test files and venv
            rel = str(py_file.relative_to(target))
            if any(skip in rel for skip in ("test", "venv", "node_modules", ".git")):
                continue

            try:
                content = py_file.read_text(errors="replace")
            except OSError:
                continue

            for i, line in enumerate(content.split("\n"), 1):
                # Skip comments
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue

                for pattern, desc in self._PATTERNS:
                    if pattern.search(line):
                        findings.append(Finding(
                            tool="ast",
                            severity=Severity.CRITICAL,
                            category=Category.AST,
                            file=rel,
                            line=i,
                            rule_id=self.rule_id,
                            rule_name=self.rule_name,
                            message=f"{desc} — debug mode must be disabled in production",
                            blocks_deploy=True,
                            effort=Effort.TRIVIAL,
                            fix_hint=f"Set to False or use environment variable",
                        ))

        return findings
