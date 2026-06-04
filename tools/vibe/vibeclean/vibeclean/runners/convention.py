"""Convention runner -- consistency checks for naming, style, imports."""

from __future__ import annotations

import ast
import re
import time

from vibeclean.models import Category, Finding, RunnerResult, RunnerStatus, Severity
from vibeclean.runners.base import BaseRunner

_CAT = Category.CONVENTION
_CAMEL = re.compile(r"^[a-z]+[A-Z][a-zA-Z]*$")
_SNAKE = re.compile(r"^[a-z][a-z0-9_]*$")
_UPPER_SNAKE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_CLASS = re.compile(r"^[A-Z][a-zA-Z0-9]*$")


class ConventionRunner(BaseRunner):
    name = "convention"

    def run(self) -> RunnerResult:
        start = time.monotonic()
        findings: list[Finding] = []
        for py_file in self._collect_python_files():
            tree = self._parse_file(py_file)
            lines = self._read_lines(py_file)
            rel = self._rel_path(py_file)
            if tree is not None:
                findings.extend(self._check_mixed_naming(tree, rel))
                findings.extend(self._check_mixed_quotes(lines, rel))
                findings.extend(self._check_mixed_indentation(lines, rel))
                findings.extend(self._check_mixed_imports(tree, rel))
                findings.extend(self._check_missing_all(tree, rel))
        return RunnerResult(
            runner=self.name, status=RunnerStatus.SUCCESS,
            findings=findings, duration_seconds=time.monotonic() - start,
        )

    def _check_mixed_naming(self, tree: ast.Module, file: str) -> list[Finding]:
        findings: list[Finding] = []
        snake: list[tuple[str, int]] = []
        camel: list[tuple[str, int]] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name.lstrip("_")
                if not name:
                    continue
                if _CAMEL.match(name):
                    camel.append((node.name, node.lineno))
                elif _SNAKE.match(name):
                    snake.append((node.name, node.lineno))
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if not isinstance(t, ast.Name):
                        continue
                    name = t.id.lstrip("_")
                    if not name or _UPPER_SNAKE.match(name) or _CLASS.match(name):
                        continue
                    if _CAMEL.match(name):
                        camel.append((t.id, node.lineno))
                    elif _SNAKE.match(name):
                        snake.append((t.id, node.lineno))

        if snake and camel:
            minority = camel if len(camel) <= len(snake) else snake
            conv = "camelCase" if minority is camel else "snake_case"
            dom = "snake_case" if conv == "camelCase" else "camelCase"
            for name, line in minority[:5]:
                findings.append(self._finding(
                    Severity.LOW, _CAT, file, "mixed-naming", "Mixed naming convention",
                    f"'{name}' uses {conv} in a file that mostly uses {dom}",
                    line=line, fix_hint=f"Rename to match {dom}",
                ))
        return findings

    def _check_mixed_quotes(self, lines: list[str], file: str) -> list[Finding]:
        single, double = 0, 0
        for line in lines:
            s = line.strip()
            if not s or s.startswith("#") or '"""' in s or "'''" in s:
                continue
            in_str = False
            for i, ch in enumerate(s):
                if ch == "#" and not in_str:
                    break
                if ch in ("'", '"') and (i == 0 or s[i - 1] != "\\"):
                    if not in_str:
                        if ch == "'":
                            single += 1
                        else:
                            double += 1
                    in_str = not in_str
        total = single + double
        if total < 4:
            return []
        ratio = min(single, double) / total
        if 0.2 < ratio < 0.5:
            dom = "double" if double >= single else "single"
            return [self._finding(
                Severity.LOW, _CAT, file, "mixed-quotes", "Inconsistent string quotes",
                f"Mixed: {single} single, {double} double (dominant: {dom})",
                line=1, fix_hint=f"Standardise on {dom} quotes",
            )]
        return []

    def _check_mixed_indentation(self, lines: list[str], file: str) -> list[Finding]:
        tabs: list[int] = []
        spaces: list[int] = []
        for i, line in enumerate(lines):
            if not line or line.isspace():
                continue
            if line[0] == "\t":
                tabs.append(i + 1)
            elif line[0] == " " and not line.lstrip().startswith("#"):
                spaces.append(i + 1)
        if tabs and spaces:
            minority = tabs if len(tabs) <= len(spaces) else spaces
            kind = "tabs" if minority is tabs else "spaces"
            dom = "spaces" if kind == "tabs" else "tabs"
            return [self._finding(
                Severity.MEDIUM, _CAT, file, "mixed-indentation", "Mixed indentation",
                f"Mixes {kind} ({len(minority)} lines) with {dom}",
                line=minority[0], fix_hint=f"Convert all indentation to {dom}",
            )]
        return []

    def _check_mixed_imports(self, tree: ast.Module, file: str) -> list[Finding]:
        rel_lines: list[int] = []
        abs_lines: list[int] = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:
                    rel_lines.append(node.lineno)
                else:
                    abs_lines.append(node.lineno)
        if rel_lines and abs_lines:
            minority = rel_lines if len(rel_lines) <= len(abs_lines) else abs_lines
            style = "relative" if minority is rel_lines else "absolute"
            dom = "absolute" if style == "relative" else "relative"
            return [self._finding(
                Severity.LOW, _CAT, file, "mixed-imports", "Inconsistent import style",
                f"Mixes {style} ({len(minority)}) with {dom} imports",
                line=minority[0], fix_hint=f"Use {dom} imports consistently",
            )]
        return []

    def _check_missing_all(self, tree: ast.Module, file: str) -> list[Finding]:
        has_all = False
        public: list[str] = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "__all__":
                        has_all = True
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if not node.name.startswith("_"):
                    public.append(node.name)
        if not has_all and len(public) >= 3:
            return [self._finding(
                Severity.LOW, _CAT, file, "missing-all", "Missing __all__",
                f"{len(public)} public names but no __all__",
                line=1, fix_hint=f"Add __all__ = {public[:5]}",
            )]
        return []
