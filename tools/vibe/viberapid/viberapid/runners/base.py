"""Base class for tool runners."""

from __future__ import annotations

import json
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from viberapid.config import Config
from viberapid.ignore import load_ignore_spec
from viberapid.installer import get_tool_bin
from viberapid.models import ToolResult, ToolStatus


_SENTINEL = object()


class AsyncToolRunner(ABC):
    """Base class for all tool runners.

    Subclasses implement:
    - name: str — tool identifier
    - should_run() -> bool — pre-flight check
    - run() -> ToolResult — execute the tool and normalise findings
    """

    name: str = ""
    requires_url: bool = False
    requires_node: bool = False
    requires_python: bool = False
    is_load_tester: bool = False

    def __init__(self, target: str, config: Config):
        self.target = target
        self.config = config
        self.skip_reason: str | None = None
        self._cached_ignore_spec: Any | None = _SENTINEL

    @property
    def ignore_spec(self):
        """Lazily load the .viberapidignore spec for the target directory."""
        if self._cached_ignore_spec is _SENTINEL:
            self._cached_ignore_spec = load_ignore_spec(self.target)
        return self._cached_ignore_spec

    @property
    def bin_path(self) -> str:
        return get_tool_bin(self.name)

    def _tool_exists(self) -> bool:
        """Check if this tool's binary is available (viberapid-managed or on PATH)."""
        path = self.bin_path
        if Path(path).exists():
            return True
        return shutil.which(path) is not None

    @property
    def tool_config(self):
        return self.config.get_tool_config(self.name)

    def should_run(self) -> bool:
        """Return True if this tool should execute. Set self.skip_reason if not."""
        if self.requires_url and not self.config.url:
            self.skip_reason = "no --url provided"
            return False
        return True

    @abstractmethod
    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        """Execute the tool and return normalised results."""
        ...

    def _exec(
        self,
        cmd: list[str],
        cwd: str | None = None,
        timeout: int | None = None,
        env: dict[str, str] | None = None,
        input_data: str | None = None,
    ) -> subprocess.CompletedProcess:
        """Run a subprocess."""
        import os

        run_env = os.environ.copy()
        if env:
            run_env.update(env)

        effective_timeout = timeout or self.config.timeout
        if self.is_load_tester:
            effective_timeout = max(effective_timeout, self.config.load_timeout)

        return subprocess.run(
            cmd,
            cwd=cwd or self.target,
            capture_output=True,
            text=True,
            timeout=effective_timeout,
            env=run_env,
            input=input_data,
        )

    def _exec_json(
        self,
        cmd: list[str],
        cwd: str | None = None,
        timeout: int | None = None,
        env: dict[str, str] | None = None,
    ) -> tuple[Any | None, str]:
        """Run a subprocess and parse JSON stdout. Returns (data, stderr)."""
        result = self._exec(cmd, cwd=cwd, timeout=timeout, env=env)
        stderr = result.stderr.strip()
        if result.stdout.strip():
            try:
                return json.loads(result.stdout), stderr
            except json.JSONDecodeError:
                pass
        return None, stderr

    def _make_error_result(self, error: str) -> ToolResult:
        return ToolResult(tool=self.name, status=ToolStatus.FAILED, error=error)

    def _file_exists(self, *names: str) -> bool:
        """Check if any of the named files exist in the target directory."""
        for name in names:
            if (Path(self.target) / name).exists():
                return True
        return False

    def _glob_files(self, *patterns: str) -> list[Path]:
        """Glob for files matching any of the patterns, respecting .viberapidignore."""
        target = Path(self.target)
        files = []
        for pattern in patterns:
            files.extend(target.rglob(pattern))
        spec = self.ignore_spec
        if spec is not None:
            files = [
                f for f in files
                if not spec.match_file(str(f.relative_to(target)))
            ]
        return files

    def _apply_tool_excludes(self, files: list[Path]) -> list[Path]:
        """Filter out files matching per-tool exclude patterns from config.

        Reads the ``exclude`` key from the tool's config in .viberapid.yml
        (a list of path substrings or glob-style patterns) and removes any
        matching files.
        """
        excludes: list[str] = self.tool_config.get("exclude") or []
        if not excludes:
            return files
        import fnmatch

        target = Path(self.target)
        filtered: list[Path] = []
        for f in files:
            rel = str(f.relative_to(target))
            if any(
                pattern in rel or fnmatch.fnmatch(rel, pattern)
                for pattern in excludes
            ):
                continue
            filtered.append(f)
        return filtered

    def _npx_path(self) -> str:
        """Get path to npx, preferring viberapid-managed node."""
        managed = get_tool_bin("npx")
        if Path(managed).exists():
            return managed
        return shutil.which("npx") or "npx"
