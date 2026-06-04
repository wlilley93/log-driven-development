"""Normaliser for pyinstrument output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser

# Thresholds for classifying slow functions (in seconds)
TIME_HIGH_THRESHOLD = 1.0
TIME_MEDIUM_THRESHOLD = 0.1
TIME_LOW_THRESHOLD = 0.01

# Maximum depth to walk the call tree
MAX_TREE_DEPTH = 50

# Minimum proportion of total time for a frame to be reported
MIN_TIME_FRACTION = 0.05


class PyinstrumentNormaliser(BaseNormaliser):
    """Convert pyinstrument JSON output to Finding objects.

    pyinstrument JSON shape:
    {
      "root_frame": {
        "function": "<module>",
        "file_path": "app.py",
        "file_path_short": "app.py",
        "line_no": 1,
        "time": 5.234,
        "is_application_code": true,
        "children": [
          {
            "function": "process",
            "file_path": "/path/to/app.py",
            "file_path_short": "app.py",
            "line_no": 42,
            "time": 3.1,
            "is_application_code": true,
            "children": [...]
          }
        ]
      }
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        root_frame = raw_data.get("root_frame", raw_data)
        if not isinstance(root_frame, dict):
            return []

        total_time = _safe_float(root_frame.get("time", 0))
        if total_time <= 0:
            return []

        findings: list[Finding] = []
        self._walk_frame(root_frame, total_time, findings, depth=0)
        return findings

    def _walk_frame(
        self,
        frame: dict[str, Any],
        total_time: float,
        findings: list[Finding],
        depth: int,
    ) -> None:
        """Recursively walk the call tree and emit findings for slow frames."""
        if depth > MAX_TREE_DEPTH:
            return

        function = frame.get("function", "<unknown>")
        filepath = frame.get("file_path_short") or frame.get("file_path", "<unknown>")
        line_no = frame.get("line_no")
        frame_time = _safe_float(frame.get("time", 0))
        is_app_code = frame.get("is_application_code", False)

        time_fraction = frame_time / total_time if total_time > 0 else 0

        # Only report application code frames that exceed the minimum threshold
        if is_app_code and time_fraction >= MIN_TIME_FRACTION and frame_time >= TIME_LOW_THRESHOLD:
            severity = self._classify_severity(frame_time)
            effort = self._classify_effort(frame_time, function)

            findings.append(Finding(
                tool="pyinstrument",
                severity=severity,
                category=Category.RUNTIME,
                file=filepath,
                rule_id="pyinstrument/slow-call",
                rule_name="Slow function call",
                message=(
                    f"'{function}' took {frame_time:.3f}s "
                    f"({time_fraction * 100:.1f}% of total {total_time:.3f}s runtime)."
                ),
                line=line_no,
                fix_hint=self._build_fix_hint(function, frame_time, time_fraction),
                metric="duration_seconds",
                current_value=round(frame_time, 3),
                target_value=TIME_MEDIUM_THRESHOLD,
                saving_estimate=(
                    f"Optimising '{function}' could save ~{frame_time:.2f}s "
                    f"({time_fraction * 100:.0f}% of total runtime)"
                ),
                effort=effort,
                raw={
                    "function": function,
                    "time": round(frame_time, 4),
                    "time_fraction": round(time_fraction, 4),
                    "is_application_code": is_app_code,
                    "depth": depth,
                },
            ))

        # Walk children
        children = frame.get("children", [])
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    self._walk_frame(child, total_time, findings, depth + 1)

    def _classify_severity(self, frame_time: float) -> Severity:
        """Classify severity based on absolute time."""
        if frame_time >= TIME_HIGH_THRESHOLD:
            return Severity.HIGH
        if frame_time >= TIME_MEDIUM_THRESHOLD:
            return Severity.MEDIUM
        return Severity.LOW

    def _classify_effort(self, frame_time: float, function: str) -> Effort:
        """Estimate the effort to fix a slow call."""
        # Very slow functions often need algorithmic changes
        if frame_time >= TIME_HIGH_THRESHOLD:
            return Effort.HIGH
        # Moderately slow can often be fixed with caching or minor refactors
        if frame_time >= TIME_MEDIUM_THRESHOLD:
            return Effort.MEDIUM
        return Effort.LOW

    def _build_fix_hint(self, function: str, time_sec: float, fraction: float) -> str:
        """Generate a targeted fix hint."""
        if time_sec >= 2.0:
            return (
                f"'{function}' is extremely slow ({time_sec:.1f}s). Investigate: "
                "I/O blocking (database queries, file reads, HTTP calls), "
                "algorithmic complexity, or missing caching. Consider async I/O, "
                "connection pooling, or batch processing."
            )
        if time_sec >= TIME_HIGH_THRESHOLD:
            return (
                f"'{function}' takes {time_sec:.2f}s ({fraction * 100:.0f}% of runtime). "
                "Check for: N+1 queries, redundant computation, large data copies, "
                "or synchronous I/O that could be async."
            )
        if time_sec >= TIME_MEDIUM_THRESHOLD:
            return (
                f"'{function}' takes {time_sec * 1000:.0f}ms. Consider caching with "
                "functools.lru_cache, reducing loop iterations, or pre-computing values."
            )
        return (
            f"'{function}' contributes {fraction * 100:.1f}% of total time. "
            "Minor optimisation may help if called frequently."
        )


def _safe_float(value: Any) -> float:
    """Safely convert a value to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
