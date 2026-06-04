"""Scan persistence — save, load, trend, and prune scan history."""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from viberapid.models import ScanResult

HISTORY_DIR = Path.home() / ".viberapid" / "history"


def _project_hash(target: str) -> str:
    """Deterministic hash of the project path for history bucketing."""
    normalised = os.path.realpath(os.path.expanduser(target))
    return hashlib.sha256(normalised.encode()).hexdigest()[:12]


def _ensure_dir(target: str) -> Path:
    """Ensure history directory for a project exists and return it."""
    project_dir = HISTORY_DIR / _project_hash(target)
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


def save_scan(scan_result: ScanResult) -> Path:
    """Persist a scan result to disk.

    Stores as JSON at ~/.viberapid/history/<project-hash>/<timestamp>.json

    Args:
        scan_result: The completed ScanResult to save.

    Returns:
        Path to the saved JSON file.
    """
    project_dir = _ensure_dir(scan_result.target)

    # Use ISO timestamp with underscores for filename safety
    ts = scan_result.timestamp.replace(":", "-").replace("+", "_")
    filename = f"{ts}.json"
    filepath = project_dir / filename

    data = scan_result.to_dict()
    # Also store the raw target path for reference
    data["_target_path"] = os.path.realpath(os.path.expanduser(scan_result.target))
    data["_project_hash"] = _project_hash(scan_result.target)

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, default=str)

    return filepath


def _load_scan_file(filepath: Path) -> dict[str, Any] | None:
    """Load a single scan JSON file."""
    try:
        with open(filepath) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def load_last(target: str) -> dict[str, Any] | None:
    """Load the most recent scan result for a project.

    Args:
        target: Project directory path.

    Returns:
        The most recent scan data dict, or None if no history exists.
    """
    project_dir = HISTORY_DIR / _project_hash(target)
    if not project_dir.exists():
        return None

    files = sorted(project_dir.glob("*.json"), reverse=True)
    if not files:
        return None

    return _load_scan_file(files[0])


def load_trend(
    target: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Load recent scan results for trend analysis.

    Args:
        target: Project directory path.
        limit: Maximum number of scans to return (most recent first).

    Returns:
        List of scan data dicts, ordered newest-first.
    """
    project_dir = HISTORY_DIR / _project_hash(target)
    if not project_dir.exists():
        return []

    files = sorted(project_dir.glob("*.json"), reverse=True)
    results: list[dict[str, Any]] = []

    for filepath in files[:limit]:
        data = _load_scan_file(filepath)
        if data is not None:
            results.append(data)

    return results


def prune_history(
    target: str,
    retention_days: int = 30,
) -> int:
    """Delete scan history older than retention_days.

    Args:
        target: Project directory path.
        retention_days: Number of days to keep. Scans older than this are deleted.

    Returns:
        Number of files pruned.
    """
    project_dir = HISTORY_DIR / _project_hash(target)
    if not project_dir.exists():
        return 0

    cutoff = time.time() - (retention_days * 86400)
    pruned = 0

    for filepath in project_dir.glob("*.json"):
        try:
            # Use file modification time as the age indicator
            if filepath.stat().st_mtime < cutoff:
                filepath.unlink()
                pruned += 1
        except OSError:
            continue

    # Remove the project dir if empty
    try:
        if project_dir.exists() and not any(project_dir.iterdir()):
            project_dir.rmdir()
    except OSError:
        pass

    return pruned


def list_projects() -> list[dict[str, Any]]:
    """List all projects with scan history.

    Returns:
        List of dicts with project_hash, scan_count, and last_scan info.
    """
    if not HISTORY_DIR.exists():
        return []

    projects: list[dict[str, Any]] = []

    for project_dir in HISTORY_DIR.iterdir():
        if not project_dir.is_dir():
            continue

        files = sorted(project_dir.glob("*.json"), reverse=True)
        if not files:
            continue

        last_scan = _load_scan_file(files[0])
        projects.append({
            "project_hash": project_dir.name,
            "scan_count": len(files),
            "last_scan_timestamp": last_scan.get("timestamp") if last_scan else None,
            "target_path": last_scan.get("_target_path") if last_scan else None,
        })

    return projects
