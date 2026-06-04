"""Runner for the built-in AST analyser — runs Python and JS/TS rule modules."""

from __future__ import annotations

import importlib
import pkgutil
import time
from pathlib import Path
from typing import Any

import pathspec

from viberapid.ignore import load_ignore_spec
from viberapid.models import Finding, ToolResult, ToolStatus
from viberapid.runners.base import AsyncToolRunner

# Directories that should be skipped during file discovery
SKIP_DIRS = frozenset({
    "node_modules",
    "node_modules_bak",
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".tox",
    ".nox",
    ".venv",
    "venv",
    "env",
    ".env",
    "dist",
    "build",
    ".next",
    ".nuxt",
    ".output",
    "coverage",
    ".turbo",
    ".cache",
    ".parcel-cache",
    ".viberapid",
    "vendor",
    "bower_components",
})

# Directory name suffixes that trigger skipping (e.g. node_modules_bak, dist_bak)
SKIP_DIR_SUFFIXES = ("_bak",)

PYTHON_EXTENSIONS = frozenset({".py"})
JS_TS_EXTENSIONS = frozenset({".js", ".ts", ".jsx", ".tsx"})


def _discover_rule_modules(package_path: str) -> list[Any]:
    """Dynamically discover and import all rule modules from a package directory.

    Each rule module must expose a `check(filepath: str, source: str) -> list[Finding]`
    function.
    """
    modules: list[Any] = []
    pkg_dir = Path(package_path).resolve()

    if not pkg_dir.is_dir():
        return modules

    # Resolve the dotted module path relative to the viberapid package root.
    # The ast_rules dir lives at viberapid/ast_rules/{python,javascript}/
    # so we compute the path relative to the viberapid package directory.
    viberapid_pkg_dir = Path(__file__).resolve().parent.parent  # .../viberapid/
    try:
        rel = pkg_dir.relative_to(viberapid_pkg_dir)
        # rel is e.g. "ast_rules/python"
        dotted_prefix = "viberapid." + ".".join(rel.parts)
    except ValueError:
        return modules

    for module_info in pkgutil.iter_modules([str(pkg_dir)]):
        if module_info.name.startswith("_"):
            continue

        dotted = f"{dotted_prefix}.{module_info.name}"

        try:
            mod = importlib.import_module(dotted)
            if hasattr(mod, "check") and callable(mod.check):
                modules.append(mod)
        except Exception:
            # Skip modules that fail to import
            continue

    return modules


def _collect_files(
    target: Path,
    extensions: frozenset[str],
    changed_files: list[str] | None = None,
    ignore_spec: pathspec.PathSpec | None = None,
) -> list[Path]:
    """Recursively collect files matching the given extensions, skipping vendor dirs.

    If changed_files is provided, only return files whose path appears in that list.
    If ignore_spec is provided, files matching the spec are excluded.
    """
    changed_set: set[str] | None = None
    if changed_files is not None:
        changed_set = set(changed_files)

    result: list[Path] = []

    for item in target.rglob("*"):
        # Skip hidden and vendor directories (exact match or suffix match)
        if any(
            part in SKIP_DIRS or part.endswith(tuple(SKIP_DIR_SUFFIXES))
            for part in item.parts
        ):
            continue

        if not item.is_file():
            continue

        if item.suffix not in extensions:
            continue

        # Filter by .viberapidignore patterns
        if ignore_spec is not None:
            rel_path = str(item.relative_to(target)) if item.is_relative_to(target) else str(item)
            if ignore_spec.match_file(rel_path):
                continue

        # Filter by changed_files if provided
        if changed_set is not None:
            item_str = str(item)
            # Check both absolute and relative paths
            rel_path = str(item.relative_to(target)) if item.is_relative_to(target) else item_str
            if item_str not in changed_set and rel_path not in changed_set:
                continue

        result.append(item)

    return result


class AstAnalyserRunner(AsyncToolRunner):
    """Run built-in AST analysis rules on Python and JS/TS source files.

    This runner does NOT require any external tools — it uses Python's built-in
    `ast` module for Python files and regex-based pattern matching for JS/TS files.

    Tool config options (in .viberapid.yml):
        tools:
          ast-analyser:
            python: true       # Enable Python rules (default: true)
            javascript: true   # Enable JS/TS rules (default: true)
            typescript: true   # Enable TypeScript rules (default: true)
    """

    name = "ast-analyser"

    def should_run(self) -> bool:
        """Always run — no external dependencies required."""
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        target = Path(self.target)
        tool_cfg = self.tool_config
        ignore = self.ignore_spec

        python_enabled = tool_cfg.get("python", True)
        javascript_enabled = tool_cfg.get("javascript", True)
        typescript_enabled = tool_cfg.get("typescript", True)

        # Build the set of JS/TS extensions based on config
        js_extensions: set[str] = set()
        if javascript_enabled:
            js_extensions.update({".js", ".jsx"})
        if typescript_enabled:
            js_extensions.update({".ts", ".tsx"})

        all_findings: list[Finding] = []
        metrics: dict[str, Any] = {
            "python_files": 0,
            "js_ts_files": 0,
            "python_rules": 0,
            "js_rules": 0,
            "python_findings": 0,
            "js_findings": 0,
            "errors": 0,
        }

        # Discover rule modules
        ast_rules_dir = Path(__file__).resolve().parent.parent / "ast_rules"
        python_rules_dir = ast_rules_dir / "python"
        js_rules_dir = ast_rules_dir / "javascript"

        python_rule_modules = _discover_rule_modules(str(python_rules_dir)) if python_enabled else []
        js_rule_modules = _discover_rule_modules(str(js_rules_dir)) if (javascript_enabled or typescript_enabled) else []

        metrics["python_rules"] = len(python_rule_modules)
        metrics["js_rules"] = len(js_rule_modules)

        # --- Python files ---
        if python_enabled and python_rule_modules:
            py_files = _collect_files(target, PYTHON_EXTENSIONS, changed_files, ignore_spec=ignore)
            metrics["python_files"] = len(py_files)

            for py_file in py_files:
                try:
                    source = py_file.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    metrics["errors"] += 1
                    continue

                file_path = str(py_file)
                for rule_mod in python_rule_modules:
                    try:
                        findings = rule_mod.check(file_path, source)
                        all_findings.extend(findings)
                        metrics["python_findings"] += len(findings)
                    except Exception:
                        metrics["errors"] += 1

        # --- JS/TS files ---
        if js_extensions and js_rule_modules:
            js_files = _collect_files(target, frozenset(js_extensions), changed_files, ignore_spec=ignore)
            metrics["js_ts_files"] = len(js_files)

            for js_file in js_files:
                try:
                    source = js_file.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    metrics["errors"] += 1
                    continue

                file_path = str(js_file)
                for rule_mod in js_rule_modules:
                    try:
                        findings = rule_mod.check(file_path, source)
                        all_findings.extend(findings)
                        metrics["js_findings"] += len(findings)
                    except Exception:
                        metrics["errors"] += 1

        status = ToolStatus.SUCCESS
        if metrics["errors"] > 0 and not all_findings:
            status = ToolStatus.PARTIAL

        return ToolResult(
            tool=self.name,
            status=status,
            findings=all_findings,
            metrics=metrics,
        )
