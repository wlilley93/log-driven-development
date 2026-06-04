"""Detect process.env.X without fallback values."""

from __future__ import annotations

import re
from pathlib import Path

from vibedeploy.models import Category, Effort, Finding, Severity


class ProcessEnvNoFallbackRule:
    """Flag process.env.KEY used without || or ?? fallback."""

    rule_id = "js-env-no-fallback"
    rule_name = "Env No Fallback"
    file_patterns = ("*.js", "*.ts", "*.mjs", "*.cjs", "*.tsx", "*.jsx")

    # Match process.env.SOMETHING not followed by || or ?? or !
    _PATTERN = re.compile(r'process\.env\.([A-Z_][A-Z0-9_]*)\b(?!\s*(?:\|\||&&|\?\?|!|\.|\[))')

    # Skip patterns where the env var is being validated or assigned
    _SKIP_PATTERNS = [
        re.compile(r'if\s*\(\s*!?\s*process\.env'),
        re.compile(r'assert'),
        re.compile(r'throw\s'),
        re.compile(r'process\.env\.\w+\s*='),
        re.compile(r'console\.log'),
        re.compile(r'required.*process\.env'),
    ]

    def scan(self, target: str) -> list[Finding]:
        findings = []

        for ext in self.file_patterns:
            for js_file in Path(target).rglob(ext):
                rel = str(js_file.relative_to(target))
                if any(skip in rel for skip in ("node_modules", ".git", "test", "dist", "build", ".next")):
                    continue

                try:
                    content = js_file.read_text(errors="replace")
                except OSError:
                    continue

                for i, line in enumerate(content.split("\n"), 1):
                    stripped = line.strip()
                    if stripped.startswith("//") or stripped.startswith("*"):
                        continue

                    # Skip validation/assertion lines
                    if any(p.search(line) for p in self._SKIP_PATTERNS):
                        continue

                    match = self._PATTERN.search(line)
                    if match:
                        var_name = match.group(1)
                        findings.append(Finding(
                            tool="ast",
                            severity=Severity.MEDIUM,
                            category=Category.AST,
                            file=rel,
                            line=i,
                            rule_id=self.rule_id,
                            rule_name=self.rule_name,
                            message=f"process.env.{var_name} used without fallback — will be undefined if not set",
                            effort=Effort.TRIVIAL,
                            fix_hint=f"Add fallback: process.env.{var_name} || 'default' or ?? 'default'",
                        ))

        return findings
