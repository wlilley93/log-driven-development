"""Duplication runner -- copy-paste and repeated code detection."""

from __future__ import annotations

import ast
import time
from collections import defaultdict
from pathlib import Path

from vibeclean.models import Category, Finding, RunnerResult, RunnerStatus, Severity
from vibeclean.runners.base import BaseRunner

_CAT = Category.DUPLICATION


def _ast_sig(node: ast.AST) -> str:
    """Structural signature: node types at each depth."""
    parts: list[str] = []
    def walk(n: ast.AST, d: int = 0) -> None:
        if d > 10:
            return
        parts.append(f"{d}:{type(n).__name__}")
        for c in ast.iter_child_nodes(n):
            walk(c, d + 1)
    walk(node)
    return "|".join(parts)


class DuplicationRunner(BaseRunner):
    name = "duplication"

    def run(self) -> RunnerResult:
        start = time.monotonic()
        findings: list[Finding] = []
        py_files = self._collect_python_files()
        rc = self.runner_config
        min_lines = rc.get("min_duplicate_lines", 5)
        min_occ = rc.get("min_occurrences", 3)

        findings.extend(self._check_duplicate_functions(py_files))
        findings.extend(self._check_repeated_blocks(py_files, min_lines, min_occ))
        findings.extend(self._check_identical_except_blocks(py_files))
        return RunnerResult(
            runner=self.name, status=RunnerStatus.SUCCESS,
            findings=findings, duration_seconds=time.monotonic() - start,
        )

    def _check_duplicate_functions(self, py_files: list[Path]) -> list[Finding]:
        findings: list[Finding] = []
        sigs: dict[str, list[tuple[str, str, int]]] = defaultdict(list)

        for pf in py_files:
            tree = self._parse_file(pf)
            if tree is None:
                continue
            rel = self._rel_path(pf)
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                real = [s for s in node.body if not (isinstance(s, ast.Expr)
                        and isinstance(getattr(s, "value", None), ast.Constant))]
                if len(real) < 3:
                    continue
                sigs[_ast_sig(node)].append((rel, node.name, node.lineno))

        for locs in sigs.values():
            if len(locs) < 2:
                continue
            ff, fn, fl = locs[0]
            for df, dn, dl in locs[1:]:
                findings.append(self._finding(
                    Severity.MEDIUM, _CAT, df, "duplicate-function",
                    "Duplicate function body",
                    f"'{dn}' has same structure as '{fn}' in {ff}:{fl}",
                    line=dl, fix_hint="Extract shared logic into a common function",
                ))
        return findings

    def _check_repeated_blocks(self, py_files: list[Path],
                                min_lines: int, min_occ: int) -> list[Finding]:
        findings: list[Finding] = []
        blocks: dict[str, list[tuple[str, int]]] = defaultdict(list)

        for pf in py_files:
            lines = self._read_lines(pf)
            rel = self._rel_path(pf)
            norm = []
            for line in lines:
                s = line.strip()
                norm.append("" if (not s or s.startswith("#")) else s)
            for i in range(len(norm) - min_lines + 1):
                block = norm[i:i + min_lines]
                if all(block):
                    blocks["\n".join(block)].append((rel, i + 1))

        for key, locs in blocks.items():
            if len(locs) < min_occ:
                continue
            seen: set[tuple[str, int]] = set()
            unique: list[tuple[str, int]] = []
            for f, l in locs:
                if not any(uf == f and abs(ul - l) < min_lines for uf, ul in seen):
                    seen.add((f, l))
                    unique.append((f, l))
            if len(unique) < min_occ:
                continue
            loc_strs = [f"{f}:{l}" for f, l in unique[:5]]
            findings.append(self._finding(
                Severity.MEDIUM, _CAT, unique[0][0], "repeated-block",
                "Repeated code block",
                f"{min_lines}+ line block repeated {len(unique)} times: {', '.join(loc_strs)}",
                line=unique[0][1],
                fix_hint="Extract the repeated block into a shared function",
            ))
        return findings

    def _check_identical_except_blocks(self, py_files: list[Path]) -> list[Finding]:
        findings: list[Finding] = []
        sigs: dict[str, list[tuple[str, int]]] = defaultdict(list)

        for pf in py_files:
            tree = self._parse_file(pf)
            if tree is None:
                continue
            rel = self._rel_path(pf)
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler) and len(node.body) >= 2:
                    sigs[_ast_sig(node)].append((rel, node.lineno))

        for locs in sigs.values():
            if len(locs) < 2:
                continue
            loc_strs = [f"{f}:{l}" for f, l in locs[:5]]
            findings.append(self._finding(
                Severity.LOW, _CAT, locs[0][0], "identical-except",
                "Identical except blocks",
                f"Same handler appears {len(locs)} times: {', '.join(loc_strs)}",
                line=locs[0][1],
                fix_hint="Extract common error handling into a shared function",
            ))
        return findings
