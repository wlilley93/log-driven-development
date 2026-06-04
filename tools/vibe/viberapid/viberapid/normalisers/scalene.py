"""Normaliser for scalene output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser

# CPU threshold percentages for severity classification
CPU_HIGH_THRESHOLD = 20.0
CPU_MEDIUM_THRESHOLD = 10.0

# Memory threshold percentages for severity classification
MEMORY_HIGH_THRESHOLD = 20.0
MEMORY_MEDIUM_THRESHOLD = 10.0


class ScaleneNormaliser(BaseNormaliser):
    """Convert scalene JSON output to Finding objects.

    scalene JSON shape:
    {
      "elapsed_time_sec": 12.5,
      "files": {
        "/path/to/file.py": {
          "lines": [
            {
              "lineno": 42,
              "function": "process_data",
              "n_cpu_percent_python": 35.2,
              "n_cpu_percent_c": 5.0,
              "n_sys_percent": 1.2,
              "n_malloc_mb": 128.5,
              "n_python_fraction": 0.8,
              "line": "    result = [transform(x) for x in data]"
            }
          ]
        }
      }
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        findings: list[Finding] = []
        files = raw_data.get("files", {})
        elapsed = raw_data.get("elapsed_time_sec", 0)

        if not isinstance(files, dict):
            return []

        for filepath, file_data in files.items():
            if not isinstance(file_data, dict):
                continue

            lines = file_data.get("lines", [])
            if not isinstance(lines, list):
                continue

            # Aggregate CPU by function for a clearer picture
            function_cpu: dict[str, _FunctionStats] = {}

            for line_data in lines:
                if not isinstance(line_data, dict):
                    continue

                function_name = line_data.get("function", "<module>")
                cpu_python = _safe_float(line_data.get("n_cpu_percent_python", 0))
                cpu_c = _safe_float(line_data.get("n_cpu_percent_c", 0))
                cpu_sys = _safe_float(line_data.get("n_sys_percent", 0))
                total_cpu = cpu_python + cpu_c + cpu_sys
                malloc_mb = _safe_float(line_data.get("n_malloc_mb", 0))
                lineno = line_data.get("lineno")
                source_line = line_data.get("line", "").strip()

                if total_cpu < 1.0 and malloc_mb < 1.0:
                    continue

                key = f"{filepath}:{function_name}"
                if key not in function_cpu:
                    function_cpu[key] = _FunctionStats(
                        filepath=filepath,
                        function=function_name,
                    )

                stats = function_cpu[key]
                stats.total_cpu += total_cpu
                stats.total_malloc_mb += malloc_mb
                if total_cpu > stats.peak_cpu:
                    stats.peak_cpu = total_cpu
                    stats.peak_cpu_line = lineno
                    stats.peak_cpu_source = source_line
                if malloc_mb > stats.peak_malloc_mb:
                    stats.peak_malloc_mb = malloc_mb
                    stats.peak_malloc_line = lineno

            # Generate findings from aggregated function stats
            for stats in function_cpu.values():
                # CPU hotspot finding
                if stats.total_cpu >= CPU_MEDIUM_THRESHOLD:
                    severity = (
                        Severity.HIGH if stats.total_cpu >= CPU_HIGH_THRESHOLD
                        else Severity.MEDIUM
                    )
                    findings.append(Finding(
                        tool="scalene",
                        severity=severity,
                        category=Category.RUNTIME,
                        file=stats.filepath,
                        rule_id="scalene/cpu-hotspot",
                        rule_name="CPU hotspot",
                        message=(
                            f"Function '{stats.function}' uses {stats.total_cpu:.1f}% CPU time. "
                            f"Peak line: {stats.peak_cpu_source or '(unknown)'}"
                        ),
                        line=stats.peak_cpu_line,
                        fix_hint=_cpu_fix_hint(stats.total_cpu, stats.function),
                        metric="cpu_percent",
                        current_value=round(stats.total_cpu, 1),
                        target_value=CPU_MEDIUM_THRESHOLD,
                        saving_estimate=f"Optimising '{stats.function}' could reclaim ~{stats.total_cpu:.0f}% CPU",
                        effort=Effort.HIGH if stats.total_cpu >= CPU_HIGH_THRESHOLD else Effort.MEDIUM,
                        raw={
                            "function": stats.function,
                            "total_cpu_percent": round(stats.total_cpu, 2),
                            "peak_cpu_line": stats.peak_cpu_line,
                        },
                    ))

                # Memory allocation hotspot finding
                if stats.total_malloc_mb >= MEMORY_MEDIUM_THRESHOLD:
                    severity = (
                        Severity.HIGH if stats.total_malloc_mb >= MEMORY_HIGH_THRESHOLD
                        else Severity.MEDIUM
                    )
                    findings.append(Finding(
                        tool="scalene",
                        severity=severity,
                        category=Category.RUNTIME,
                        file=stats.filepath,
                        rule_id="scalene/memory-hotspot",
                        rule_name="Memory allocation hotspot",
                        message=(
                            f"Function '{stats.function}' allocates {stats.total_malloc_mb:.1f} MB. "
                            f"Peak allocation at line {stats.peak_malloc_line or '(unknown)'}."
                        ),
                        line=stats.peak_malloc_line,
                        fix_hint=_memory_fix_hint(stats.total_malloc_mb, stats.function),
                        metric="malloc_mb",
                        current_value=round(stats.total_malloc_mb, 1),
                        effort=Effort.HIGH if stats.total_malloc_mb >= MEMORY_HIGH_THRESHOLD else Effort.MEDIUM,
                        raw={
                            "function": stats.function,
                            "total_malloc_mb": round(stats.total_malloc_mb, 2),
                            "peak_malloc_line": stats.peak_malloc_line,
                        },
                    ))

        return findings


class _FunctionStats:
    """Accumulator for per-function profiling stats."""

    __slots__ = (
        "filepath", "function", "total_cpu", "peak_cpu", "peak_cpu_line",
        "peak_cpu_source", "total_malloc_mb", "peak_malloc_mb", "peak_malloc_line",
    )

    def __init__(self, filepath: str, function: str):
        self.filepath = filepath
        self.function = function
        self.total_cpu: float = 0.0
        self.peak_cpu: float = 0.0
        self.peak_cpu_line: int | None = None
        self.peak_cpu_source: str = ""
        self.total_malloc_mb: float = 0.0
        self.peak_malloc_mb: float = 0.0
        self.peak_malloc_line: int | None = None


def _safe_float(value: Any) -> float:
    """Safely convert a value to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _cpu_fix_hint(cpu_percent: float, function: str) -> str:
    """Generate a targeted fix hint for CPU hotspots."""
    if cpu_percent >= 50:
        return (
            f"'{function}' dominates CPU usage ({cpu_percent:.0f}%). Consider: "
            "algorithmic optimisation (O(n^2) -> O(n log n)), caching expensive "
            "computations, moving hot loops to C extensions (Cython/numpy), or "
            "parallelising with multiprocessing."
        )
    if cpu_percent >= CPU_HIGH_THRESHOLD:
        return (
            f"'{function}' is a significant CPU consumer ({cpu_percent:.0f}%). "
            "Profile the hot lines, consider list comprehension over loops, "
            "functools.lru_cache for repeated calls, or numpy for numerical work."
        )
    return (
        f"'{function}' uses notable CPU ({cpu_percent:.0f}%). Review the hot "
        "lines for unnecessary recomputation or sub-optimal data structures."
    )


def _memory_fix_hint(malloc_mb: float, function: str) -> str:
    """Generate a targeted fix hint for memory hotspots."""
    if malloc_mb >= 100:
        return (
            f"'{function}' allocates {malloc_mb:.0f} MB. Consider streaming/chunked "
            "processing instead of loading all data into memory, using generators, "
            "or memory-mapped files for large datasets."
        )
    if malloc_mb >= MEMORY_HIGH_THRESHOLD:
        return (
            f"'{function}' allocates {malloc_mb:.0f} MB. Look for unnecessary copies "
            "(e.g., list slicing), prefer in-place operations, use __slots__ on "
            "data classes, or switch to numpy arrays for numerical data."
        )
    return (
        f"'{function}' allocates {malloc_mb:.0f} MB. Check for intermediate list "
        "creation that could be replaced with generators or itertools."
    )
