#!/usr/bin/env python3
"""
max_function_length.py - the max-function-length deny gate of the LDD closure-gate.

A long function is where a God-object and hidden duplication grow. This gate denies a
commit when any function body exceeds the configured line limit, so functions stay small
enough that duplication and tangled responsibility are visible (and so the duplication
ratchet can actually catch the second copy).

What it does
------------
Finds function/method definitions across common languages and measures the body length
(significant lines: blank lines and whole-line comments do not count). It reports every
function over the limit with its file:line and length, and exits non-zero if any are
found.

This is a language-agnostic, dependency-free heuristic, not a full parser. It handles two
families:
  - Brace languages (JS/TS, Rust, Go, Java, C/C++, C#, Kotlin, Swift, PHP): it finds a
    definition keyword/pattern, then counts from the opening `{` to its matching `}`.
  - Indent languages (Python, Ruby-ish): it finds `def`/`function` and counts the
    indented (or `def..end`) block.
For a stricter, parser-grade limit, wire your linter's own max-function rule (ESLint
`max-lines-per-function`, Rust `clippy::too_many_lines`, etc.); this tool is the portable
floor that runs even where none is configured. See README.

Exit codes: 0 = all within limit, 1 = at least one over (deny), 2 = usage/config error.

No third-party dependencies. Python 3.8+.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import gather_files, is_significant, read_config_section, read_exclude_globs

BRACE_SUFFIXES = (
    ".js", ".jsx", ".ts", ".tsx", ".rs", ".go", ".java", ".kt", ".c", ".h", ".cc",
    ".cpp", ".hpp", ".cs", ".swift", ".scala", ".php",
)
INDENT_SUFFIXES = (".py",)

# Heuristic definition patterns. Deliberately broad; over-detection only adds candidates,
# and the body-length measurement is what matters.
BRACE_DEF_PATTERNS = [
    re.compile(r"\bfunction\b"),                       # JS function
    re.compile(r"\bfn\s+\w+"),                         # Rust
    re.compile(r"\bfunc\s+(\(.*\)\s*)?\w+"),           # Go
    re.compile(r"=>\s*\{"),                            # JS/TS arrow with block body
    re.compile(r"\b(public|private|protected|static|async|override)\b.*\([^;]*\)\s*\{?"),  # methods
    re.compile(r"^\s*\w[\w<>,\s\*&:]*\s+\w+\s*\([^;{]*\)\s*\{"),  # C-style "type name(args) {"
]
PY_DEF_PATTERN = re.compile(r"^(\s*)(async\s+def|def)\s+\w+\s*\(")


def scan_brace_file(path, limit):
    """Return list of (line_no, name_hint, body_significant_lines) over the limit."""
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    findings = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if any(p.search(line) for p in BRACE_DEF_PATTERNS):
            # Find the opening brace from this line onward (within a few lines for multi-line sigs).
            brace_line = None
            for j in range(i, min(i + 6, n)):
                if "{" in lines[j]:
                    brace_line = j
                    break
            if brace_line is None:
                i += 1
                continue
            depth = 0
            sig_count = 0
            end = brace_line
            started = False
            for k in range(brace_line, n):
                depth += lines[k].count("{") - lines[k].count("}")
                if k > brace_line and is_significant(lines[k]):
                    sig_count += 1
                started = True
                if started and depth <= 0:
                    end = k
                    break
            if sig_count > limit:
                name = line.strip()[:80]
                findings.append((i + 1, name, sig_count))
            i = max(end, i) + 1
            continue
        i += 1
    return findings


def scan_indent_file(path, limit):
    """Python-style: count the indented block under a def (and nested defs separately)."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    findings = []
    n = len(lines)
    for idx, line in enumerate(lines):
        m = PY_DEF_PATTERN.match(line)
        if not m:
            continue
        def_indent = len(m.group(1))
        sig_count = 0
        k = idx + 1
        # Skip a multi-line signature: advance to the first body line (deeper indent).
        while k < n:
            body = lines[k]
            if not body.strip():
                k += 1
                continue
            cur_indent = len(body) - len(body.lstrip())
            if cur_indent <= def_indent and body.strip():
                break  # dedent back to def level or above -> body ended
            if is_significant(body):
                sig_count += 1
            k += 1
        if sig_count > limit:
            findings.append((idx + 1, line.strip()[:80], sig_count))
    return findings


def read_limit(config_path):
    """Read [function] max_lines from the config (no third-party deps)."""
    val = read_config_section(config_path, "function").get("max_lines")
    if val is None:
        return None
    try:
        return int(val)
    except ValueError:
        return None


def main(argv=None):
    ap = argparse.ArgumentParser(description="LDD max-function-length deny gate.")
    ap.add_argument("paths", nargs="*", default=["."], help="Source roots to scan (default: .).")
    ap.add_argument("--config", default="closure-gate.toml", help="Config with [function] max_lines.")
    ap.add_argument("--limit", type=int, default=None, help="Max body lines (default: config or 40).")
    args = ap.parse_args(argv)

    limit = args.limit if args.limit is not None else (read_limit(Path(args.config)) or 40)
    suffixes = BRACE_SUFFIXES + INDENT_SUFFIXES
    exclude_globs = read_exclude_globs(Path(args.config))
    files = gather_files(args.paths, suffixes, exclude_globs=exclude_globs)
    if not files:
        print("max-function-length: no source files found under", args.paths, file=sys.stderr)
        return 2

    all_findings = []
    for f in files:
        try:
            if f.suffix in INDENT_SUFFIXES:
                fnd = scan_indent_file(f, limit)
            else:
                fnd = scan_brace_file(f, limit)
        except OSError:
            continue
        for (ln, name, length) in fnd:
            all_findings.append((str(f), ln, name, length))

    if not all_findings:
        print(f"max-function-length: OK (no function body over {limit} significant lines).")
        return 0

    print(f"max-function-length: DENY. {len(all_findings)} function(s) over {limit} significant lines:",
          file=sys.stderr)
    for (fp, ln, name, length) in sorted(all_findings, key=lambda x: -x[3]):
        print(f"  {fp}:{ln}  ({length} lines)  {name}", file=sys.stderr)
    print("  Split each into smaller functions; a long function hides duplication and God-objects.",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
