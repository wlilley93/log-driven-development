"""Normaliser for py-spy speedscope JSON output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser

# Percentage of total samples a frame must consume to be reported
SAMPLE_HIGH_THRESHOLD = 20.0
SAMPLE_MEDIUM_THRESHOLD = 10.0
SAMPLE_LOW_THRESHOLD = 5.0


class PySpyNormaliser(BaseNormaliser):
    """Convert py-spy speedscope JSON output to Finding objects.

    py-spy speedscope JSON shape:
    {
      "$schema": "https://www.speedscope.app/file-format-schema.json",
      "shared": {
        "frames": [
          {"name": "func_name", "file": "/path/to/file.py", "line": 42, "col": 0}
        ]
      },
      "profiles": [
        {
          "type": "sampled",
          "name": "...",
          "unit": "seconds",
          "startValue": 0,
          "endValue": 10.0,
          "samples": [[0, 1, 2], [0, 1, 3], ...],
          "weights": [0.01, 0.01, ...],
          "frames": [
            {"name": "func_name", "file": "/path/to/file.py", "line": 42}
          ]
        }
      ]
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        # speedscope format can have frames in "shared" or inline in profiles
        shared_frames = []
        shared = raw_data.get("shared", {})
        if isinstance(shared, dict):
            shared_frames = shared.get("frames", [])

        profiles = raw_data.get("profiles", [])
        if not isinstance(profiles, list):
            return []

        findings: list[Finding] = []

        for profile in profiles:
            if not isinstance(profile, dict):
                continue
            findings.extend(self._normalise_profile(profile, shared_frames))

        return findings

    def _normalise_profile(
        self, profile: dict[str, Any], shared_frames: list[dict]
    ) -> list[Finding]:
        """Normalise a single speedscope profile."""
        profile_type = profile.get("type", "")
        frames = profile.get("frames", shared_frames)
        if not isinstance(frames, list) or not frames:
            return []

        samples = profile.get("samples", [])
        weights = profile.get("weights", [])
        if not isinstance(samples, list) or not samples:
            return []

        # Accumulate time per frame index
        frame_time: dict[int, float] = {}
        total_time = 0.0

        for i, sample in enumerate(samples):
            weight = _safe_float(weights[i]) if i < len(weights) else 0.01
            total_time += weight
            if not isinstance(sample, list):
                continue
            # Each sample is a stack of frame indices; attribute time to leaf
            # but also accumulate for all frames in the stack (inclusive time)
            seen_in_stack: set[int] = set()
            for frame_idx in sample:
                if isinstance(frame_idx, int) and frame_idx not in seen_in_stack:
                    seen_in_stack.add(frame_idx)
                    frame_time[frame_idx] = frame_time.get(frame_idx, 0.0) + weight

        if total_time <= 0:
            return []

        findings: list[Finding] = []

        for frame_idx, inclusive_time in sorted(
            frame_time.items(), key=lambda x: x[1], reverse=True
        ):
            if frame_idx >= len(frames):
                continue

            frame = frames[frame_idx]
            if not isinstance(frame, dict):
                continue

            name = frame.get("name", "<unknown>")
            filepath = frame.get("file", "<unknown>")
            line = frame.get("line")

            # Skip stdlib / site-packages unless they dominate
            if _is_internal_frame(filepath, name):
                continue

            pct = (inclusive_time / total_time) * 100.0
            if pct < SAMPLE_LOW_THRESHOLD:
                continue

            severity = _classify_severity(pct)
            effort = Effort.HIGH if pct >= SAMPLE_HIGH_THRESHOLD else Effort.MEDIUM

            findings.append(Finding(
                tool="py-spy",
                severity=severity,
                category=Category.RUNTIME,
                file=filepath,
                rule_id="py-spy/cpu-hotspot",
                rule_name="CPU hotspot (sampled)",
                message=(
                    f"'{name}' accounts for {pct:.1f}% of sampled CPU time "
                    f"({inclusive_time:.3f}s of {total_time:.3f}s total)."
                ),
                line=line,
                fix_hint=_build_fix_hint(name, pct),
                metric="cpu_sample_percent",
                current_value=round(pct, 1),
                target_value=SAMPLE_MEDIUM_THRESHOLD,
                saving_estimate=(
                    f"Optimising '{name}' could reclaim ~{pct:.0f}% CPU "
                    f"(~{inclusive_time:.2f}s)"
                ),
                effort=effort,
                raw={
                    "frame_name": name,
                    "file": filepath,
                    "line": line,
                    "inclusive_time_seconds": round(inclusive_time, 4),
                    "sample_percent": round(pct, 2),
                },
            ))

        return findings


def _is_internal_frame(filepath: str, name: str) -> bool:
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


def _build_fix_hint(name: str, pct: float) -> str:
    """Generate a targeted fix hint for CPU hotspots."""
    if pct >= 40:
        return (
            f"'{name}' dominates CPU time ({pct:.0f}%). This is the primary "
            "optimisation target. Consider: algorithmic improvements, caching with "
            "functools.lru_cache, offloading to C extensions (Cython, pybind11), "
            "or parallelising with multiprocessing/concurrent.futures."
        )
    if pct >= SAMPLE_HIGH_THRESHOLD:
        return (
            f"'{name}' is a significant hotspot ({pct:.0f}%). Profile individual "
            "lines with scalene, check for unnecessary allocations, consider "
            "vectorisation with numpy, or cache repeated computations."
        )
    return (
        f"'{name}' consumes notable CPU ({pct:.0f}%). Review for redundant work, "
        "tight loops that could be batched, or data structure choices that affect "
        "lookup/iteration performance."
    )


def _safe_float(value: Any) -> float:
    """Safely convert a value to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
