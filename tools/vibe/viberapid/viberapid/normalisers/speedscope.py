"""Normaliser for speedscope JSON profile format."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser

# Thresholds for reporting frames
WEIGHT_HIGH_THRESHOLD = 20.0  # percentage of total weight
WEIGHT_MEDIUM_THRESHOLD = 10.0
WEIGHT_LOW_THRESHOLD = 5.0


class SpeedscopeNormaliser(BaseNormaliser):
    """Convert speedscope JSON format to Finding objects.

    speedscope JSON schema (https://www.speedscope.app/file-format-schema.json):
    {
      "$schema": "https://www.speedscope.app/file-format-schema.json",
      "shared": {
        "frames": [
          {"name": "function_name", "file": "file.py", "line": 42, "col": 0}
        ]
      },
      "profiles": [
        {
          "type": "sampled" | "evented",
          "name": "profile-name",
          "unit": "seconds" | "microseconds" | "milliseconds" | "nanoseconds" | "bytes" | "none",
          "startValue": 0,
          "endValue": 100,
          "samples": [[0, 1, 2], ...],      # sampled: stack index arrays
          "weights": [0.01, ...],             # sampled: weight per sample
          "events": [...]                     # evented: open/close frame events
        }
      ]
    }

    Also handles Chrome DevTools .cpuprofile format:
    {
      "nodes": [{"id": 1, "callFrame": {"functionName": "...", "url": "...", "lineNumber": 0}, "children": [2, 3]}],
      "startTime": 0,
      "endTime": 1000,
      "samples": [1, 2, 3, ...],
      "timeDeltas": [100, 200, ...]
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        # Detect format
        if "profiles" in raw_data:
            return self._normalise_speedscope(raw_data)
        elif "nodes" in raw_data and "samples" in raw_data:
            return self._normalise_cpuprofile(raw_data)

        return []

    def _normalise_speedscope(self, data: dict[str, Any]) -> list[Finding]:
        """Normalise speedscope native format."""
        shared_frames = []
        shared = data.get("shared", {})
        if isinstance(shared, dict):
            shared_frames = shared.get("frames", [])

        profiles = data.get("profiles", [])
        if not isinstance(profiles, list):
            return []

        findings: list[Finding] = []

        for profile in profiles:
            if not isinstance(profile, dict):
                continue

            profile_type = profile.get("type", "sampled")
            frames = profile.get("frames", shared_frames)

            if profile_type == "sampled":
                findings.extend(self._normalise_sampled_profile(profile, frames))
            elif profile_type == "evented":
                findings.extend(self._normalise_evented_profile(profile, frames))

        return findings

    def _normalise_sampled_profile(
        self, profile: dict[str, Any], frames: list
    ) -> list[Finding]:
        """Normalise a sampled profile (stack snapshots with weights)."""
        samples = profile.get("samples", [])
        weights = profile.get("weights", [])
        unit = profile.get("unit", "seconds")

        if not isinstance(samples, list) or not samples:
            return []
        if not isinstance(frames, list) or not frames:
            return []

        # Accumulate inclusive time per frame
        frame_weight: dict[int, float] = {}
        total_weight = 0.0

        for i, sample in enumerate(samples):
            weight = _safe_float(weights[i]) if i < len(weights) else 1.0
            total_weight += weight

            if not isinstance(sample, list):
                continue

            seen: set[int] = set()
            for idx in sample:
                if isinstance(idx, int) and idx not in seen:
                    seen.add(idx)
                    frame_weight[idx] = frame_weight.get(idx, 0.0) + weight

        if total_weight <= 0:
            return []

        return self._build_findings_from_weights(
            frames, frame_weight, total_weight, unit
        )

    def _normalise_evented_profile(
        self, profile: dict[str, Any], frames: list
    ) -> list[Finding]:
        """Normalise an evented profile (open/close frame events)."""
        events = profile.get("events", [])
        unit = profile.get("unit", "seconds")

        if not isinstance(events, list) or not events:
            return []
        if not isinstance(frames, list) or not frames:
            return []

        # Track open frames and accumulate durations
        open_stack: list[tuple[int, float]] = []  # (frame_idx, open_time)
        frame_duration: dict[int, float] = {}
        total_duration = 0.0

        for event in events:
            if not isinstance(event, dict):
                continue

            event_type = event.get("type", "")
            frame_idx = event.get("frame", -1)
            at = _safe_float(event.get("at", 0))

            if event_type == "O":  # Open
                open_stack.append((frame_idx, at))
            elif event_type == "C" and open_stack:  # Close
                # Pop matching frame
                for j in range(len(open_stack) - 1, -1, -1):
                    if open_stack[j][0] == frame_idx:
                        _, open_time = open_stack.pop(j)
                        duration = at - open_time
                        frame_duration[frame_idx] = (
                            frame_duration.get(frame_idx, 0.0) + duration
                        )
                        total_duration = max(total_duration, at)
                        break

        if total_duration <= 0:
            return []

        return self._build_findings_from_weights(
            frames, frame_duration, total_duration, unit
        )

    def _build_findings_from_weights(
        self,
        frames: list,
        frame_weight: dict[int, float],
        total_weight: float,
        unit: str,
    ) -> list[Finding]:
        """Build findings from accumulated per-frame weights."""
        findings: list[Finding] = []

        for idx, weight in sorted(
            frame_weight.items(), key=lambda x: x[1], reverse=True
        ):
            if idx >= len(frames):
                continue

            frame = frames[idx]
            if not isinstance(frame, dict):
                continue

            name = frame.get("name", "<unknown>")
            filepath = frame.get("file", "<unknown>")
            line = frame.get("line")

            if _is_internal_frame(filepath, name):
                continue

            pct = (weight / total_weight) * 100.0
            if pct < WEIGHT_LOW_THRESHOLD:
                continue

            severity = _classify_severity(pct)
            unit_label = _unit_label(unit)

            findings.append(Finding(
                tool="speedscope",
                severity=severity,
                category=Category.RUNTIME,
                file=filepath,
                rule_id="speedscope/hotspot",
                rule_name=f"Performance hotspot ({unit_label})",
                message=(
                    f"'{name}' accounts for {pct:.1f}% of {unit_label} "
                    f"({weight:.3f} {unit} of {total_weight:.3f} total)."
                ),
                line=line,
                fix_hint=_build_fix_hint(name, pct, unit),
                metric=f"{unit}_percent",
                current_value=round(pct, 1),
                target_value=WEIGHT_MEDIUM_THRESHOLD,
                saving_estimate=f"Optimising '{name}' could improve {unit_label} by ~{pct:.0f}%",
                effort=Effort.HIGH if pct >= WEIGHT_HIGH_THRESHOLD else Effort.MEDIUM,
                raw={
                    "frame_name": name,
                    "file": filepath,
                    "line": line,
                    "weight": round(weight, 4),
                    "percent": round(pct, 2),
                    "unit": unit,
                },
            ))

        return findings

    def _normalise_cpuprofile(self, data: dict[str, Any]) -> list[Finding]:
        """Normalise Chrome DevTools .cpuprofile format."""
        nodes = data.get("nodes", [])
        samples = data.get("samples", [])
        time_deltas = data.get("timeDeltas", [])

        if not isinstance(nodes, list) or not isinstance(samples, list):
            return []

        # Build node lookup
        node_map: dict[int, dict] = {}
        for node in nodes:
            if isinstance(node, dict):
                node_map[node.get("id", -1)] = node

        # Accumulate time per node
        node_time: dict[int, float] = {}
        total_time = 0.0

        for i, sample_id in enumerate(samples):
            delta = _safe_float(time_deltas[i]) if i < len(time_deltas) else 0.0
            total_time += delta
            node_time[sample_id] = node_time.get(sample_id, 0.0) + delta

        if total_time <= 0:
            return []

        findings: list[Finding] = []

        for node_id, time in sorted(node_time.items(), key=lambda x: x[1], reverse=True):
            node = node_map.get(node_id)
            if not node:
                continue

            call_frame = node.get("callFrame", {})
            if not isinstance(call_frame, dict):
                continue

            name = call_frame.get("functionName", "<anonymous>")
            url = call_frame.get("url", "<unknown>")
            line = call_frame.get("lineNumber")

            if not name or name in ("(idle)", "(program)", "(garbage collector)"):
                continue

            pct = (time / total_time) * 100.0
            if pct < WEIGHT_LOW_THRESHOLD:
                continue

            severity = _classify_severity(pct)

            findings.append(Finding(
                tool="speedscope",
                severity=severity,
                category=Category.RUNTIME,
                file=url,
                rule_id="speedscope/cpuprofile-hotspot",
                rule_name="CPU hotspot (V8 profile)",
                message=(
                    f"'{name}' accounts for {pct:.1f}% of CPU time "
                    f"({time / 1000:.1f}ms of {total_time / 1000:.1f}ms total)."
                ),
                line=line,
                fix_hint=_build_fix_hint(name, pct, "microseconds"),
                metric="cpu_percent",
                current_value=round(pct, 1),
                target_value=WEIGHT_MEDIUM_THRESHOLD,
                effort=Effort.HIGH if pct >= WEIGHT_HIGH_THRESHOLD else Effort.MEDIUM,
                raw={
                    "node_id": node_id,
                    "function_name": name,
                    "url": url,
                    "time_us": round(time, 2),
                    "percent": round(pct, 2),
                },
            ))

        return findings


def _is_internal_frame(filepath: str, name: str) -> bool:
    """Return True for internal/stdlib frames that should be skipped."""
    internal_markers = (
        "/lib/python", "site-packages/", "<frozen", "<built-in",
        "node_modules/", "/internal/", "node:internal",
        "/importlib/", "/_bootstrap",
    )
    skip_names = ("(idle)", "(program)", "(garbage collector)", "<anonymous>", "(root)")
    return (
        any(marker in filepath for marker in internal_markers)
        or name in skip_names
    )


def _classify_severity(pct: float) -> Severity:
    """Classify severity based on weight percentage."""
    if pct >= WEIGHT_HIGH_THRESHOLD:
        return Severity.HIGH
    if pct >= WEIGHT_MEDIUM_THRESHOLD:
        return Severity.MEDIUM
    return Severity.LOW


def _unit_label(unit: str) -> str:
    """Convert speedscope unit to a human-readable label."""
    labels = {
        "seconds": "CPU time",
        "milliseconds": "CPU time",
        "microseconds": "CPU time",
        "nanoseconds": "CPU time",
        "bytes": "memory",
        "none": "samples",
    }
    return labels.get(unit, "profiler samples")


def _build_fix_hint(name: str, pct: float, unit: str) -> str:
    """Generate a fix hint based on the hotspot."""
    resource = "CPU time" if "second" in unit or "microsecond" in unit else "resources"

    if pct >= 40:
        return (
            f"'{name}' dominates {resource} ({pct:.0f}%). Open the profile in "
            "speedscope (npx speedscope <file>) for interactive flame graph analysis. "
            "Focus on: algorithmic complexity, unnecessary allocations, and I/O blocking."
        )
    if pct >= WEIGHT_HIGH_THRESHOLD:
        return (
            f"'{name}' is a significant hotspot ({pct:.0f}%). Review with the "
            "speedscope left-heavy view to see which callers contribute most. "
            "Consider caching, batching, or offloading to background processing."
        )
    return (
        f"'{name}' consumes {pct:.0f}% of {resource}. Open in speedscope for "
        "call-tree context and check for redundant work or tight loops."
    )


def _safe_float(value: Any) -> float:
    """Safely convert a value to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
