"""Load .viberapidignore file for gitignore-style path exclusion."""
from __future__ import annotations

from pathlib import Path

import pathspec


def load_ignore_spec(target_dir: str) -> pathspec.PathSpec | None:
    """Load .viberapidignore from the target directory, if it exists."""
    ignore_file = Path(target_dir) / ".viberapidignore"
    if not ignore_file.exists():
        return None
    with open(ignore_file) as f:
        return pathspec.PathSpec.from_lines("gitwildmatch", f)
