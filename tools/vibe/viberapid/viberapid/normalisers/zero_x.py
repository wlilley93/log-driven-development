"""Normaliser for 0x flamegraph profiler output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser

# Percentage thresholds for severity classification
SAMPLE_HIGH_THRESHOLD = 20.0
SAMPLE_MEDIUM_THRESHOLD = 10.0
SAMPLE_LOW_THRESHOLD = 5.0


class ZeroXNormaliser(BaseNormaliser):
    """Convert 0x parsed profile data to Finding objects.

    Expected data shape (produced by ZeroXRunner._parse_profile_data):
    {
      "total_samples": 10000,
      "frames": [
        {
          "name": "processRequest",
          "file": "server.js",
          "line": 42,
          "inclusive_samples": 3500,
          "percent": 35.0
        }
      ],
      "meta": {...}
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
        name = frame.get("name", "<unknown>")
        filepath = frame.get("file", "<unknown>")
        line = frame.get("line")
        pct = _safe_float(frame.get("percent", 0))
        inclusive_samples = frame.get("inclusive_samples", 0)

        if pct < SAMPLE_LOW_THRESHOLD:
            return None

        # Skip Node.js internals and V8 builtins
        if _is_internal_frame(filepath, name):
            return None

        severity = _classify_severity(pct)
        effort = Effort.HIGH if pct >= SAMPLE_HIGH_THRESHOLD else Effort.MEDIUM

        return Finding(
            tool="0x",
            severity=severity,
            category=Category.RUNTIME,
            file=filepath,
            rule_id="0x/cpu-hotspot",
            rule_name="CPU hotspot (V8 flamegraph)",
            message=(
                f"'{name}' accounts for {pct:.1f}% of CPU samples "
                f"({inclusive_samples:,} of {total_samples:,} samples)."
            ),
            line=line,
            fix_hint=_build_fix_hint(name, pct),
            metric="cpu_sample_percent",
            current_value=round(pct, 1),
            target_value=SAMPLE_MEDIUM_THRESHOLD,
            saving_estimate=f"Optimising '{name}' could reclaim ~{pct:.0f}% CPU time",
            effort=effort,
            raw=frame,
        )


def _is_internal_frame(filepath: str, name: str) -> bool:
    """Return True for Node.js internals, V8 builtins, and third-party code."""
    internal_markers = (
        "node_modules/", "node:internal", "/internal/",
        "<anonymous>", "(idle)", "(program)", "(garbage collector)",
        "native ", "v8::", "Builtins_",
    )
    skip_names = ("(idle)", "(program)", "(garbage collector)", "(root)", "")
    return (
        any(marker in filepath or marker in name for marker in internal_markers)
        or name in skip_names
    )


def _classify_severity(pct: float) -> Severity:
    """Classify severity based on sample percentage."""
    if pct >= SAMPLE_HIGH_THRESHOLD:
        return Severity.HIGH
    if pct >= SAMPLE_MEDIUM_THRESHOLD:
        return Severity.MEDIUM
    return Severity.LOW


def _build_fix_hint(name: str, pct: float) -> str:
    """Generate a targeted fix hint for Node.js CPU hotspots."""
    if pct >= 40:
        return (
            f"'{name}' dominates CPU ({pct:.0f}%). This is the primary bottleneck. "
            "Consider: offloading to worker_threads, caching with Map or Redis, "
            "algorithmic improvements, or replacing JSON.parse/stringify on hot paths "
            "with streaming parsers (json-stream, fast-json-stringify)."
        )
    if pct >= SAMPLE_HIGH_THRESHOLD:
        return (
            f"'{name}' is a major CPU consumer ({pct:.0f}%). Review with the 0x "
            "flamegraph (open the HTML file in a browser). Check for: synchronous "
            "crypto operations (use async variants), regex backtracking, deep object "
            "cloning, or unoptimised loops over large datasets."
        )
    if pct >= SAMPLE_MEDIUM_THRESHOLD:
        return (
            f"'{name}' uses {pct:.0f}% CPU. Common fixes: cache expensive computations, "
            "avoid creating objects in hot paths (pre-allocate), use Buffer instead of "
            "string concatenation, and batch database queries."
        )
    return (
        f"'{name}' uses {pct:.0f}% CPU. Minor hotspot — optimise if on a critical "
        "request path or called frequently. Consider memoisation or lazy evaluation."
    )


def _safe_float(value: Any) -> float:
    """Safely convert a value to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
