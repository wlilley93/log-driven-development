#!/usr/bin/env python3
"""
closure_gate.py - run the whole LDD closure-gate in one shot.

The closure-gate is LDD's continuous structural enforcement: it runs on every commit and
decides, mechanically, whether the tree is clean. This orchestrator runs every gate in
order and denies (exit 1) if any fails. Stand it up BEFORE the walking skeleton, so
"clean" is checkable from the first line of the rebuild.

The gates, in order (each is skipped only if its command is left blank in the config):
  1. formatter        - your formatter in --check mode (deny on fail)
  2. linter           - your linter, warnings-as-errors (deny on fail)
  3. type-check       - your type-checker, if the language has one (deny on fail)
  4. max-function-len - the portable deny gate in this directory (deny on fail)
  5. duplication      - the ratchet in this directory: hold-or-lower, never raise (deny on fail)
  6. tests            - your full suite, run from a clean state (deny on fail)
  7. security-scan    - the ONE continuous security owner (vibescan --fast: secrets + dep-CVE +
                        fast SAST; subsumes the old supply-chain gate). Deny on a new finding.
  8. structure-scan   - the continuous structural slop scan (vibeclean: AI-slop, god-files,
                        duplication the richer scanner catches). Deny on a regression.

Gates 7 and 8 are the continuous edge of the security and refactoring suites (the LDD process
council's two-tier(+) model: cheap per-commit gates here, heavy passes at milestone-close). They
default to the vibe* tools vendored under ../vibe. If a tool is not installed, the gate is a LOUD
skip with an install hint (exit 127), never a silent absence and never a hard block on a missing
tool. The heavy passes (vibeaudit deep, the security suite, a full refactor round) are NOT here:
they fire at milestone-close on a risk trigger. See ../../docs/systems.md for the ownership matrix.

The project-specific commands live in closure-gate.toml under [commands]; the two
portable checks (4, 5) are these scripts. Anything you leave blank is skipped (and
reported as skipped, never silently absent). "Done" means this sweep is clean: never
"the tests pass" alone.

Exit codes: 0 = all gates passed, 1 = at least one gate denied, 2 = usage/config error.

No third-party dependencies. Python 3.8+.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _common import read_config_section


def read_commands(config_path):
    """Read the [commands] table from the config (no third-party deps). Returns dict."""
    return read_config_section(config_path, "commands")


def run_step(name, command, cwd, tolerate_missing=False):
    """Run a shell command. Returns (ok, skipped).

    tolerate_missing: if True, a 'command not found' (exit 127) is reported as a LOUD skip with
    an install hint rather than a deny. Used for the suite gates (security/structure scan) whose
    tool may not be installed yet: a missing tool must never silently disable security, but it
    also must not hard-block a commit (LDD-INV-1, never silently absent; not hostile when absent).
    """
    if not command:
        print(f"[skip] {name}: no command configured (skipped, not silently absent).")
        return True, True
    print(f"[run ] {name}: {command}")
    try:
        proc = subprocess.run(command, shell=True, cwd=cwd)
    except OSError as e:
        print(f"[FAIL] {name}: could not run ({e})", file=sys.stderr)
        return False, False
    if tolerate_missing and proc.returncode == 127:
        print(f"[warn] {name}: tool not installed (exit 127). This gate is OFF until you install "
              f"it (e.g. pip install vibescan vibeclean, or run from ../vibe). Reported, not silent.")
        return True, True
    ok = proc.returncode == 0
    print(f"[{'pass' if ok else 'FAIL'}] {name}: exit {proc.returncode}")
    return ok, False


def run_python_check(name, script, extra_args, config_path, cwd):
    cmd = [sys.executable, str(HERE / script), "--config", str(config_path)] + extra_args
    print(f"[run ] {name}: {' '.join(shlex.quote(c) for c in cmd)}")
    try:
        proc = subprocess.run(cmd, cwd=cwd)
    except OSError as e:
        print(f"[FAIL] {name}: could not run ({e})", file=sys.stderr)
        return False
    ok = proc.returncode == 0
    print(f"[{'pass' if ok else 'FAIL'}] {name}: exit {proc.returncode}")
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run the full LDD closure-gate.")
    ap.add_argument("--config", default="closure-gate.toml", help="Path to closure-gate.toml.")
    ap.add_argument("--paths", default=".", help="Comma-separated source roots for the portable checks.")
    ap.add_argument("--cwd", default=".", help="Working directory to run project commands in.")
    ap.add_argument("--skip", default="", help="Comma-separated gate names to skip (e.g. tests for a fast pre-commit).")
    args = ap.parse_args(argv)

    config_path = Path(args.config).resolve()
    cwd = Path(args.cwd).resolve()
    paths = args.paths.split(",")
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    cmds = read_commands(config_path)

    results = []  # (name, ok, skipped)

    # 1-3: project-supplied commands.
    for name, key in (("formatter", "format_check"), ("linter", "lint"), ("type-check", "typecheck")):
        if name in skip:
            results.append((name, True, True))
            continue
        ok, skipped = run_step(name, cmds.get(key, ""), cwd)
        results.append((name, ok, skipped))

    # 4: portable max-function-length.
    if "max-function-length" in skip:
        results.append(("max-function-length", True, True))
    else:
        ok = run_python_check("max-function-length", "max_function_length.py", paths, config_path, cwd)
        results.append(("max-function-length", ok, False))

    # 5: portable duplication ratchet (check mode: hold-or-lower, deny if over).
    if "duplication" in skip:
        results.append(("duplication-ratchet", True, True))
    else:
        ok = run_python_check("duplication-ratchet", "duplication_ratchet.py", ["--check"] + paths, config_path, cwd)
        results.append(("duplication-ratchet", ok, False))

    # 6: tests (project-supplied).
    if "tests" in skip:
        results.append(("tests", True, True))
    else:
        ok, skipped = run_step("tests", cmds.get("test", ""), cwd)
        results.append(("tests", ok, skipped))

    # 7-8: the continuous edge of the security + refactoring suites (the two-tier(+) model). These
    # default to the vendored vibe* tools; a missing tool is a LOUD skip (exit 127), never silent,
    # never a hard block. security-scan is the ONE security owner here (subsumes supply-chain).
    for name, key in (("security-scan", "security_scan"), ("structure-scan", "structure_scan")):
        if name in skip:
            results.append((name, True, True))
            continue
        ok, skipped = run_step(name, cmds.get(key, ""), cwd, tolerate_missing=True)
        results.append((name, ok, skipped))

    return _report(results)


def _report(results):
    """Print the gate summary and return the process exit code (1 if any gate denied)."""
    print("\n=== closure-gate summary ===")
    denied = []
    for (name, ok, skipped) in results:
        status = "skip" if skipped else ("pass" if ok else "DENY")
        print(f"  {status:>4}  {name}")
        if not ok and not skipped:
            denied.append(name)

    if denied:
        print(f"\nclosure-gate: DENY. Failing gates: {', '.join(denied)}.")
        print("The commit is refused until the tree is clean. 'Done' means this sweep is clean, "
              "never 'the tests pass' alone.")
        return 1

    print("\nclosure-gate: clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
