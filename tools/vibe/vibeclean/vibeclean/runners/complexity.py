"""Complexity runner -- AST-based structural issue detection."""

from __future__ import annotations

import ast
import time
from pathlib import Path

from vibeclean.models import Category, Finding, RunnerResult, RunnerStatus, Severity
from vibeclean.runners.base import BaseRunner

_CAT = Category.COMPLEXITY


class ComplexityRunner(BaseRunner):
    name = "complexity"

    def run(self) -> RunnerResult:
        start = time.monotonic()
        findings: list[Finding] = []
        py_files = self._collect_python_files()
        rc = self.runner_config
        max_lines = rc.get("max_function_lines", 50)
        max_depth = rc.get("max_nesting_depth", 4)
        max_params = rc.get("max_parameters", 6)
        god_lines = rc.get("god_file_lines", 500)
        god_defs = rc.get("god_file_definitions", 10)
        import_graph: dict[str, set[str]] = {}

        for py_file in py_files:
            tree = self._parse_file(py_file)
            lines = self._read_lines(py_file)
            rel = self._rel_path(py_file)
            if tree is None:
                continue
            findings.extend(self._check_long_functions(tree, rel, max_lines))
            findings.extend(self._check_deep_nesting(tree, rel, max_depth))
            findings.extend(self._check_god_files(tree, rel, lines, god_lines, god_defs))
            findings.extend(self._check_too_many_params(tree, rel, max_params))
            import_graph[self._file_to_module(py_file)] = self._collect_imports(tree)

        findings.extend(self._check_circular_imports(import_graph))
        return RunnerResult(
            runner=self.name, status=RunnerStatus.SUCCESS,
            findings=findings, duration_seconds=time.monotonic() - start,
        )

    def _check_long_functions(self, tree: ast.Module, file: str, limit: int) -> list[Finding]:
        findings: list[Finding] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            end = getattr(node, "end_lineno", None) or node.lineno
            length = end - node.lineno + 1
            if length > limit:
                findings.append(self._finding(
                    Severity.MEDIUM, _CAT, file, "long-function", "Long function",
                    f"'{node.name}' is {length} lines (max {limit})",
                    line=node.lineno, end_line=end,
                    fix_hint="Break into smaller, focused functions",
                ))
        return findings

    def _check_deep_nesting(self, tree: ast.Module, file: str, limit: int) -> list[Finding]:
        findings: list[Finding] = []
        reported: set[int] = set()
        nesting = (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.AsyncFor, ast.AsyncWith)

        def walk(node: ast.AST, depth: int) -> None:
            for child in ast.iter_child_nodes(node):
                d = depth + 1 if isinstance(child, nesting) else depth
                if d > limit and isinstance(child, nesting) and child.lineno not in reported:
                    reported.add(child.lineno)
                    findings.append(self._finding(
                        Severity.HIGH, _CAT, file, "deep-nesting", "Deeply nested code",
                        f"Nested {d} levels deep (max {limit})", line=child.lineno,
                        fix_hint="Extract into helpers or use early returns",
                    ))
                walk(child, d)

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                walk(node, 0)
        return findings

    def _check_god_files(self, tree: ast.Module, file: str, lines: list[str],
                         max_lines: int, max_defs: int) -> list[Finding]:
        if len(lines) <= max_lines:
            return []
        top = sum(1 for n in ast.iter_child_nodes(tree)
                  if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))
        if top > max_defs:
            return [self._finding(
                Severity.MEDIUM, _CAT, file, "god-file", "God file",
                f"{len(lines)} lines and {top} top-level definitions",
                line=1, fix_hint="Split into smaller, focused modules",
            )]
        return []

    def _check_too_many_params(self, tree: ast.Module, file: str, limit: int) -> list[Finding]:
        findings: list[Finding] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            a = node.args
            params = [x.arg for x in a.args + a.kwonlyargs + a.posonlyargs
                      if x.arg not in ("self", "cls")]
            if a.vararg:
                params.append(f"*{a.vararg.arg}")
            if a.kwarg:
                params.append(f"**{a.kwarg.arg}")
            if len(params) > limit:
                findings.append(self._finding(
                    Severity.LOW, _CAT, file, "too-many-params", "Too many parameters",
                    f"'{node.name}' has {len(params)} parameters (max {limit})",
                    line=node.lineno,
                    fix_hint="Group related parameters into a dataclass/config object",
                ))
        return findings

    def _file_to_module(self, path: Path) -> str:
        rel = path.relative_to(self.target)
        parts = list(rel.parts)
        if parts[-1] == "__init__.py":
            parts = parts[:-1]
        else:
            parts[-1] = parts[-1].replace(".py", "")
        return ".".join(parts)

    def _collect_imports(self, tree: ast.Module) -> set[str]:
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    imports.add(a.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        return imports

    def _check_circular_imports(self, graph: dict[str, set[str]]) -> list[Finding]:
        findings: list[Finding] = []
        visited: set[str] = set()
        reported: set[frozenset[str]] = set()

        def dfs(node: str, path: list[str], path_set: set[str]) -> None:
            if node in path_set:
                idx = path.index(node)
                cycle = path[idx:]
                key = frozenset(cycle)
                if key not in reported:
                    reported.add(key)
                    findings.append(self._finding(
                        Severity.HIGH, _CAT, node.replace(".", "/") + ".py",
                        "circular-import", "Circular import",
                        f"Cycle: {' -> '.join(cycle + [node])}",
                        line=1, fix_hint="Restructure imports or use lazy imports",
                    ))
                return
            if node in visited:
                return
            visited.add(node)
            path.append(node)
            path_set.add(node)
            for nb in graph.get(node, set()):
                if nb in graph:
                    dfs(nb, path, path_set)
            path.pop()
            path_set.discard(node)

        for module in graph:
            dfs(module, [], set())
        return findings
