"""Dead code runner -- AST-based detection of unused and unreachable code."""

from __future__ import annotations

import ast
import time
from pathlib import Path

from vibeclean.models import Category, Finding, RunnerResult, RunnerStatus, Severity
from vibeclean.runners.base import BaseRunner

_CAT = Category.DEAD_CODE


class DeadCodeRunner(BaseRunner):
    name = "dead_code"

    def run(self) -> RunnerResult:
        start = time.monotonic()
        findings: list[Finding] = []
        py_files = self._collect_python_files()
        imported_modules: set[str] = set()

        for py_file in py_files:
            tree = self._parse_file(py_file)
            if tree is None:
                continue
            rel = self._rel_path(py_file)
            findings.extend(self._check_unused_imports(tree, rel))
            findings.extend(self._check_unused_variables(tree, rel))
            findings.extend(self._check_unreachable_code(tree, rel))
            findings.extend(self._check_empty_bodies(tree, rel))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported_modules.add(alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported_modules.add(node.module.split(".")[0])

        findings.extend(self._check_orphaned_files(py_files, imported_modules))
        return RunnerResult(
            runner=self.name, status=RunnerStatus.SUCCESS,
            findings=findings, duration_seconds=time.monotonic() - start,
        )

    def _check_unused_imports(self, tree: ast.Module, file: str) -> list[Finding]:
        findings: list[Finding] = []
        imported: dict[str, int] = {}
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported[alias.asname or alias.name] = node.lineno
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name != "*":
                        imported[alias.asname or alias.name] = node.lineno
        if not imported:
            return findings

        used: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used.add(node.id)

        # Skip files with __all__ (re-export pattern)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "__all__":
                        return findings

        for name, line in imported.items():
            if name.startswith("_") or name in used:
                continue
            findings.append(self._finding(
                Severity.MEDIUM, _CAT, file, "unused-import", "Unused import",
                f"'{name}' is imported but never used", line=line,
                fix_hint=f"Remove the import of '{name}'",
            ))
        return findings

    def _check_unused_variables(self, tree: ast.Module, file: str) -> list[Finding]:
        findings: list[Finding] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            assigned: dict[str, int] = {}
            read: set[str] = set()
            for child in ast.walk(node):
                if isinstance(child, ast.Assign):
                    for t in child.targets:
                        if isinstance(t, ast.Name):
                            assigned[t.id] = child.lineno
                elif isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                    read.add(child.id)
            for name, line in assigned.items():
                if not name.startswith("_") and name not in read:
                    findings.append(self._finding(
                        Severity.LOW, _CAT, file, "unused-variable", "Unused variable",
                        f"'{name}' is assigned but never read", line=line,
                        fix_hint=f"Remove or use '{name}', or prefix with _",
                    ))
        return findings

    def _check_unreachable_code(self, tree: ast.Module, file: str) -> list[Finding]:
        findings: list[Finding] = []
        terminal = (ast.Return, ast.Raise, ast.Break, ast.Continue)
        for node in ast.walk(tree):
            for _, value in ast.iter_fields(node):
                if not isinstance(value, list):
                    continue
                for i, child in enumerate(value):
                    if isinstance(child, terminal) and i < len(value) - 1:
                        nxt = value[i + 1]
                        findings.append(self._finding(
                            Severity.MEDIUM, _CAT, file, "unreachable-code",
                            "Unreachable code",
                            f"Code after {type(child).__name__.lower()} is unreachable",
                            line=getattr(nxt, "lineno", None),
                            fix_hint="Remove the unreachable code",
                        ))
                        break
        return findings

    def _check_empty_bodies(self, tree: ast.Module, file: str) -> list[Finding]:
        findings: list[Finding] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            body = node.body
            is_empty = False
            if len(body) == 1:
                s = body[0]
                is_empty = isinstance(s, ast.Pass) or (
                    isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant)
                    and s.value.value is ...
                )
            elif len(body) == 2:
                f, s = body
                is_doc = (isinstance(f, ast.Expr) and isinstance(f.value, ast.Constant)
                          and isinstance(f.value.value, str))
                is_stub = isinstance(s, ast.Pass) or (
                    isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant)
                    and s.value.value is ...
                )
                is_empty = is_doc and is_stub
            if is_empty:
                findings.append(self._finding(
                    Severity.LOW, _CAT, file, "empty-body", "Empty function body",
                    f"Function '{node.name}' has an empty body",
                    line=node.lineno,
                    fix_hint="Implement the function or add a docstring explaining why",
                ))
        return findings

    def _check_orphaned_files(self, py_files: list[Path], imported: set[str]) -> list[Finding]:
        findings: list[Finding] = []
        skip_names = {"__init__", "__main__", "conftest", "setup", "manage", "wsgi", "asgi"}
        for py_file in py_files:
            name = py_file.stem
            if name.startswith("test_") or name in skip_names or name.startswith("__"):
                continue
            if name not in imported:
                rel = self._rel_path(py_file)
                parts = Path(rel).parts
                if not any(p.replace(".py", "") in imported for p in parts):
                    findings.append(self._finding(
                        Severity.LOW, _CAT, rel, "orphaned-file", "Orphaned file",
                        f"'{rel}' does not appear to be imported by any other file",
                        line=1, fix_hint="Remove if unused, or add to __init__.py",
                    ))
        return findings
