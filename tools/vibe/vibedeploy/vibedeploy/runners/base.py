"""Base class for tool runners."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from vibedeploy.config import Config
from vibedeploy.installer import get_tool_bin
from vibedeploy.models import ToolResult, ToolStatus


class AsyncToolRunner(ABC):
    """Base class for all tool runners.

    Subclasses implement:
    - name: str — tool identifier
    - should_run() -> bool — pre-flight check
    - run() -> ToolResult — execute the tool and normalise findings
    """

    name: str = ""
    requires_url: bool = False
    requires_docker: bool = False
    requires_k8s: bool = False
    requires_cloud: bool = False

    def __init__(self, target: str, config: Config):
        self.target = target
        self.config = config
        self.skip_reason: str | None = None

    @property
    def bin_path(self) -> str:
        return get_tool_bin(self.name)

    def _tool_exists(self) -> bool:
        """Check if this tool's binary is available."""
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
            self.skip_reason = "requires --url"
            return False
        if self.requires_docker and not self._file_exists("Dockerfile", "docker-compose.yml", "docker-compose.yaml"):
            self.skip_reason = "no Dockerfile found"
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

    # Directories to skip when scanning source files
    _SKIP_DIRS = frozenset({
        "node_modules", ".git", "__pycache__", ".next", "venv", ".venv",
        "vendor", "dist", "build", ".tox", ".eggs", "coverage", ".mypy_cache",
        ".pytest_cache", ".cache", "bower_components",
    })

    def _scan_files(self, *patterns: str, skip_vendor: bool = True, max_files: int = 5000) -> list[Path]:
        """Find files matching glob patterns in the target directory.

        Uses os.walk to skip vendor dirs (node_modules, .git, etc.) BEFORE
        descending, which is orders of magnitude faster than rglob on large projects.
        """
        import fnmatch

        target_path = Path(self.target)
        results: list[Path] = []

        # Extract the filename-only pattern from each glob (strip leading **/)
        file_patterns: list[str] = []
        for pattern in patterns:
            # Normalise: "**/*.ts" -> "*.ts", "*server*.ts" stays as-is
            p = pattern
            while p.startswith("**/") or p.startswith("*/"):
                p = p.split("/", 1)[1] if "/" in p else p
                break
            # If pattern still has path separators, it's a complex glob — fall back
            if "/" in p:
                file_patterns.append(p.rsplit("/", 1)[-1])
            else:
                file_patterns.append(p)

        for dirpath, dirnames, filenames in os.walk(target_path):
            # Prune skip dirs IN-PLACE so os.walk won't descend into them
            if skip_vendor:
                dirnames[:] = [d for d in dirnames if d not in self._SKIP_DIRS]

            for filename in filenames:
                for fp in file_patterns:
                    if fnmatch.fnmatch(filename, fp):
                        results.append(Path(dirpath) / filename)
                        if len(results) >= max_files:
                            return results
                        break  # Don't match same file against multiple patterns

        return results

    def _read_file(self, path: str | Path) -> str:
        """Read a file relative to target, return empty string on error."""
        try:
            full_path = Path(self.target) / path if not Path(path).is_absolute() else Path(path)
            return full_path.read_text(errors="replace")
        except (OSError, UnicodeDecodeError):
            return ""
