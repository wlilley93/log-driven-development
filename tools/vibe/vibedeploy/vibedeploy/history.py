"""Scan result persistence and trend analysis."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

HISTORY_DIR = Path.home() / ".vibedeploy" / "history"


def _project_hash(target: str) -> str:
    """Hash the project by its git remote URL, falling back to absolute path."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=target,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            key = result.stdout.strip()
        else:
            key = str(Path(target).resolve())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        key = str(Path(target).resolve())

    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _project_dir(target: str) -> Path:
    return HISTORY_DIR / _project_hash(target)


def save_scan(target: str, scan_data: dict[str, Any]) -> Path:
    """Save scan result to history."""
    project_dir = _project_dir(target)
    project_dir.mkdir(parents=True, exist_ok=True)

    timestamp = scan_data.get("timestamp", datetime.now(timezone.utc).isoformat())
    safe_ts = timestamp.replace(":", "-").replace("+", "_")
    filepath = project_dir / f"{safe_ts}.json"

    with open(filepath, "w") as f:
        json.dump(scan_data, f, indent=2, default=str)

    return filepath


def load_last(target: str) -> dict[str, Any] | None:
    """Load the most recent scan result for a project."""
    project_dir = _project_dir(target)
    if not project_dir.exists():
        return None

    files = sorted(project_dir.glob("*.json"), reverse=True)
    if not files:
        return None

    with open(files[0]) as f:
        return json.load(f)


def load_trend(target: str, limit: int = 20) -> list[dict[str, Any]]:
    """Load scan history for trend analysis."""
    project_dir = _project_dir(target)
    if not project_dir.exists():
        return []

    files = sorted(project_dir.glob("*.json"), reverse=True)[:limit]
    results = []
    for filepath in reversed(files):
        try:
            with open(filepath) as f:
                data = json.load(f)
                results.append({
                    "timestamp": data.get("timestamp"),
                    "severity_counts": data.get("severity_counts", {}),
                    "readiness_score": data.get("readiness_score", 0),
                    "deploy_ready": data.get("deploy_ready", False),
                    "blocker_count": data.get("blocker_count", 0),
                    "exit_code": data.get("exit_code", 0),
                    "duration_seconds": data.get("duration_seconds", 0),
                })
        except (json.JSONDecodeError, KeyError):
            continue

    return results


def prune_history(target: str, retention_days: int = 30) -> int:
    """Remove history entries older than retention period. Returns count removed."""
    project_dir = _project_dir(target)
    if not project_dir.exists():
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    removed = 0

    for filepath in project_dir.glob("*.json"):
        try:
            with open(filepath) as f:
                data = json.load(f)
            ts = data.get("timestamp", "")
            if ts and datetime.fromisoformat(ts) < cutoff:
                filepath.unlink()
                removed += 1
        except (json.JSONDecodeError, ValueError, OSError):
            continue

    return removed
