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
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import gather_files, is_significant, read_config_section, read_exclude_globs

DEFAULT_INCLUDE_SUFFIXES = (
    ".py", ".js", ".jsx", ".ts", ".tsx", ".rs", ".go", ".java", ".kt", ".rb",
    ".php", ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".swift", ".scala", ".sql",
)


def normalise(line: str) -> str:
    # Collapse internal whitespace so indentation/formatting differences do not hide a clone.
    return re.sub(r"\s+", " ", line.strip())


def _read_significant(files):
    """Return (per_file_sig, total_significant). per_file_sig maps file -> [(lineno, normalised)]."""
    per_file_sig = {}
    total_sig = 0
    for f in files:
        try:
            raw = f.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        sig = [(idx, normalise(line)) for idx, line in enumerate(raw, start=1) if is_significant(line)]
        per_file_sig[f] = sig
        total_sig += len(sig)
    return per_file_sig, total_sig


def _index_windows(per_file_sig, min_lines):
    """Hash every window of `min_lines` significant lines: window_hash -> [(file, start_index)]."""
    window_locations = defaultdict(list)
    for f, sig in per_file_sig.items():
        texts = [t for (_, t) in sig]
        for start in range(0, len(texts) - min_lines + 1):
            window = "\n".join(texts[start:start + min_lines])
            h = hashlib.sha1(window.encode("utf-8")).hexdigest()
            window_locations[h].append((f, start))
    return window_locations


def _collect_duplicates(window_locations, per_file_sig, min_lines):
    """Return (duplicated_line_keys, examples) for windows occurring at >= 2 distinct locations."""
    duplicated_line_keys = set()  # (file, significant_index)
    examples = []
    for locs in window_locations.values():
        # Require the window at two different (file, start) pairs to count as a clone.
        if len({(f, s) for (f, s) in locs}) < 2:
            continue
        for (f, start) in locs:
            for offset in range(min_lines):
                duplicated_line_keys.add((f, start + offset))
        if len(examples) < 10:
            (fa, sa), (fb, sb) = locs[0], locs[1]
            examples.append((str(fa), per_file_sig[fa][sa][0], str(fb), per_file_sig[fb][sb][0], min_lines))
    return duplicated_line_keys, examples


def measure(files, min_lines):
    """
    Return (total_significant_lines, duplicated_significant_lines, examples).

    A line is "duplicated" if it participates in at least one window of `min_lines`
    consecutive significant lines whose normalised text appears at >= 2 distinct
    locations across the scanned set.
    """
    per_file_sig, total_sig = _read_significant(files)
    window_locations = _index_windows(per_file_sig, min_lines)
    duplicated_line_keys, examples = _collect_duplicates(window_locations, per_file_sig, min_lines)
    duplicated = len(duplicated_line_keys)
    return total_sig, duplicated, examples


def read_budget(config_path):
    """Read [duplication] budget_percent and min_lines. Returns (budget: float|None, min_lines: int|None)."""
    dup = read_config_section(config_path, "duplication")
    budget = None
    min_lines = None
    if "budget_percent" in dup:
        try:
            budget = float(dup["budget_percent"])
        except ValueError:
            pass
    if "min_lines" in dup:
        try:
            min_lines = int(dup["min_lines"])
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


def _build_parser():
    ap = argparse.ArgumentParser(description="LDD duplication ratchet (hold or lower, never raise).")
    ap.add_argument("paths", nargs="*", default=["."], help="Source roots to scan (default: .).")
    ap.add_argument("--config", default="closure-gate.toml", help="Config file with [duplication] budget_percent.")
    ap.add_argument("--min-lines", type=int, default=None, help="Min consecutive significant lines for a clone (default: config or 5).")
    ap.add_argument("--budget", type=float, default=None, help="Override the budget percent (else read from config).")
    ap.add_argument("--measured", type=float, default=None, help="Use this externally-measured percent (e.g. from a real clone detector) instead of scanning.")
    ap.add_argument("--include", default=None, help="Comma-separated file suffixes to include (overrides default set).")
    ap.add_argument("--update-budget", action="store_true", help="Lower the stored budget to the current measured value (never raises).")
    ap.add_argument("--check", action="store_true", help="Check measured against budget and exit non-zero if over (the default action).")
    return ap


def _apply_update_budget(config_path, budget, pct):
    """The --update-budget action: lower the stored budget, or refuse to raise it. Returns exit code."""
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


def _apply_check(config_path, budget, pct, examples):
    """The default --check action: deny if measured exceeds budget. Returns exit code."""
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


def main(argv=None):
    args = _build_parser().parse_args(argv)
    config_path = Path(args.config)
    cfg_budget, cfg_min_lines = read_budget(config_path)
    min_lines = args.min_lines or cfg_min_lines or 5
    budget = args.budget if args.budget is not None else cfg_budget
    include = tuple(args.include.split(",")) if args.include else DEFAULT_INCLUDE_SUFFIXES

    if args.measured is not None:
        total_sig, duplicated, examples, pct = 0, 0, [], args.measured
    else:
        files = gather_files(args.paths, include, exclude_globs=read_exclude_globs(config_path))
        if not files:
            print("duplication-ratchet: no source files found under", args.paths, file=sys.stderr)
            return 2
        total_sig, duplicated, examples = measure(files, min_lines)
        pct = (100.0 * duplicated / total_sig) if total_sig else 0.0

    print(f"duplication-ratchet: {pct:.4f}% duplicated "
          f"({duplicated}/{total_sig} significant lines, min_lines={min_lines})")

    if args.update_budget:
        return _apply_update_budget(config_path, budget, pct)
    return _apply_check(config_path, budget, pct, examples)


if __name__ == "__main__":
    sys.exit(main())
