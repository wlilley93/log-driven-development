"""Base class for analysis runners."""

from __future__ import annotations

import ast
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from vibeclean.config import Config
from vibeclean.models import Category, Finding, RunnerResult, RunnerStatus, Severity


class BaseRunner(ABC):
    """Base class for all analysis runners.

    Subclasses implement:
    - name: str -- runner identifier
    - run() -> RunnerResult -- execute analysis and return findings
    """

    name: str = ""

    def __init__(self, target: str, config: Config):
        self.target = target
        self.config = config

    @property
    def runner_config(self):
        return self.config.get_runner_config(self.name)

    def _collect_python_files(self) -> list[Path]:
        """Collect all .py files in the target, respecting exclusions."""
        target = Path(self.target)
        files = []
        for py_file in target.rglob("*.py"):
            rel = str(py_file.relative_to(target))
            if not self.config.is_path_excluded(rel):
                files.append(py_file)
        return sorted(files)

    def _parse_file(self, file_path: Path) -> ast.Module | None:
        """Parse a Python file into an AST. Returns None on parse error."""
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
            return ast.parse(source, filename=str(file_path))
        except (SyntaxError, ValueError):
            return None

    def _read_lines(self, file_path: Path) -> list[str]:
        """Read file lines. Returns empty list on error."""
        try:
            return file_path.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()
        except OSError:
            return []

    def _rel_path(self, file_path: Path) -> str:
        """Return path relative to target."""
        try:
            return str(file_path.relative_to(self.target))
        except ValueError:
            return str(file_path)

    def _finding(
        self, severity: Severity, category: Category, file: str,
        rule_id: str, rule_name: str, message: str,
        line: int | None = None, end_line: int | None = None,
        fix_hint: str | None = None,
    ) -> Finding:
        """Shorthand to create a Finding pre-filled with this runner's name."""
        return Finding(
            runner=self.name, severity=severity, category=category,
            file=file, rule_id=rule_id, rule_name=rule_name,
            message=message, line=line, end_line=end_line, fix_hint=fix_hint,
        )

    def _make_error_result(self, error: str) -> RunnerResult:
        return RunnerResult(runner=self.name, status=RunnerStatus.FAILED, error=error)

    @abstractmethod
    def run(self) -> RunnerResult:
        """Execute the analysis and return results."""
        ...
