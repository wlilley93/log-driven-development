"""Normaliser for Fil (fil-profile) output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser

# Size thresholds for peak allocation severity (MB)
PEAK_CRITICAL_MB = 256.0
PEAK_HIGH_MB = 64.0
PEAK_MEDIUM_MB = 16.0

# Individual allocation thresholds (MB)
ALLOC_HIGH_MB = 50.0
ALLOC_MEDIUM_MB = 10.0


class FilNormaliser(BaseNormaliser):
    """Convert Fil output to Finding objects.

    Fil focuses on peak memory — the single moment when the most memory is in use.
    This is unlike continuous profilers (memray, scalene) that track allocations
    over time.

    Expected data shape:
    {
      "peak_memory_mb": 128.5,           # optional — overall peak
      "peak_allocations": [
        {
          "function": "load_data",
          "file": "data_loader.py",
          "line": 42,
          "size_mb": 64.2
        }
      ]
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        findings: list[Finding] = []

        peak_memory_mb = _safe_float(raw_data.get("peak_memory_mb", 0))

        # Overall peak memory finding
        if peak_memory_mb >= PEAK_MEDIUM_MB:
            severity = _classify_peak_severity(peak_memory_mb)
            findings.append(Finding(
                tool="fil",
                severity=severity,
                category=Category.RUNTIME,
                file="<process>",
                rule_id="fil/peak-memory",
                rule_name="Peak memory usage",
                message=(
                    f"Peak memory usage: {peak_memory_mb:.1f} MB. "
                    "This is the maximum resident memory at any single point during execution."
                ),
                fix_hint=_peak_hint(peak_memory_mb),
                metric="peak_memory_mb",
                current_value=round(peak_memory_mb, 1),
                target_value=PEAK_HIGH_MB,
                saving_estimate=(
                    f"Reducing peak memory could save ~{peak_memory_mb - PEAK_HIGH_MB:.0f} MB"
                    if peak_memory_mb > PEAK_HIGH_MB else None
                ),
                effort=Effort.HIGH,
                raw={"peak_memory_mb": round(peak_memory_mb, 2)},
            ))

        # Individual peak allocation hotspots
        allocations = raw_data.get("peak_allocations", [])
        if isinstance(allocations, list):
            for alloc in allocations:
                if not isinstance(alloc, dict):
                    continue
                finding = self._normalise_allocation(alloc)
                if finding:
                    findings.append(finding)

        return findings

    def _normalise_allocation(self, alloc: dict[str, Any]) -> Finding | None:
        """Convert a single peak allocation entry to a Finding."""
        function = alloc.get("function", "<unknown>")
        filepath = alloc.get("file", "<unknown>")
        line = alloc.get("line")
        size_mb = _safe_float(alloc.get("size_mb", 0))

        if size_mb < ALLOC_MEDIUM_MB:
            return None

        severity = (
            Severity.HIGH if size_mb >= ALLOC_HIGH_MB
            else Severity.MEDIUM
        )
        effort = Effort.HIGH if size_mb >= ALLOC_HIGH_MB else Effort.MEDIUM

        return Finding(
            tool="fil",
            severity=severity,
            category=Category.RUNTIME,
            file=filepath,
            rule_id="fil/peak-allocation",
            rule_name="Peak allocation contributor",
            message=(
                f"'{function}' contributes {size_mb:.1f} MB to peak memory. "
                "This allocation was live at the moment of highest memory usage."
            ),
            line=line,
            fix_hint=_alloc_hint(function, size_mb),
            metric="peak_allocation_mb",
            current_value=round(size_mb, 1),
            target_value=ALLOC_MEDIUM_MB,
            saving_estimate=f"Freeing '{function}' allocation could reduce peak by ~{size_mb:.0f} MB",
            effort=effort,
            raw=alloc,
        )


def _classify_peak_severity(peak_mb: float) -> Severity:
    """Classify severity based on peak memory."""
    if peak_mb >= PEAK_CRITICAL_MB:
        return Severity.CRITICAL
    if peak_mb >= PEAK_HIGH_MB:
        return Severity.HIGH
    return Severity.MEDIUM


def _peak_hint(peak_mb: float) -> str:
    """Generate a fix hint for overall peak memory."""
    if peak_mb >= PEAK_CRITICAL_MB:
        return (
            f"Peak memory is {peak_mb:.0f} MB — likely to cause OOM in constrained "
            "environments. The peak is usually caused by a single operation loading too "
            "much data at once. Use Fil's flamegraph to identify the exact call stack, "
            "then switch to streaming/chunked processing, generators, or memory-mapped files."
        )
    if peak_mb >= PEAK_HIGH_MB:
        return (
            f"Peak memory is {peak_mb:.0f} MB. Identify the peak call stack in Fil's "
            "flamegraph output. Common fixes: process data in batches, use generators "
            "instead of lists, free large objects before allocating new ones, and "
            "avoid loading entire files into memory."
        )
    return (
        f"Peak memory is {peak_mb:.0f} MB. Review the peak allocation point for "
        "opportunities to reduce memory: lazy loading, smaller batch sizes, or "
        "releasing references to large objects sooner."
    )


def _alloc_hint(function: str, size_mb: float) -> str:
    """Generate a fix hint for a specific peak allocation."""
    if size_mb >= 100:
        return (
            f"'{function}' holds {size_mb:.0f} MB at peak. This single allocation "
            "dominates memory usage. Strategies: stream/chunk the data, use memory-mapped "
            "files (mmap), process and discard incrementally, or use a disk-backed "
            "structure (SQLite, shelve) instead of in-memory collections."
        )
    if size_mb >= ALLOC_HIGH_MB:
        return (
            f"'{function}' holds {size_mb:.0f} MB at peak. Consider: releasing the data "
            "before the next large allocation (del + gc.collect), using views/slices "
            "instead of copies, or lazy-loading only the needed subset."
        )
    return (
        f"'{function}' holds {size_mb:.0f} MB at peak. Check if this data can be "
        "loaded lazily, freed earlier, or represented more compactly (e.g., numpy "
        "arrays instead of lists of floats, __slots__ on objects)."
    )


def _safe_float(value: Any) -> float:
    """Safely convert a value to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
