#!/usr/bin/env python3
"""
_common.py - shared helpers for the LDD closure-gate portable checks.

The two portable scanners (max_function_length.py, duplication_ratchet.py) and the
orchestrator (closure_gate.py) all need the same three things: a list of source files to
scan, a notion of which lines are "significant", and a zero-dependency reader for the
closure-gate.toml config. Before this module those three pieces were copied into each
script (the exact cross-module duplication the ratchet exists to delete). They live here
once, with a single owner (LDD-INV-9).

It also adds the consume-vs-own boundary the gate was missing: `[scope] exclude` in the
config lists trees that are CONSUMED COMMODITIES (vendored deps, generated code) which the
gate must NOT police. You own and gate your differentiating code; you do not gate code you
merely vendored. See docs/invariants.md (the consume-the-commodity principle) and the
closure-gate README.

No third-party dependencies. Python 3.8+.
"""

from __future__ import annotations

import os
from fnmatch import fnmatch
from pathlib import Path

# Build-output / dependency / cache trees that are never first-party source. Excluded by
# default in every scan; the single home for this list (was copied into both scanners).
DEFAULT_EXCLUDE_DIRS = (
    ".git", "node_modules", "dist", "build", "target", "vendor", "venv", ".venv",
    "__pycache__", ".next", ".cache", "coverage", "out", ".mypy_cache", ".pytest_cache",
)

# Whole-line comment markers treated as "not significant" (a pragmatic default across the
# common stacks, not an exhaustive parser).
LINE_COMMENT_PREFIXES = ("//", "#", "--", ";", "*", "/*", "*/")


def is_significant(line: str, comment_prefixes=LINE_COMMENT_PREFIXES) -> bool:
    """A line is significant if it is non-blank and not a whole-line comment."""
    s = line.strip()
    if not s:
        return False
    return not s.startswith(comment_prefixes)


def _is_excluded(path: Path, exclude_globs) -> bool:
    """True if `path` falls under any consumed-commodity exclude entry.

    An entry matches if it equals a path segment run at the tail of the path (so a bare
    "tools/vibe" prunes that whole subtree) or matches the full posix path as a glob (so
    "*/generated/*" works too).
    """
    if not exclude_globs:
        return False
    posix = path.as_posix()
    for pat in exclude_globs:
        p = pat.strip("/")
        if not p:
            continue
        if posix == p or posix.endswith("/" + p) or ("/" + p + "/") in (posix + "/"):
            return True
        if fnmatch(posix, pat):
            return True
    return False


def gather_files(roots, suffixes, exclude_dirs=DEFAULT_EXCLUDE_DIRS, exclude_globs=()):
    """Collect source files under `roots` with a matching suffix.

    Prunes `exclude_dirs` by name (build/cache trees) and `exclude_globs` by path
    (consumed-commodity trees declared in [scope] exclude). Returns a sorted, de-duped list.
    """
    files = []
    for root in roots:
        root_path = Path(root)
        if root_path.is_file():
            if root_path.suffix in suffixes and not _is_excluded(root_path, exclude_globs):
                files.append(root_path)
            continue
        for dirpath, dirnames, filenames in os.walk(root_path):
            dirnames[:] = [
                d for d in dirnames
                if d not in exclude_dirs and not _is_excluded(Path(dirpath) / d, exclude_globs)
            ]
            for name in filenames:
                p = Path(dirpath) / name
                if p.suffix in suffixes and not _is_excluded(p, exclude_globs):
                    files.append(p)
    return sorted(set(files))


def read_config_section(config_path, section: str) -> dict:
    """Read one [section] of the closure-gate.toml as a dict of raw string values.

    A single zero-dependency reader replacing the three bespoke per-section parsers that
    used to live in the scanners and the orchestrator. Callers coerce their own types
    (int/float). Inline `# comments`, surrounding quotes, and blank lines are stripped.
    Returns {} if the file or section is absent.
    """
    out = {}
    path = Path(config_path)
    if not path.exists():
        return out
    in_section = False
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("#") or not s:
            continue
        if s.startswith("[") and s.endswith("]"):
            in_section = s == f"[{section}]"
            continue
        if in_section and "=" in s:
            key, _, val = s.partition("=")
            out[key.strip()] = val.split("#", 1)[0].strip().strip('"').strip("'")
    return out


def read_exclude_globs(config_path) -> tuple:
    """Read [scope] exclude (a comma-separated list of consumed-commodity path globs)."""
    scope = read_config_section(config_path, "scope")
    raw = scope.get("exclude", "")
    return tuple(g.strip() for g in raw.split(",") if g.strip())
