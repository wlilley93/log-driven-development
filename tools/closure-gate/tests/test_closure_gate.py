#!/usr/bin/env python3
"""
Tests for the LDD closure-gate portable checks.

The closure-gate enforces "tests pass" on every project it gates; it must itself be
verified, or it is the one untested thing demanding tests of everything else. These cover
the load-bearing behaviour: the shared helpers, the function-length detector, and the
duplication ratchet's hold-or-lower discipline.

Zero third-party dependencies (stdlib unittest, to match the tools). Run with:
    python3 -m unittest discover -s tools/closure-gate/tests
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import _common  # noqa: E402
import duplication_ratchet as ratchet  # noqa: E402
import max_function_length as mfl  # noqa: E402


def _write(d: Path, name: str, text: str) -> Path:
    p = d / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


class TestCommon(unittest.TestCase):
    def test_is_significant(self):
        self.assertTrue(_common.is_significant("    x = 1"))
        self.assertFalse(_common.is_significant("   "))
        self.assertFalse(_common.is_significant("  # a comment"))
        self.assertFalse(_common.is_significant("// js comment"))

    def test_gather_files_excludes_build_dirs(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write(d, "a.py", "x = 1\n")
            _write(d, "node_modules/dep.py", "y = 2\n")
            files = _common.gather_files([d], (".py",))
            names = {f.name for f in files}
            self.assertEqual(names, {"a.py"})

    def test_gather_files_excludes_scope_globs(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write(d, "owned/a.py", "x = 1\n")
            _write(d, "vendor_tree/b.py", "y = 2\n")
            files = _common.gather_files([d], (".py",), exclude_globs=("vendor_tree",))
            names = {f.name for f in files}
            self.assertEqual(names, {"a.py"})

    def test_read_config_section_and_exclude(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _write(Path(td), "closure-gate.toml",
                         "[scope]\nexclude = \"tools/vibe, gen\"\n\n[function]\nmax_lines = 40 # nb\n")
            self.assertEqual(_common.read_config_section(cfg, "function"), {"max_lines": "40"})
            self.assertEqual(_common.read_exclude_globs(cfg), ("tools/vibe", "gen"))
            self.assertEqual(_common.read_config_section(cfg, "absent"), {})


class TestMaxFunctionLength(unittest.TestCase):
    def test_flags_long_python_function(self):
        with tempfile.TemporaryDirectory() as td:
            body = "\n".join(f"    a{i} = {i}" for i in range(50))
            p = _write(Path(td), "big.py", f"def big():\n{body}\n")
            findings = mfl.scan_indent_file(p, limit=40)
            self.assertEqual(len(findings), 1)
            self.assertGreater(findings[0][2], 40)

    def test_passes_short_function(self):
        with tempfile.TemporaryDirectory() as td:
            p = _write(Path(td), "small.py", "def small():\n    return 1\n")
            self.assertEqual(mfl.scan_indent_file(p, limit=40), [])

    def test_flags_long_brace_function(self):
        with tempfile.TemporaryDirectory() as td:
            body = "\n".join(f"  let a{i} = {i};" for i in range(50))
            p = _write(Path(td), "big.ts", f"function big() {{\n{body}\n}}\n")
            findings = mfl.scan_brace_file(p, limit=40)
            self.assertEqual(len(findings), 1)

    def test_read_limit(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _write(Path(td), "c.toml", "[function]\nmax_lines = 25\n")
            self.assertEqual(mfl.read_limit(cfg), 25)


class TestDuplicationRatchet(unittest.TestCase):
    def test_measure_detects_a_clone(self):
        block = "\n".join(f"line_{i} = {i}" for i in range(6))
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write(d, "a.py", block + "\nunique_a = 1\n")
            _write(d, "b.py", block + "\nunique_b = 2\n")
            files = _common.gather_files([d], (".py",))
            total, duplicated, examples = ratchet.measure(files, min_lines=5)
            self.assertGreater(duplicated, 0)
            self.assertTrue(examples)

    def test_measure_no_clone(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write(d, "a.py", "alpha = 1\nbeta = 2\n")
            _write(d, "b.py", "gamma = 3\ndelta = 4\n")
            files = _common.gather_files([d], (".py",))
            _total, duplicated, _examples = ratchet.measure(files, min_lines=5)
            self.assertEqual(duplicated, 0)

    def test_ratchet_refuses_to_raise(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _write(Path(td), "c.toml", "[duplication]\nbudget_percent = 1.0000\nmin_lines = 5\n")
            # measured (5.0) above budget (1.0): update-budget must refuse and keep the file.
            rc = ratchet._apply_update_budget(cfg, budget=1.0, pct=5.0)
            self.assertEqual(rc, 1)
            self.assertIn("budget_percent = 1.0000", cfg.read_text())

    def test_ratchet_lowers(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _write(Path(td), "c.toml", "[duplication]\nbudget_percent = 5.0000\nmin_lines = 5\n")
            rc = ratchet._apply_update_budget(cfg, budget=5.0, pct=2.0)
            self.assertEqual(rc, 0)
            self.assertIn("budget_percent = 2.0000", cfg.read_text())

    def test_check_denies_when_over(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _write(Path(td), "c.toml", "x\n")
            self.assertEqual(ratchet._apply_check(cfg, budget=1.0, pct=2.0, examples=[]), 1)
            self.assertEqual(ratchet._apply_check(cfg, budget=2.0, pct=1.0, examples=[]), 0)

    def test_read_budget(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _write(Path(td), "c.toml", "[duplication]\nbudget_percent = 0.8000\nmin_lines = 5\n")
            budget, min_lines = ratchet.read_budget(cfg)
            self.assertAlmostEqual(budget, 0.8)
            self.assertEqual(min_lines, 5)


if __name__ == "__main__":
    unittest.main()
