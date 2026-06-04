"""Feedback tracking — mark findings as false positives."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel

FEEDBACK_FILE = ".vibeaudit-feedback.json"


class FeedbackEntry(BaseModel):
    finding_id: str
    true_positive: bool
    reason: str
    timestamp: str


def record_feedback(finding_id: str, true_positive: bool, reason: str, base_dir: Path) -> None:
    """Record feedback for a finding."""
    path = base_dir / FEEDBACK_FILE
    entries: list[dict] = []

    if path.exists():
        try:
            entries = json.loads(path.read_text())
        except json.JSONDecodeError:
            entries = []

    entries.append({
        "finding_id": finding_id,
        "true_positive": true_positive,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    path.write_text(json.dumps(entries, indent=2))


def load_feedback(base_dir: Path) -> dict[str, FeedbackEntry]:
    """Load all feedback entries keyed by finding_id."""
    path = base_dir / FEEDBACK_FILE
    if not path.exists():
        return {}

    try:
        entries = json.loads(path.read_text())
        result = {}
        for entry in entries:
            fe = FeedbackEntry(**entry)
            result[fe.finding_id] = fe
        return result
    except (json.JSONDecodeError, KeyError):
        return {}
