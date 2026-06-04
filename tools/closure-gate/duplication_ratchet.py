#!/usr/bin/env python3
"""
duplication_ratchet.py - the load-bearing gate of the LDD closure-gate.

A cross-module duplication budget you may only ever HOLD or LOWER (by folding the
duplication into one shared function). You NEVER raise the number to make a commit
pass: raising it concedes the sprawl the gate exists to delete.

What it measures
----------------
It scans your source files for blocks of duplicated code (the same run of >= MIN_LINES
significant lines appearing in two or more places), and reports the fraction of scanned
significant lines that participate in a duplicate block. That fraction is the
"duplication percentage". The gate fails if it exceeds the budget recorded in the
config file.

This is a language-agnostic, dependency-free approximation of a clone detector (it is to
jscpd/PMD-CPD what a smoke test is to a full suite). It normalises whitespace, ignores
blank lines and comment-only lines for the common comment markers, then hashes every
window of MIN_LINES consecutive significant lines and counts windows whose normalised
content appears in more than one place. For a heavier, AST-aware clone scan, point the
config at a real clone detector and feed its percentage in via --measured (see README).

The ratchet, not the absolute number, is the discipline
-------------------------------------------------------
- The budget lives in the config file (default: closure-gate.toml, key
  [duplication] budget_percent). It is the number you last CLOSED at.
- `--check` (default) fails if measured > budget. It does not touch the config.
- `--update-budget` LOWERS the stored budget to the current measured value, but REFUSES
  to raise it. Lowering is how you ratchet down after folding duplication. Raising is
  refused on purpose; if you genuinely must (e.g. a large vendored import you accept),
  edit the config by hand and journal the reason, so the concession is on the record.

Exit codes: 0 = within budget, 1 = over budget (deny), 2 = usage/config error.

No third-party dependencies. Python 3.8+.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

# Whole-line comment markers we treat as "not significant" when set for a file's suffix.
# Genericise/extend for your stack; this is a pragmatic default, not an exhaustive parser.
LINE_COMMENT_PREFIXES = ("//", "#", "--", ";", "*", "/*", "*/")

DEFAULT_INCLUDE_SUFFIXES = (
    ".py", ".js", ".jsx", ".ts", ".tsx", ".rs", ".go", ".java", ".kt", ".rb",
    ".php", ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".swift", ".scala", ".sql",
)

DEFAULT_EXCLUDE_DIRS = (
    ".git", "node_modules", "dist", "build", "target", "vendor", "venv", ".venv",
    "__pycache__", ".next", ".cache", "coverage", "out", ".mypy_cache", ".pytest_cache",
)


def is_significant(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    return not s.startswith(LINE_COMMENT_PREFIXES)


def normalise(line: str) -> str:
    # Collapse internal whitespace so indentation/formatting differences do not hide a clone.
    return re.sub(r"\s+", " ", line.strip())


def gather_files(roots, include_suffixes, exclude_dirs):
    files = []
    for root in roots:
        root_path = Path(root)
        if root_path.is_file():
            if root_path.suffix in include_suffixes:
                files.append(root_path)
            continue
        for dirpath, dirnames, filenames in os.walk(root_path):
            dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
            for name in filenames:
                p = Path(dirpath) / name
                if p.suffix in include_suffixes:
                    files.append(p)
    return sorted(set(files))


def measure(files, min_lines):
    """
    Return (total_significant_lines, duplicated_significant_lines, examples).

    A line is "duplicated" if it participates in at least one window of `min_lines`
    consecutive significant lines whose normalised text appears at >= 2 distinct
    locations across the scanned set.
    """
    # window_hash -> list of (file, start_index_into_significant_lines)
    window_locations = defaultdict(list)
    # Per-file list of (original_line_no, normalised_text) for significant lines only.
    per_file_sig = {}

    total_sig = 0
    for f in files:
        try:
            raw = f.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        sig = []
        for idx, line in enumerate(raw, start=1):
            if is_significant(line):
                sig.append((idx, normalise(line)))
        per_file_sig[f] = sig
        total_sig += len(sig)

    # Hash every window of min_lines significant lines.
    for f, sig in per_file_sig.items():
        texts = [t for (_, t) in sig]
        for start in range(0, len(texts) - min_lines + 1):
            window = "\n".join(texts[start:start + min_lines])
            h = hashlib.sha1(window.encode("utf-8")).hexdigest()
            window_locations[h].append((f, start))

    # A window is duplicated if it occurs at >= 2 distinct locations.
    duplicated_line_keys = set()  # (file, significant_index)
    examples = []
    for h, locs in window_locations.items():
        if len(locs) < 2:
            continue
        # Distinct locations only (a window repeating inside one tight loop is still a clone,
        # but require it appear at two different (file,start) pairs to count).
        if len({(f, s) for (f, s) in locs}) < 2:
            continue
        for (f, start) in locs:
            for offset in range(min_lines):
                duplicated_line_keys.add((f, start + offset))
        if len(examples) < 10:
            (fa, sa), (fb, sb) = locs[0], locs[1]
            la = per_file_sig[fa][sa][0]
            lb = per_file_sig[fb][sb][0]
            examples.append((str(fa), la, str(fb), lb, min_lines))

    duplicated = len(duplicated_line_keys)
    return total_sig, duplicated, examples


def read_budget(config_path):
    """
    Minimal TOML-ish reader for [duplication] budget_percent and min_lines, so the tool
    has zero third-party deps. Accepts the same file the other gates read.
    Returns (budget_percent: float, min_lines: int).
    """
    budget = None
    min_lines = None
    in_dup = False
    if not config_path.exists():
        return budget, min_lines
    for line in config_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("#") or not s:
            continue
        if s.startswith("[") and s.endswith("]"):
            in_dup = s == "[duplication]"
            continue
        if not in_dup:
            continue
        if "=" not in s:
            continue
        key, _, val = s.partition("=")
        key = key.strip()
        val = val.split("#", 1)[0].strip().strip('"').strip("'")
        if key == "budget_percent":
            try:
                budget = float(val)
            except ValueError:
                pass
        elif key == "min_lines":
            try:
                min_lines = int(val)
            except ValueError:
                pass
    return budget, min_lines


def write_budget(config_path, new_budget):
    """Rewrite only the budget_percent line under [duplication], preserving the rest."""
    lines = config_path.read_text(encoding="utf-8").splitlines()
    out = []
    in_dup = False
    wrote = False
    for line in lines:
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            in_dup = s == "[duplication]"
        if in_dup and s.startswith("budget_percent"):
            out.append(f"budget_percent = {new_budget:.4f}")
            wrote = True
            continue
        out.append(line)
    if not wrote:
        # Append a [duplication] block if the config did not have one.
        out.append("")
        out.append("[duplication]")
        out.append(f"budget_percent = {new_budget:.4f}")
    config_path.write_text("\n".join(out) + "\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description="LDD duplication ratchet (hold or lower, never raise).")
    ap.add_argument("paths", nargs="*", default=["."], help="Source roots to scan (default: .).")
    ap.add_argument("--config", default="closure-gate.toml", help="Config file with [duplication] budget_percent.")
    ap.add_argument("--min-lines", type=int, default=None, help="Min consecutive significant lines for a clone (default: config or 5).")
    ap.add_argument("--budget", type=float, default=None, help="Override the budget percent (else read from config).")
    ap.add_argument("--measured", type=float, default=None, help="Use this externally-measured percent (e.g. from a real clone detector) instead of scanning.")
    ap.add_argument("--include", default=None, help="Comma-separated file suffixes to include (overrides default set).")
    ap.add_argument("--update-budget", action="store_true", help="Lower the stored budget to the current measured value (never raises).")
    ap.add_argument("--check", action="store_true", help="Check measured against budget and exit non-zero if over (the default action).")
    args = ap.parse_args(argv)

    config_path = Path(args.config)
    cfg_budget, cfg_min_lines = read_budget(config_path)

    min_lines = args.min_lines or cfg_min_lines or 5
    budget = args.budget if args.budget is not None else cfg_budget
    include = tuple(args.include.split(",")) if args.include else DEFAULT_INCLUDE_SUFFIXES

    if args.measured is not None:
        total_sig, duplicated, examples = 0, 0, []
        pct = args.measured
    else:
        files = gather_files(args.paths, include, DEFAULT_EXCLUDE_DIRS)
        if not files:
            print("duplication-ratchet: no source files found under", args.paths, file=sys.stderr)
            return 2
        total_sig, duplicated, examples = measure(files, min_lines)
        pct = (100.0 * duplicated / total_sig) if total_sig else 0.0

    print(f"duplication-ratchet: {pct:.4f}% duplicated "
          f"({duplicated}/{total_sig} significant lines, min_lines={min_lines})")

    if args.update_budget:
        if budget is None:
            write_budget(config_path, pct)
            print(f"duplication-ratchet: set initial budget to {pct:.4f}% in {config_path}")
            return 0
        if pct < budget - 1e-9:
            write_budget(config_path, pct)
            print(f"duplication-ratchet: LOWERED budget {budget:.4f}% -> {pct:.4f}% (ratcheted down by folding)")
            return 0
        if pct <= budget + 1e-9:
            print(f"duplication-ratchet: measured {pct:.4f}% == budget {budget:.4f}%, nothing to lower.")
            return 0
        print(f"duplication-ratchet: REFUSING to raise budget {budget:.4f}% -> {pct:.4f}%. "
              f"Fold the duplication instead of raising the number. "
              f"(If you must accept it, edit {config_path} by hand and journal the reason.)",
              file=sys.stderr)
        return 1

    # Default action: check.
    if budget is None:
        print("duplication-ratchet: no budget set. Run with --update-budget once to record the current value, "
              f"or set [duplication] budget_percent in {config_path}.", file=sys.stderr)
        return 2

    if pct <= budget + 1e-9:
        print(f"duplication-ratchet: OK ({pct:.4f}% <= budget {budget:.4f}%).")
        return 0

    print(f"duplication-ratchet: DENY. {pct:.4f}% > budget {budget:.4f}%. "
          f"Fold the new duplication into one shared function (do NOT raise the budget).", file=sys.stderr)
    if examples:
        print("  sample duplicate blocks:", file=sys.stderr)
        for (fa, la, fb, lb, n) in examples[:5]:
            print(f"    {fa}:{la}  <=>  {fb}:{lb}  ({n}+ lines)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
