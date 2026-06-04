"""Base class for tool runners."""

from __future__ import annotations

import json
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from vibescan.config import Config
from vibescan.installer import get_tool_bin
from vibescan.models import ToolResult, ToolStatus


class AsyncToolRunner(ABC):
    """Base class for all tool runners.

    Subclasses implement:
    - name: str — tool identifier
    - should_run() -> bool — pre-flight check
    - run() -> ToolResult — execute the tool and normalise findings
    """

    name: str = ""
    deep_only: bool = False
    is_secret_scanner: bool = False

    def __init__(self, target: str, config: Config):
        self.target = target
        self.config = config
        self.skip_reason: str | None = None

    @property
    def bin_path(self) -> str:
        return get_tool_bin(self.name)

    def _tool_exists(self) -> bool:
        """Check if this tool's binary is available (vibescan-managed or on PATH)."""
        path = self.bin_path
        if Path(path).exists():
            return True
        return shutil.which(path) is not None

    @property
    def tool_config(self):
        return self.config.get_tool_config(self.name)

    @property
    def global_excludes(self) -> list[str]:
        """Global exclude patterns from the top-level config."""
        return self.config.exclude

    def should_run(self) -> bool:
        """Return True if this tool should execute. Set self.skip_reason if not."""
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

        return subprocess.run(
            cmd,
            cwd=cwd or self.target,
            capture_output=True,
            text=True,
            timeout=timeout or self.config.timeout,
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
