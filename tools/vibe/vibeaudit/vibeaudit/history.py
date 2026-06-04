"""Scan history management."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from vibeaudit.models import ScanResult

HISTORY_DIR = ".vibeaudit-history"


def store_scan(result: ScanResult, base_dir: Path) -> Path:
    """Store scan result in history directory."""
    history = base_dir / HISTORY_DIR
    history.mkdir(exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    short_hash = hex(abs(hash(result.model_dump_json()[:100])))[2:8]
    filename = f"{ts}-{short_hash}.json"

    path = history / filename
    path.write_text(result.model_dump_json(indent=2))
    return path


def get_last_scan(base_dir: Path) -> ScanResult | None:
    """Get the most recent scan result."""
    history = base_dir / HISTORY_DIR
    if not history.is_dir():
        return None

    files = sorted(history.glob("*.json"), reverse=True)
    if not files:
        return None

    try:
        data = json.loads(files[0].read_text())
        return ScanResult(**data)
    except (json.JSONDecodeError, Exception):
        return None


def get_scan_by_ref(ref: str, base_dir: Path) -> ScanResult | None:
    """Get a scan result by partial filename match or git ref."""
    history = base_dir / HISTORY_DIR
    if not history.is_dir():
        return None

    for f in sorted(history.glob("*.json"), reverse=True):
        if ref in f.name:
            try:
                data = json.loads(f.read_text())
                return ScanResult(**data)
            except Exception:
                continue

    return None
