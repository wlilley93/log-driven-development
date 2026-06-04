"""Normaliser for node --prof tick processor output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser

# Percentage thresholds
TICK_HIGH_THRESHOLD = 15.0
TICK_MEDIUM_THRESHOLD = 5.0
TICK_LOW_THRESHOLD = 2.0

# GC percentage threshold for a finding
GC_WARNING_THRESHOLD = 10.0
GC_HIGH_THRESHOLD = 25.0


class NodeProfNormaliser(BaseNormaliser):
    """Convert node --prof-process output to Finding objects.

    Expected data shape (from NodeProfRunner._parse_text_output):
    {
      "summary": {
        "JavaScript": {"ticks": 1234, "total_percent": 45.6},
        "C++": {"ticks": 567, "total_percent": 21.0},
        "GC": {"ticks": 123, "total_percent": 4.6},
        ...
      },
      "sections": {
        "JavaScript": [
          {
            "function": "processData",
            "file": "server.js",
            "line": 42,
            "ticks": 456,
            "total_percent": 16.9,
            "nonlib_percent": 18.8,
            "section": "JavaScript"
          }
        ],
        "C++": [...]
      }
    }

    Or --preprocess JSON (V8 internal format):
    {
      "code": [...],
      "ticks": [...],
      ...
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        findings: list[Finding] = []

        # Process summary for high-level insights
        summary = raw_data.get("summary", {})
        if isinstance(summary, dict):
            findings.extend(self._normalise_summary(summary))

        # Process individual function hotspots
        sections = raw_data.get("sections", {})
        if isinstance(sections, dict):
            for section_name, entries in sections.items():
                if not isinstance(entries, list):
                    continue
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    finding = self._normalise_function(entry)
                    if finding:
                        findings.append(finding)

        return findings

    def _normalise_summary(self, summary: dict[str, Any]) -> list[Finding]:
        """Generate findings from the profiler summary section."""
        findings: list[Finding] = []

        # Check GC pressure
        gc_data = summary.get("GC", {})
        if isinstance(gc_data, dict):
            gc_pct = _safe_float(gc_data.get("total_percent", 0))
            if gc_pct >= GC_WARNING_THRESHOLD:
                severity = Severity.HIGH if gc_pct >= GC_HIGH_THRESHOLD else Severity.MEDIUM
                findings.append(Finding(
                    tool="node-prof",
                    severity=severity,
                    category=Category.RUNTIME,
                    file="<process>",
                    rule_id="node-prof/gc-pressure",
                    rule_name="GC pressure",
                    message=(
                        f"Garbage collection uses {gc_pct:.1f}% of total CPU ticks. "
                        "High GC pressure degrades latency and throughput."
                    ),
                    fix_hint=_gc_fix_hint(gc_pct),
                    metric="gc_percent",
                    current_value=round(gc_pct, 1),
                    target_value=GC_WARNING_THRESHOLD,
                    saving_estimate=f"Reducing GC could reclaim ~{gc_pct:.0f}% CPU time",
                    effort=Effort.HIGH,
                    raw={"gc_summary": gc_data},
                ))

        # Check C++ dominance (may indicate native binding bottleneck)
        cpp_data = summary.get("C++", {})
        if isinstance(cpp_data, dict):
            cpp_pct = _safe_float(cpp_data.get("total_percent", 0))
            if cpp_pct >= 50:
                findings.append(Finding(
                    tool="node-prof",
                    severity=Severity.MEDIUM,
                    category=Category.RUNTIME,
                    file="<process>",
                    rule_id="node-prof/cpp-dominance",
                    rule_name="C++ code dominance",
                    message=(
                        f"C++ code uses {cpp_pct:.1f}% of CPU ticks. Most time is spent "
                        "in native bindings or V8 internals rather than JavaScript."
                    ),
                    fix_hint=(
                        "High C++ time usually means: (1) native addon bottleneck — check "
                        "if a JS-native alternative exists, (2) heavy regex or JSON parsing — "
                        "use streaming alternatives, or (3) crypto operations — use async "
                        "variants (crypto.subtle). Review the C++ section for specific functions."
                    ),
                    metric="cpp_percent",
                    current_value=round(cpp_pct, 1),
                    effort=Effort.HIGH,
                    raw={"cpp_summary": cpp_data},
                ))

        return findings

    def _normalise_function(self, entry: dict[str, Any]) -> Finding | None:
        """Convert a single function entry to a Finding."""
        function = entry.get("function", "<unknown>")
        filepath = entry.get("file", "<unknown>")
        line = entry.get("line")
        total_pct = _safe_float(entry.get("total_percent", 0))
        ticks = entry.get("ticks", 0)
        section = entry.get("section", "JavaScript")

        if total_pct < TICK_LOW_THRESHOLD:
            return None

        # Skip internal V8 functions
        if _is_internal_function(function, filepath):
            return None

        severity = _classify_severity(total_pct)
        effort = Effort.HIGH if total_pct >= TICK_HIGH_THRESHOLD else Effort.MEDIUM

        section_label = "JavaScript" if section == "JavaScript" else "native"

        return Finding(
            tool="node-prof",
            severity=severity,
            category=Category.RUNTIME,
            file=filepath,
            rule_id=f"node-prof/{section.lower()}-hotspot",
            rule_name=f"CPU hotspot ({section_label})",
            message=(
                f"'{function}' uses {total_pct:.1f}% of CPU ticks "
                f"({ticks:,} ticks) in the {section_label} layer."
            ),
            line=line,
            fix_hint=_function_fix_hint(function, total_pct, section),
            metric="tick_percent",
            current_value=round(total_pct, 1),
            target_value=TICK_MEDIUM_THRESHOLD,
            saving_estimate=f"Optimising '{function}' could reclaim ~{total_pct:.0f}% CPU",
            effort=effort,
            raw=entry,
        )


def _is_internal_function(function: str, filepath: str) -> bool:
    """Return True for V8/Node.js internal functions."""
    internal_names = (
        "Builtin:", "Runtime_", "Stub:", "BytecodeHandler:",
        "LoadIC:", "StoreIC:", "KeyedLoadIC:",
    )
    internal_paths = (
        "node_modules/", "node:internal", "/internal/",
        "v8/", "deps/",
    )
    return (
        any(function.startswith(n) for n in internal_names)
        or any(m in filepath for m in internal_paths)
    )


def _classify_severity(pct: float) -> Severity:
    """Classify severity based on tick percentage."""
    if pct >= TICK_HIGH_THRESHOLD:
        return Severity.HIGH
    if pct >= TICK_MEDIUM_THRESHOLD:
        return Severity.MEDIUM
    return Severity.LOW


def _gc_fix_hint(gc_pct: float) -> str:
    """Generate a fix hint for GC pressure."""
    if gc_pct >= GC_HIGH_THRESHOLD:
        return (
            f"GC uses {gc_pct:.0f}% CPU — severe allocation pressure. "
            "Immediate actions: use object pooling for hot-path objects, "
            "pre-allocate Buffers, avoid closures in loops, replace "
            "JSON.parse/stringify with streaming alternatives on large payloads, "
            "and tune --max-old-space-size and --max-semi-space-size."
        )
    return (
        f"GC uses {gc_pct:.0f}% CPU. Reduce allocations: reuse objects/buffers, "
        "avoid creating temporary objects in request handlers, use typed arrays "
        "for numeric data, and consider --expose-gc with strategic gc() calls."
    )


def _function_fix_hint(function: str, pct: float, section: str) -> str:
    """Generate a fix hint for a function hotspot."""
    if section != "JavaScript":
        return (
            f"'{function}' spends {pct:.0f}% in native code. If this is a native "
            "addon, check for a pure-JS or WASM alternative. For V8 builtins, "
            "review the calling JavaScript code for patterns that cause deoptimisation "
            "(hidden class changes, megamorphic calls)."
        )

    if pct >= 30:
        return (
            f"'{function}' dominates JavaScript CPU ({pct:.0f}%). This is the primary "
            "optimisation target. Consider: worker_threads for parallel execution, "
            "caching with LRU, algorithmic improvements, and using V8's optimisation "
            "hints (monomorphic calls, avoid try-catch in hot functions)."
        )
    if pct >= TICK_HIGH_THRESHOLD:
        return (
            f"'{function}' is a major JS hotspot ({pct:.0f}%). Strategies: memoise "
            "expensive computations, move heavy work off the event loop (worker_threads, "
            "setImmediate for chunking), and ensure V8 can optimise the function "
            "(avoid arguments object, avoid changing object shapes)."
        )
    return (
        f"'{function}' uses {pct:.0f}% CPU. Review for: unnecessary object creation, "
        "repeated string concatenation (use array.join), or patterns that prevent "
        "V8 optimisation (eval, with, delete)."
    )


def _safe_float(value: Any) -> float:
    """Safely convert a value to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
