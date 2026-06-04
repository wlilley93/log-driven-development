"""Normaliser for memray output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser

# Memory allocation thresholds (MB) for severity classification
ALLOC_HIGH_THRESHOLD = 50.0
ALLOC_MEDIUM_THRESHOLD = 10.0

# Percentage thresholds for severity
PCT_HIGH_THRESHOLD = 25.0
PCT_MEDIUM_THRESHOLD = 10.0

# Peak memory threshold for a warning
PEAK_MEMORY_WARNING_MB = 512.0
PEAK_MEMORY_CRITICAL_MB = 1024.0


class MemrayNormaliser(BaseNormaliser):
    """Convert memray stats output to Finding objects.

    Expected data shape (parsed from memray stats text):
    {
      "total_allocations": 12345,
      "total_memory_mb": 256.5,
      "peak_memory_mb": 128.3,
      "top_by_size": [
        {
          "file": "file.py",
          "line": 42,
          "function": "func_name",
          "size_mb": 64.2,
          "count": 0,
          "percent": 50.0
        }
      ],
      "top_by_count": [
        {
          "file": "file.py",
          "line": 42,
          "function": "func_name",
          "size_mb": 0.0,
          "count": 5000,
          "percent": 40.0
        }
      ]
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        findings: list[Finding] = []

        peak_mb = _safe_float(raw_data.get("peak_memory_mb", 0))
        total_mb = _safe_float(raw_data.get("total_memory_mb", 0))

        # Peak memory usage finding
        if peak_mb >= PEAK_MEMORY_WARNING_MB:
            severity = (
                Severity.CRITICAL if peak_mb >= PEAK_MEMORY_CRITICAL_MB
                else Severity.HIGH
            )
            findings.append(Finding(
                tool="memray",
                severity=severity,
                category=Category.RUNTIME,
                file="<process>",
                rule_id="memray/peak-memory",
                rule_name="High peak memory usage",
                message=(
                    f"Peak memory usage: {peak_mb:.1f} MB "
                    f"(total allocated: {total_mb:.1f} MB). "
                    "This may cause OOM kills in constrained environments."
                ),
                fix_hint=_peak_memory_hint(peak_mb),
                metric="peak_memory_mb",
                current_value=round(peak_mb, 1),
                target_value=PEAK_MEMORY_WARNING_MB,
                saving_estimate=f"Reducing peak memory could save ~{peak_mb - PEAK_MEMORY_WARNING_MB:.0f} MB",
                effort=Effort.HIGH,
                raw={
                    "peak_memory_mb": round(peak_mb, 2),
                    "total_memory_mb": round(total_mb, 2),
                },
            ))

        # Top allocators by size
        top_by_size = raw_data.get("top_by_size", [])
        if isinstance(top_by_size, list):
            for alloc in top_by_size:
                if not isinstance(alloc, dict):
                    continue
                finding = self._normalise_size_allocator(alloc, total_mb)
                if finding:
                    findings.append(finding)

        # Top allocators by count (high allocation count = GC pressure)
        top_by_count = raw_data.get("top_by_count", [])
        if isinstance(top_by_count, list):
            for alloc in top_by_count:
                if not isinstance(alloc, dict):
                    continue
                finding = self._normalise_count_allocator(alloc)
                if finding:
                    findings.append(finding)

        return findings

    def _normalise_size_allocator(
        self, alloc: dict[str, Any], total_mb: float
    ) -> Finding | None:
        """Convert a top-by-size allocator entry to a Finding."""
        filepath = alloc.get("file", "<unknown>")
        line = alloc.get("line")
        function = alloc.get("function", "<unknown>")
        size_mb = _safe_float(alloc.get("size_mb", 0))
        pct = _safe_float(alloc.get("percent", 0))

        if size_mb < ALLOC_MEDIUM_THRESHOLD and pct < PCT_MEDIUM_THRESHOLD:
            return None

        severity = _classify_severity_by_size(size_mb, pct)

        return Finding(
            tool="memray",
            severity=severity,
            category=Category.RUNTIME,
            file=filepath,
            rule_id="memray/allocation-hotspot",
            rule_name="Memory allocation hotspot",
            message=(
                f"'{function}' allocates {size_mb:.1f} MB "
                f"({pct:.1f}% of total allocations). "
                "This is a major source of memory pressure."
            ),
            line=line,
            fix_hint=_size_fix_hint(function, size_mb),
            metric="allocation_mb",
            current_value=round(size_mb, 1),
            target_value=ALLOC_MEDIUM_THRESHOLD,
            saving_estimate=f"Optimising '{function}' could reduce memory by ~{size_mb:.0f} MB",
            effort=Effort.HIGH if size_mb >= ALLOC_HIGH_THRESHOLD else Effort.MEDIUM,
            raw=alloc,
        )

    def _normalise_count_allocator(self, alloc: dict[str, Any]) -> Finding | None:
        """Convert a top-by-count allocator entry to a Finding."""
        filepath = alloc.get("file", "<unknown>")
        line = alloc.get("line")
        function = alloc.get("function", "<unknown>")
        count = alloc.get("count", 0)
        pct = _safe_float(alloc.get("percent", 0))

        if pct < PCT_MEDIUM_THRESHOLD:
            return None

        severity = Severity.HIGH if pct >= PCT_HIGH_THRESHOLD else Severity.MEDIUM

        return Finding(
            tool="memray",
            severity=severity,
            category=Category.RUNTIME,
            file=filepath,
            rule_id="memray/allocation-count",
            rule_name="High allocation count",
            message=(
                f"'{function}' performs {count:,} allocations "
                f"({pct:.1f}% of total). High allocation rates cause GC pressure."
            ),
            line=line,
            fix_hint=_count_fix_hint(function, count),
            metric="allocation_count",
            current_value=float(count),
            effort=Effort.MEDIUM,
            raw=alloc,
        )


def _classify_severity_by_size(size_mb: float, pct: float) -> Severity:
    """Classify severity based on allocation size and percentage."""
    if size_mb >= ALLOC_HIGH_THRESHOLD or pct >= PCT_HIGH_THRESHOLD:
        return Severity.HIGH
    if size_mb >= ALLOC_MEDIUM_THRESHOLD or pct >= PCT_MEDIUM_THRESHOLD:
        return Severity.MEDIUM
    return Severity.LOW


def _peak_memory_hint(peak_mb: float) -> str:
    """Generate a fix hint for high peak memory."""
    if peak_mb >= PEAK_MEMORY_CRITICAL_MB:
        return (
            f"Peak memory is {peak_mb:.0f} MB — risk of OOM in containers. "
            "Strategies: stream data instead of loading into memory, use generators "
            "and itertools, process in chunks, use memory-mapped files (mmap) for "
            "large datasets, or switch to numpy/polars for tabular data."
        )
    return (
        f"Peak memory is {peak_mb:.0f} MB. Consider: lazy loading, generators "
        "instead of lists, __slots__ on data classes, and releasing references "
        "to large objects when no longer needed (del + gc.collect)."
    )


def _size_fix_hint(function: str, size_mb: float) -> str:
    """Generate a fix hint for size-based allocation hotspots."""
    if size_mb >= 100:
        return (
            f"'{function}' allocates {size_mb:.0f} MB. Use streaming/chunked processing, "
            "memory-mapped files, or generators to avoid loading all data at once. "
            "For DataFrames, use polars (lazy) or pandas with chunked reading."
        )
    if size_mb >= ALLOC_HIGH_THRESHOLD:
        return (
            f"'{function}' allocates {size_mb:.0f} MB. Check for: large list/dict "
            "comprehensions that could be generators, unnecessary data copies (use "
            "views/slices), or intermediate collections that could be streamed."
        )
    return (
        f"'{function}' allocates {size_mb:.0f} MB. Consider reusing buffers, "
        "using __slots__ on frequently-created objects, or replacing lists with "
        "arrays (array module or numpy) for homogeneous numeric data."
    )


def _count_fix_hint(function: str, count: int) -> str:
    """Generate a fix hint for high allocation count."""
    if count >= 100_000:
        return (
            f"'{function}' makes {count:,} allocations, creating heavy GC pressure. "
            "Use object pooling, pre-allocate arrays/buffers, avoid creating temporary "
            "objects in tight loops, and prefer in-place operations."
        )
    return (
        f"'{function}' makes {count:,} allocations. Reduce by: reusing objects, "
        "using __slots__, converting inner-loop string concatenation to join(), "
        "and pre-sizing lists with [None] * n."
    )


def _safe_float(value: Any) -> float:
    """Safely convert a value to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
