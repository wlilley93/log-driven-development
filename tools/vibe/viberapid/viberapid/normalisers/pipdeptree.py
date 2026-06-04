"""Normaliser for pipdeptree output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser

# Depth threshold for flagging deep dependency chains
DEEP_CHAIN_THRESHOLD = 5

# Depth threshold for critical dependency depth
CRITICAL_DEPTH_THRESHOLD = 8


class PipdeptreeNormaliser(BaseNormaliser):
    """Convert pipdeptree JSON output to Finding objects.

    pipdeptree --json shape:
    [
      {
        "package": {
          "package_name": "requests",
          "installed_version": "2.31.0",
          "key": "requests"
        },
        "dependencies": [
          {
            "package_name": "urllib3",
            "installed_version": "2.1.0",
            "required_version": ">=1.21.1,<3",
            "key": "urllib3"
          }
        ]
      }
    ]
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, list):
            return []

        findings: list[Finding] = []

        # Track all packages and their dependency depths
        depth_map: dict[str, int] = {}
        self._build_depth_map(raw_data, depth_map)

        # Detect deep dependency chains
        for pkg_name, depth in depth_map.items():
            if depth >= DEEP_CHAIN_THRESHOLD:
                severity = (
                    Severity.HIGH if depth >= CRITICAL_DEPTH_THRESHOLD
                    else Severity.MEDIUM
                )
                findings.append(Finding(
                    tool="pipdeptree",
                    severity=severity,
                    category=Category.DEPENDENCY,
                    file="requirements.txt",
                    rule_id="pipdeptree/deep-chain",
                    rule_name="Deep dependency chain",
                    message=(
                        f"Package '{pkg_name}' has a dependency chain {depth} levels deep. "
                        f"Deep chains increase install time, disk usage, and supply chain risk."
                    ),
                    fix_hint=_deep_chain_hint(pkg_name, depth),
                    metric="dependency_depth",
                    current_value=float(depth),
                    target_value=float(DEEP_CHAIN_THRESHOLD),
                    effort=Effort.HIGH,
                    raw={"package": pkg_name, "depth": depth},
                ))

        # Detect version conflicts
        for pkg_entry in raw_data:
            if not isinstance(pkg_entry, dict):
                continue

            pkg_info = pkg_entry.get("package", {})
            if not isinstance(pkg_info, dict):
                continue

            pkg_name = pkg_info.get("package_name", "unknown")
            installed = pkg_info.get("installed_version", "")
            deps = pkg_entry.get("dependencies", [])

            if not isinstance(deps, list):
                continue

            for dep in deps:
                if not isinstance(dep, dict):
                    continue

                dep_name = dep.get("package_name", "unknown")
                dep_installed = dep.get("installed_version", "")
                dep_required = dep.get("required_version", "")

                # pipdeptree marks conflicts in the required_version field
                if dep_installed and dep_required and not _version_satisfies(dep_installed, dep_required):
                    findings.append(Finding(
                        tool="pipdeptree",
                        severity=Severity.HIGH,
                        category=Category.DEPENDENCY,
                        file="requirements.txt",
                        rule_id="pipdeptree/version-conflict",
                        rule_name="Dependency version conflict",
                        message=(
                            f"'{pkg_name}' requires '{dep_name}{dep_required}' but "
                            f"'{dep_installed}' is installed. This may cause runtime errors."
                        ),
                        fix_hint=(
                            f"Resolve the version conflict: either upgrade/downgrade "
                            f"'{dep_name}' to satisfy '{dep_required}', or find a version "
                            f"of '{pkg_name}' compatible with '{dep_name}=={dep_installed}'. "
                            f"Run `pip install '{dep_name}{dep_required}'` to attempt resolution."
                        ),
                        effort=Effort.MEDIUM,
                        raw={
                            "parent": pkg_name,
                            "dependency": dep_name,
                            "installed": dep_installed,
                            "required": dep_required,
                        },
                    ))

        return findings

    def _build_depth_map(
        self,
        packages: list[dict[str, Any]],
        depth_map: dict[str, int],
    ) -> None:
        """Build a map of package name -> max dependency depth."""
        for pkg_entry in packages:
            if not isinstance(pkg_entry, dict):
                continue

            pkg_info = pkg_entry.get("package", {})
            if not isinstance(pkg_info, dict):
                continue

            pkg_name = pkg_info.get("package_name", "unknown")
            depth = self._calc_max_depth(pkg_entry)
            depth_map[pkg_name] = max(depth_map.get(pkg_name, 0), depth)

    def _calc_max_depth(self, pkg_entry: dict[str, Any], current: int = 0) -> int:
        """Recursively calculate the maximum dependency depth."""
        deps = pkg_entry.get("dependencies", [])
        if not isinstance(deps, list) or not deps:
            return current

        max_depth = current
        for dep in deps:
            if isinstance(dep, dict):
                child_depth = self._calc_max_depth(dep, current + 1)
                max_depth = max(max_depth, child_depth)

        return max_depth


def _version_satisfies(installed: str, required: str) -> bool:
    """Basic check if installed version satisfies requirement.

    This is a simplified check — for complex specifiers, we conservatively
    return True (no false positives). pipdeptree itself does the real check
    and marks conflicts.
    """
    if not required or required == "Any":
        return True

    # If pipdeptree output already cleaned the requirement to just a version
    # or if it contains complex specifiers, be conservative
    try:
        # Simple equality check: ==X.Y.Z
        if required.startswith("=="):
            return installed == required[2:]
        # For complex specifiers (>=, <=, !=, ~=, etc.), defer to pipdeptree
        return True
    except Exception:
        return True


def _deep_chain_hint(pkg_name: str, depth: int) -> str:
    """Generate a fix hint for deep dependency chains."""
    if depth >= CRITICAL_DEPTH_THRESHOLD:
        return (
            f"'{pkg_name}' has an extremely deep dependency tree ({depth} levels). "
            "Consider: replacing it with a lighter alternative, pinning a version with "
            "fewer transitive deps, or using `pip-compile` with `--no-annotate` to "
            "flatten and audit the full tree. Deep chains increase vulnerability surface."
        )
    return (
        f"'{pkg_name}' has a dependency chain {depth} levels deep (threshold: "
        f"{DEEP_CHAIN_THRESHOLD}). Review if all transitive dependencies are necessary. "
        "Consider using `pip-tools` or `poetry` to manage and audit the dependency tree. "
        "Lighter alternatives may exist."
    )
