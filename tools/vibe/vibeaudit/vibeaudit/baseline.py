"""Baseline management — suppress known findings."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from vibeaudit.models import ScanResult

BASELINE_FILE = ".vibeaudit-baseline.json"


def create_baseline(result: ScanResult, base_dir: Path) -> Path:
    """Create a baseline file from scan results."""
    path = base_dir / BASELINE_FILE
    data = {
        "version": 1,
        "created": datetime.now(timezone.utc).isoformat(),
        "updated": datetime.now(timezone.utc).isoformat(),
        "findings": {
            f.id: {
                "title": f.title,
                "vuln_class": f.vuln_class.value,
                "file": f.file_location,
                "reason": "baselined",
            }
            for f in result.findings
        },
    }
    path.write_text(json.dumps(data, indent=2))
    return path


def update_baseline(result: ScanResult, base_dir: Path) -> Path:
    """Update existing baseline with new findings."""
    path = base_dir / BASELINE_FILE
    data = {"version": 1, "created": datetime.now(timezone.utc).isoformat(), "findings": {}}

    if path.exists():
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            pass

    for f in result.findings:
        if f.id not in data.get("findings", {}):
            data.setdefault("findings", {})[f.id] = {
                "title": f.title,
                "vuln_class": f.vuln_class.value,
                "file": f.file_location,
                "reason": "baselined",
            }

    data["updated"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(data, indent=2))
    return path


def load_baseline(path: Path) -> set[str]:
    """Load baseline finding IDs."""
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text())
        return set(data.get("findings", {}).keys())
    except (json.JSONDecodeError, KeyError):
        return set()
