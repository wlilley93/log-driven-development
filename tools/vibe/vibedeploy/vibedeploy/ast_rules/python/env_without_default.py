"""Detect os.environ[] without .get() fallback."""

from __future__ import annotations

import re
from pathlib import Path

from vibedeploy.models import Category, Effort, Finding, Severity


class EnvWithoutDefaultRule:
    """Flag os.environ['KEY'] that should use os.environ.get('KEY', default)."""

    rule_id = "py-env-no-default"
    rule_name = "Env Without Default"
    file_patterns = ("*.py",)

    def scan(self, target: str) -> list[Finding]:
        findings = []
        # os.environ["KEY"] or os.environ['KEY'] without .get()
        pattern = re.compile(r'os\.environ\s*\[\s*[\'"](\w+)[\'"]\s*\]')

        for py_file in Path(target).rglob("*.py"):
            try:
                content = py_file.read_text(errors="replace")
            except OSError:
                continue

            rel_path = str(py_file.relative_to(target))

            for i, line in enumerate(content.split("\n"), 1):
                match = pattern.search(line)
                if match:
                    var_name = match.group(1)
                    findings.append(Finding(
                        tool="ast",
                        severity=Severity.MEDIUM,
                        category=Category.AST,
                        file=rel_path,
                        line=i,
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        message=f"os.environ['{var_name}'] will raise KeyError if not set — use os.environ.get('{var_name}', default)",
                        effort=Effort.TRIVIAL,
                        fix_hint=f"Replace with os.environ.get('{var_name}', '<default>')",
                    ))

        return findings
