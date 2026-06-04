"""Slop detector runner -- finds AI-generated code smell patterns."""

from __future__ import annotations

import ast
import re
import time

from vibeclean.models import Category, Finding, RunnerResult, RunnerStatus, Severity
from vibeclean.runners.base import BaseRunner

_CAT = Category.SLOP
_STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "if", "else", "then", "and", "or", "not", "no", "it", "its", "this",
    "that", "we", "i", "he", "she", "they", "them", "their", "our", "my",
})
_TODO_RE = re.compile(r"#\s*(TODO|FIXME|HACK|XXX|TEMP)\b", re.IGNORECASE)
_DEBUG_RE = re.compile(r"^\s*print\s*\(\s*['\"]?(debug|DEBUG|>>>|---|\*\*\*|!!|test|TRACE)")


class SlopDetectorRunner(BaseRunner):
    name = "slop_detector"

    def run(self) -> RunnerResult:
        start = time.monotonic()
        findings: list[Finding] = []
        for py_file in self._collect_python_files():
            tree = self._parse_file(py_file)
            lines = self._read_lines(py_file)
            rel = self._rel_path(py_file)
            if tree is not None:
                findings.extend(self._check_redundant_comments(lines, rel))
                findings.extend(self._check_obvious_docstrings(tree, rel))
                findings.extend(self._check_useless_try_except(tree, rel))
                findings.extend(self._check_todo_comments(lines, rel))
                findings.extend(self._check_debug_prints(lines, rel))
                findings.extend(self._check_useless_annotations(tree, rel))
        return RunnerResult(
            runner=self.name, status=RunnerStatus.SUCCESS,
            findings=findings, duration_seconds=time.monotonic() - start,
        )

    def _words(self, text: str) -> set[str]:
        """Extract meaningful words, lowercased, stop words removed."""
        return {w for w in re.findall(r"[a-zA-Z_]\w*", text.lower())
                if w not in _STOP_WORDS and len(w) > 1}

    def _check_redundant_comments(self, lines: list[str], file: str) -> list[Finding]:
        findings: list[Finding] = []
        for i, line in enumerate(lines):
            s = line.strip()
            if "#" in s and not s.startswith("#"):
                code, _, comment = s.partition("#")
                cw, cmw = self._words(code), self._words(comment)
                if cw and cmw and len(cw & cmw) / len(cmw) >= 0.6:
                    findings.append(self._finding(
                        Severity.LOW, _CAT, file, "redundant-comment", "Redundant comment",
                        f"Comment restates the code ({len(cw & cmw) / len(cmw):.0%} overlap)",
                        line=i + 1, fix_hint="Remove the comment or add meaningful context",
                    ))
                continue
            if s.startswith("#") and i + 1 < len(lines):
                nxt = lines[i + 1].strip()
                if nxt and not nxt.startswith("#"):
                    cmw, cw = self._words(s.lstrip("#")), self._words(nxt)
                    if cmw and cw and len(cmw & cw) / len(cmw) >= 0.6:
                        findings.append(self._finding(
                            Severity.LOW, _CAT, file, "redundant-comment", "Redundant comment",
                            f"Comment restates the next line ({len(cmw & cw) / len(cmw):.0%} overlap)",
                            line=i + 1, fix_hint="Remove the comment or explain why, not what",
                        ))
        return findings

    def _check_obvious_docstrings(self, tree: ast.Module, file: str) -> list[Finding]:
        findings: list[Finding] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if len(node.body) != 2:
                continue
            first = node.body[0]
            if not (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                continue
            doc = first.value.value.strip()
            if len(doc.split()) <= 6:
                fw = set(node.name.lower().replace("_", " ").split())
                dw = self._words(doc)
                if fw and dw and len(fw & dw) / max(len(dw), 1) >= 0.5:
                    findings.append(self._finding(
                        Severity.LOW, _CAT, file, "obvious-docstring", "Obvious docstring",
                        f"Docstring on '{node.name}' restates the function name",
                        line=first.lineno, fix_hint="Remove or add meaningful detail",
                    ))
        return findings

    def _check_useless_try_except(self, tree: ast.Module, file: str) -> list[Finding]:
        findings: list[Finding] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            for h in node.handlers:
                if (len(h.body) == 1 and isinstance(h.body[0], ast.Raise)
                        and h.body[0].exc is None):
                    findings.append(self._finding(
                        Severity.MEDIUM, _CAT, file, "useless-try-except",
                        "Useless try/except",
                        "try/except that just re-raises adds no value",
                        line=h.lineno, fix_hint="Remove the try/except or add handling",
                    ))
        return findings

    def _check_todo_comments(self, lines: list[str], file: str) -> list[Finding]:
        findings: list[Finding] = []
        for i, line in enumerate(lines):
            m = _TODO_RE.search(line)
            if m:
                findings.append(self._finding(
                    Severity.MEDIUM, _CAT, file, "todo-comment", "TODO/FIXME comment",
                    f"{m.group(1).upper()} comment: {line.strip()[:80]}",
                    line=i + 1, fix_hint="Resolve or move to issue tracker",
                ))
        return findings

    def _check_debug_prints(self, lines: list[str], file: str) -> list[Finding]:
        findings: list[Finding] = []
        for i, line in enumerate(lines):
            if _DEBUG_RE.match(line):
                findings.append(self._finding(
                    Severity.LOW, _CAT, file, "debug-print", "Debug print statement",
                    f"Looks like debug output: {line.strip()[:60]}",
                    line=i + 1, fix_hint="Remove or use proper logging",
                ))
        return findings

    def _check_useless_annotations(self, tree: ast.Module, file: str) -> list[Finding]:
        findings: list[Finding] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.returns and self._is_useless(node.returns):
                    findings.append(self._finding(
                        Severity.LOW, _CAT, file, "useless-type-annotation",
                        "Useless type annotation",
                        f"Return type 'Any'/'object' on '{node.name}' adds no value",
                        line=node.lineno, fix_hint="Use a specific type or remove",
                    ))
                for arg in node.args.args + node.args.kwonlyargs:
                    if arg.annotation and self._is_useless(arg.annotation):
                        findings.append(self._finding(
                            Severity.LOW, _CAT, file, "useless-type-annotation",
                            "Useless type annotation",
                            f"Parameter '{arg.arg}: Any/object' adds no value",
                            line=arg.lineno, fix_hint="Use a specific type or remove",
                        ))
            elif isinstance(node, ast.AnnAssign):
                if node.annotation and self._is_useless(node.annotation):
                    name = node.target.id if isinstance(node.target, ast.Name) else ""
                    findings.append(self._finding(
                        Severity.LOW, _CAT, file, "useless-type-annotation",
                        "Useless type annotation",
                        f"Annotation '{name}: Any/object' adds no value",
                        line=node.lineno, fix_hint="Use a specific type or remove",
                    ))
        return findings

    def _is_useless(self, node: ast.expr) -> bool:
        if isinstance(node, ast.Name) and node.id in ("Any", "object"):
            return True
        if isinstance(node, ast.Constant) and node.value in ("Any", "object"):
            return True
        return False
