"""Base class for test quality runners."""

from __future__ import annotations

import ast
from abc import ABC, abstractmethod
from pathlib import Path

from vibetest.config import Config
from vibetest.models import RunnerResult, RunnerStatus


class BaseRunner(ABC):
    """Base class for all test quality runners.

    Subclasses implement:
    - name: str -- runner identifier
    - should_run() -> bool -- pre-flight check
    - run() -> RunnerResult -- execute analysis and produce findings
    """

    name: str = ""

    def __init__(self, target: str, config: Config):
        self.target = target
        self.config = config
        self.skip_reason: str | None = None

    @property
    def runner_config(self):
        return self.config.get_runner_config(self.name)

    def should_run(self) -> bool:
        """Return True if this runner should execute. Set self.skip_reason if not."""
        return True

    @abstractmethod
    def run(self) -> RunnerResult:
        """Execute the analysis and return results."""
        ...

    def _make_error_result(self, error: str) -> RunnerResult:
        return RunnerResult(runner=self.name, status=RunnerStatus.FAILED, error=error)

    def _find_python_files(self, root: Path | None = None) -> list[Path]:
        """Find all .py files under the target, respecting excludes."""
        root = root or Path(self.target)
        files = []
        for p in root.rglob("*.py"):
            rel = str(p.relative_to(Path(self.target)))
            if not self.config.is_path_excluded(rel):
                files.append(p)
        return files

    def _find_test_files(self) -> list[Path]:
        """Find test files (test_*.py or *_test.py) under the target."""
        target = Path(self.target)
        files = []
        for p in target.rglob("*.py"):
            rel = str(p.relative_to(target))
            if self.config.is_path_excluded(rel):
                continue
            if p.name.startswith("test_") or p.name.endswith("_test.py"):
                files.append(p)
        return files

    def _find_source_files(self) -> list[Path]:
        """Find non-test Python source files under the target."""
        target = Path(self.target)
        files = []
        for p in target.rglob("*.py"):
            rel = str(p.relative_to(target))
            if self.config.is_path_excluded(rel):
                continue
            if p.name.startswith("test_") or p.name.endswith("_test.py"):
                continue
            if p.name == "conftest.py":
                continue
            files.append(p)
        return files

    def _parse_ast(self, file_path: Path) -> ast.Module | None:
        """Parse a Python file into an AST, returning None on failure."""
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
            return ast.parse(source, filename=str(file_path))
        except (SyntaxError, ValueError):
            return None
