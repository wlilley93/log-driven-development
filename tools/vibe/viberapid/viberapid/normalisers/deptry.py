"""Normaliser for deptry output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser

# deptry error codes and their classifications
DEPTRY_CODES = {
    "DEP001": {
        "name": "Missing dependency",
        "severity": Severity.HIGH,
        "effort": Effort.LOW,
        "description": "A package is imported but not declared as a dependency.",
    },
    "DEP002": {
        "name": "Unused dependency",
        "severity": Severity.MEDIUM,
        "effort": Effort.LOW,
        "description": "A package is declared as a dependency but not imported.",
    },
    "DEP003": {
        "name": "Transitive dependency used directly",
        "severity": Severity.LOW,
        "effort": Effort.LOW,
        "description": "A transitive dependency is imported directly instead of via its parent.",
    },
    "DEP004": {
        "name": "Misplaced dev dependency",
        "severity": Severity.MEDIUM,
        "effort": Effort.LOW,
        "description": "A dev dependency is imported in non-dev code.",
    },
}


class DeptryNormaliser(BaseNormaliser):
    """Convert deptry JSON output to Finding objects.

    deptry JSON output shape (list of violations):
    [
      {
        "error": {
          "code": "DEP002",
          "message": "'flask' defined as a dependency but not used in the codebase"
        },
        "module": "flask",
        "location": {
          "file": "pyproject.toml",
          "line": 15,
          "column": 0
        }
      }
    ]

    Alternative shape (flattened):
    [
      {
        "code": "DEP001",
        "message": "...",
        "module": "requests",
        "file": "src/api.py",
        "line": 3
      }
    ]
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, list):
            return []

        findings: list[Finding] = []

        for issue in raw_data:
            if not isinstance(issue, dict):
                continue

            finding = self._normalise_issue(issue)
            if finding:
                findings.append(finding)

        return findings

    def _normalise_issue(self, issue: dict[str, Any]) -> Finding | None:
        """Convert a single deptry issue to a Finding."""
        # Extract fields from nested or flat format
        error = issue.get("error", {})
        if isinstance(error, dict):
            code = error.get("code", "")
            message = error.get("message", "")
        else:
            code = issue.get("code", "")
            message = issue.get("message", "")

        module = issue.get("module", "unknown")

        # Extract location from nested or flat format
        location = issue.get("location", {})
        if isinstance(location, dict):
            filepath = location.get("file", "pyproject.toml")
            line = location.get("line")
            col = location.get("column")
        else:
            filepath = issue.get("file", "pyproject.toml")
            line = issue.get("line")
            col = issue.get("column")

        if not code and not message:
            return None

        code_info = DEPTRY_CODES.get(code, {})
        severity = code_info.get("severity", Severity.MEDIUM) if code_info else Severity.MEDIUM
        effort = code_info.get("effort", Effort.MEDIUM) if code_info else Effort.MEDIUM
        rule_name = code_info.get("name", code) if code_info else code

        if not message:
            message = code_info.get("description", f"Dependency issue ({code})") if code_info else f"Dependency issue: {module}"

        fix_hint = self._build_fix_hint(code, module)

        return Finding(
            tool="deptry",
            severity=severity,
            category=Category.DEPENDENCY,
            file=filepath,
            rule_id=f"deptry/{code}" if code else "deptry/unknown",
            rule_name=rule_name,
            message=message,
            line=line,
            col=col,
            fix_hint=fix_hint,
            effort=effort,
            raw=issue,
        )

    def _build_fix_hint(self, code: str, module: str) -> str:
        """Generate a targeted fix hint based on the error code."""
        if code == "DEP001":
            return (
                f"Package '{module}' is imported but not in your dependency list. "
                f"Add it: `pip install {module}` and add to pyproject.toml or "
                f"requirements.txt. Without this, builds on fresh environments will fail."
            )

        if code == "DEP002":
            return (
                f"Package '{module}' is declared as a dependency but never imported. "
                f"Remove it from pyproject.toml/requirements.txt to reduce install size "
                f"and attack surface, or verify it is used via a plugin, CLI, or dynamic import."
            )

        if code == "DEP003":
            return (
                f"Package '{module}' is a transitive dependency (installed by another "
                f"package) but imported directly. Add '{module}' to your direct dependencies "
                f"to prevent breakage if the parent package drops it in a future version."
            )

        if code == "DEP004":
            return (
                f"Package '{module}' is a dev dependency but is imported in production code. "
                f"Either move it to regular dependencies, or restructure the code so "
                f"production paths do not import dev-only packages."
            )

        return (
            f"Review the dependency declaration for '{module}'. "
            f"Run `deptry .` for detailed analysis."
        )
