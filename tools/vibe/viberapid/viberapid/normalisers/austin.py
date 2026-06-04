"""Normaliser for austin output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser

# Percentage thresholds for severity classification
SAMPLE_HIGH_THRESHOLD = 20.0
SAMPLE_MEDIUM_THRESHOLD = 10.0
SAMPLE_LOW_THRESHOLD = 5.0


class AustinNormaliser(BaseNormaliser):
    """Convert austin parsed output to Finding objects.

    Expected data shape (produced by AustinRunner._parse_collapsed_stacks):
    {
      "total_samples": 10000,
      "frames": [
        {
          "file": "app.py",
          "function": "process_data",
          "line": 42,
          "inclusive_samples": 3500,
          "percent": 35.0
        }
      ]
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        total_samples = raw_data.get("total_samples", 0)
        frames = raw_data.get("frames", [])

        if not isinstance(frames, list) or total_samples <= 0:
            return []

        findings: list[Finding] = []

        for frame in frames:
            if not isinstance(frame, dict):
                continue

            finding = self._normalise_frame(frame, total_samples)
            if finding:
                findings.append(finding)

        return findings

    def _normalise_frame(self, frame: dict[str, Any], total_samples: int) -> Finding | None:
        """Convert a single frame entry to a Finding."""
        filepath = frame.get("file", "<unknown>")
        function = frame.get("function", "<unknown>")
        line = frame.get("line")
        pct = _safe_float(frame.get("percent", 0))
        inclusive_samples = frame.get("inclusive_samples", 0)

        # Skip frames below the reporting threshold
        if pct < SAMPLE_LOW_THRESHOLD:
            return None

        # Skip internal/stdlib frames
        if _is_internal_frame(filepath, function):
            return None

        severity = _classify_severity(pct)
        effort = Effort.HIGH if pct >= SAMPLE_HIGH_THRESHOLD else Effort.MEDIUM

        return Finding(
            tool="austin",
            severity=severity,
            category=Category.RUNTIME,
            file=filepath,
            rule_id="austin/cpu-hotspot",
            rule_name="CPU hotspot (sampled)",
            message=(
                f"'{function}' accounts for {pct:.1f}% of CPU samples "
                f"({inclusive_samples:,} of {total_samples:,} samples). "
                "Near-zero-overhead sampling confirms this is a real hotspot."
            ),
            line=line,
            fix_hint=_build_fix_hint(function, pct),
            metric="cpu_sample_percent",
            current_value=round(pct, 1),
            target_value=SAMPLE_MEDIUM_THRESHOLD,
            saving_estimate=(
                f"Optimising '{function}' could reclaim ~{pct:.0f}% CPU time"
            ),
            effort=effort,
            raw=frame,
        )


def _is_internal_frame(filepath: str, function: str) -> bool:
    """Return True if the frame is from Python internals or third-party packages."""
    internal_markers = (
        "/lib/python", "site-packages/", "<frozen", "<built-in",
        "/importlib/", "/_bootstrap", "runpy.py",
    )
    return any(marker in filepath for marker in internal_markers)


def _classify_severity(pct: float) -> Severity:
    """Classify severity based on sample percentage."""
    if pct >= SAMPLE_HIGH_THRESHOLD:
        return Severity.HIGH
    if pct >= SAMPLE_MEDIUM_THRESHOLD:
        return Severity.MEDIUM
    return Severity.LOW


def _build_fix_hint(function: str, pct: float) -> str:
    """Generate a targeted fix hint for CPU hotspots."""
    if pct >= 40:
        return (
            f"'{function}' dominates CPU ({pct:.0f}%). austin's low-overhead sampling "
            "confirms this is the real bottleneck (not profiler artefact). Focus here: "
            "algorithmic changes, Cython/C extension for hot loops, or offload to "
            "multiprocessing. Use austin-tui for interactive flame graph analysis."
        )
    if pct >= SAMPLE_HIGH_THRESHOLD:
        return (
            f"'{function}' is a major CPU consumer ({pct:.0f}%). Consider: caching "
            "with functools.lru_cache, vectorising with numpy, reducing iteration "
            "count, or pre-computing values. austin's overhead is <1%, so these "
            "numbers closely match production behaviour."
        )
    if pct >= SAMPLE_MEDIUM_THRESHOLD:
        return (
            f"'{function}' uses {pct:.0f}% CPU. Review for: unnecessary recomputation, "
            "sub-optimal data structures (dict vs set for lookups), or tight loops that "
            "could be replaced with built-in operations (map, filter, comprehensions)."
        )
    return (
        f"'{function}' uses {pct:.0f}% CPU. Minor hotspot — optimise if called in a "
        "tight loop or on a hot path. Consider memoisation or batching."
    )


def _safe_float(value: Any) -> float:
    """Safely convert a value to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
