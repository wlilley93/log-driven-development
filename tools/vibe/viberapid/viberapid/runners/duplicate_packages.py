"""Runner for duplicate-packages — finds packages at multiple versions in the lock file."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.duplicate_packages import DuplicatePackagesNormaliser
from viberapid.runners.base import AsyncToolRunner


class DuplicatePackagesRunner(AsyncToolRunner):
    """Parse package-lock.json or yarn.lock to find duplicate package versions."""

    name = "duplicate-packages"
    requires_node = True

    def should_run(self) -> bool:
        if not self._file_exists("package-lock.json", "yarn.lock"):
            self.skip_reason = "no package-lock.json or yarn.lock found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        lock_path = Path(self.target) / "package-lock.json"
        yarn_lock_path = Path(self.target) / "yarn.lock"

        if lock_path.exists():
            result = self._parse_npm_lockfile(lock_path)
        elif yarn_lock_path.exists():
            result = self._parse_yarn_lockfile(yarn_lock_path)
        else:
            return self._make_error_result("No lock file found")

        if result is None:
            return self._make_error_result("Failed to parse lock file")

        normaliser = DuplicatePackagesNormaliser()
        findings = normaliser.normalise(result)

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "total_duplicates": result.get("total_duplicates", 0),
                "unique_duplicate_packages": len(result.get("duplicates", {})),
            },
        )

    def _parse_npm_lockfile(self, lock_path: Path) -> dict[str, Any] | None:
        """Parse package-lock.json and find packages at multiple versions."""
        try:
            data = json.loads(lock_path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

        package_versions: dict[str, set[str]] = {}

        # package-lock.json v2/v3 uses "packages" key
        packages = data.get("packages", {})
        for pkg_path, info in packages.items():
            if not pkg_path or not isinstance(info, dict):
                continue
            version = info.get("version")
            if not version:
                continue

            # Extract package name from the path
            # e.g. "node_modules/lodash" -> "lodash"
            # e.g. "node_modules/@babel/core" -> "@babel/core"
            parts = pkg_path.split("node_modules/")
            if not parts:
                continue
            name = parts[-1]
            if not name or name.startswith("."):
                continue

            if name not in package_versions:
                package_versions[name] = set()
            package_versions[name].add(version)

        # Fall back to v1 "dependencies" (recursive)
        if not packages:
            self._collect_v1_deps(data.get("dependencies", {}), package_versions)

        duplicates = {
            name: sorted(versions)
            for name, versions in package_versions.items()
            if len(versions) > 1
        }

        return {
            "duplicates": duplicates,
            "total_duplicates": sum(len(v) - 1 for v in duplicates.values()),
        }

    def _collect_v1_deps(
        self,
        deps: dict[str, Any],
        versions: dict[str, set[str]],
    ) -> None:
        """Recursively collect versions from v1 lockfile format."""
        for name, info in deps.items():
            if not isinstance(info, dict):
                continue
            version = info.get("version")
            if version:
                if name not in versions:
                    versions[name] = set()
                versions[name].add(version)
            # Recurse into nested dependencies
            nested = info.get("dependencies", {})
            if nested:
                self._collect_v1_deps(nested, versions)

    def _parse_yarn_lockfile(self, lock_path: Path) -> dict[str, Any] | None:
        """Parse yarn.lock to find packages at multiple versions."""
        try:
            content = lock_path.read_text()
        except OSError:
            return None

        package_versions: dict[str, set[str]] = {}

        # yarn.lock format:
        # "package@^1.0.0", "package@~1.2.0":
        #   version "1.2.3"
        current_names: list[str] = []
        for line in content.split("\n"):
            stripped = line.strip()

            # Entry header line (package names)
            if stripped and not stripped.startswith("#") and not line.startswith(" "):
                current_names = []
                # Parse quoted or unquoted package specifiers
                specs = re.findall(r'"?([^@"\s,]+)@[^"\s,]+"?', stripped)
                current_names = list(set(specs))

            # Version line
            elif stripped.startswith("version "):
                version = stripped.split('"')[1] if '"' in stripped else stripped.split()[-1]
                for name in current_names:
                    if name not in package_versions:
                        package_versions[name] = set()
                    package_versions[name].add(version)

        duplicates = {
            name: sorted(versions)
            for name, versions in package_versions.items()
            if len(versions) > 1
        }

        return {
            "duplicates": duplicates,
            "total_duplicates": sum(len(v) - 1 for v in duplicates.values()),
        }
