#!/usr/bin/env python3
"""
docs_link_check.py - the portable docs-link gate.

LDD's headline rule is "Done = the clean sweep, not the tests pass". The closure-gate
enforces that on code; this enforces it on the docs the method itself ships. It walks every
tracked-looking markdown file under the given roots and asserts every RELATIVE link resolves
to a real file, so a half-done rename (the council->court class of bug) or a dead reference is
denied at commit time instead of shipping.

It checks only relative links. External links (http/https/mailto), in-page anchors (#frag),
and bare-word placeholders in syntax examples (a target with no "/" and no ".", e.g. `](url)`)
are skipped. The vendored tools/vibe/ tree is skipped (it is third-party, not LDD's deliverable).

Usage: docs_link_check.py [--config PATH] [ROOT ...]   (ROOT defaults to ".")
Exit codes: 0 = all relative links resolve, 1 = at least one is broken.
No third-party dependencies. Python 3.8+.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

LINK_RE = re.compile(r"\]\(([^)]+)\)")
SKIP_DIRS = {".git", "node_modules", "__pycache__"}
SKIP_PREFIXES = ("tools/vibe/",)  # vendored third-party tools, not LDD's own docs


def _iter_markdown(roots):
    for root in roots:
        if os.path.isfile(root) and root.endswith(".md"):
            yield root
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                if fn.endswith(".md"):
                    p = os.path.normpath(os.path.join(dirpath, fn))
                    rel = p[2:] if p.startswith("./") else p
                    if any(rel.startswith(pre) for pre in SKIP_PREFIXES):
                        continue
                    yield p


def _is_relative_path_link(target):
    """A link we should resolve: not external, not a pure anchor, not a bare placeholder word."""
    if not target or target.startswith(("http://", "https://", "mailto:", "#")):
        return False
    path = target.split("#", 1)[0].strip()
    if not path:
        return False
    # A bare word with no separator and no extension is a syntax placeholder (e.g. `](url)`).
    if "/" not in path and "." not in path:
        return False
    return True


def check(roots):
    broken = []
    for md in _iter_markdown(roots):
        base = os.path.dirname(md)
        with open(md, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                for m in LINK_RE.finditer(line):
                    target = m.group(1).strip()
                    if not _is_relative_path_link(target):
                        continue
                    path = target.split("#", 1)[0].strip()
                    resolved = os.path.normpath(os.path.join(base, path))
                    if not os.path.exists(resolved):
                        broken.append((md, lineno, target))
    return broken


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check that relative markdown links resolve.")
    ap.add_argument("--config", default=None, help="Unused; accepted for closure-gate compatibility.")
    ap.add_argument("roots", nargs="*", default=["."], help="Roots to scan (default: .).")
    args = ap.parse_args(argv)
    roots = args.roots or ["."]

    broken = check(roots)
    if broken:
        print(f"docs-links: {len(broken)} broken relative link(s):", file=sys.stderr)
        for (md, lineno, target) in broken:
            print(f"  {md}:{lineno} -> {target}", file=sys.stderr)
        return 1
    print("docs-links: all relative markdown links resolve.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
