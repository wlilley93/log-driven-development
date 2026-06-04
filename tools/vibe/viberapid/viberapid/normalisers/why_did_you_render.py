"""Normaliser for why-did-you-render (WDYR) output."""

from __future__ import annotations

from collections import Counter
from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser

# Thresholds for aggregated re-render counts
RERENDER_HIGH_THRESHOLD = 10
RERENDER_MEDIUM_THRESHOLD = 3


class WhyDidYouRenderNormaliser(BaseNormaliser):
    """Convert why-did-you-render log entries to Finding objects.

    WDYR provides detailed per-render logging. We aggregate by component to
    produce actionable findings rather than one-per-render-event noise.

    Expected data shape:
    {
      "entries": [
        {
          "component": "Dashboard",
          "file": "src/components/Dashboard.tsx",
          "reason": "props changed",
          "changed_props": ["onClick", "items"],
          "details": [...]
        }
      ]
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        entries = raw_data.get("entries", [])
        if not isinstance(entries, list):
            return []

        # Aggregate entries by component
        component_data: dict[str, _ComponentAggr] = {}

        for entry in entries:
            if not isinstance(entry, dict):
                continue

            name = entry.get("component", "<Unknown>")
            filepath = entry.get("file", "<unknown>")
            reason = entry.get("reason", "unknown")
            changed_props = entry.get("changed_props", [])

            key = f"{filepath}:{name}"
            if key not in component_data:
                component_data[key] = _ComponentAggr(
                    name=name, filepath=filepath
                )

            aggr = component_data[key]
            aggr.rerender_count += 1
            aggr.reasons.append(reason)
            if isinstance(changed_props, list):
                aggr.all_changed_props.extend(str(p) for p in changed_props)

        # Generate findings from aggregated data
        findings: list[Finding] = []

        for aggr in component_data.values():
            finding = self._normalise_aggregated(aggr)
            if finding:
                findings.append(finding)

        return findings

    def _normalise_aggregated(self, aggr: _ComponentAggr) -> Finding | None:
        """Convert aggregated component data to a Finding."""
        if aggr.rerender_count < RERENDER_MEDIUM_THRESHOLD:
            return None

        severity = _classify_severity(aggr.rerender_count)
        primary_reason = _primary_reason(aggr.reasons)
        top_props = _top_props(aggr.all_changed_props, limit=5)
        effort = _classify_effort(primary_reason, top_props)

        props_str = ", ".join(top_props) if top_props else "N/A"
        reasons_summary = _reasons_summary(aggr.reasons)

        return Finding(
            tool="why-did-you-render",
            severity=severity,
            category=Category.RENDER,
            file=aggr.filepath,
            rule_id=f"wdyr/{_reason_to_rule_suffix(primary_reason)}",
            rule_name=f"Avoidable re-render ({primary_reason})",
            message=(
                f"'{aggr.name}' re-rendered {aggr.rerender_count} times unnecessarily. "
                f"Primary cause: {primary_reason}. "
                f"Frequently changing props: {props_str}. "
                f"Breakdown: {reasons_summary}."
            ),
            fix_hint=_build_fix_hint(aggr.name, primary_reason, top_props, aggr.rerender_count),
            metric="unnecessary_renders",
            current_value=float(aggr.rerender_count),
            target_value=0,
            saving_estimate=(
                f"Fixing '{aggr.name}' avoids {aggr.rerender_count} unnecessary re-renders "
                "per interaction cycle"
            ),
            effort=effort,
            raw={
                "component": aggr.name,
                "file": aggr.filepath,
                "rerender_count": aggr.rerender_count,
                "primary_reason": primary_reason,
                "top_changed_props": top_props,
                "reasons_breakdown": dict(Counter(aggr.reasons)),
            },
        )


class _ComponentAggr:
    """Aggregator for per-component WDYR entries."""

    __slots__ = ("name", "filepath", "rerender_count", "reasons", "all_changed_props")

    def __init__(self, name: str, filepath: str):
        self.name = name
        self.filepath = filepath
        self.rerender_count = 0
        self.reasons: list[str] = []
        self.all_changed_props: list[str] = []


def _primary_reason(reasons: list[str]) -> str:
    """Determine the most common re-render reason."""
    if not reasons:
        return "unknown"
    counter = Counter(reasons)
    return counter.most_common(1)[0][0]


def _top_props(props: list[str], limit: int = 5) -> list[str]:
    """Return the most frequently changing props."""
    if not props:
        return []
    counter = Counter(props)
    return [prop for prop, _ in counter.most_common(limit)]


def _reasons_summary(reasons: list[str]) -> str:
    """Create a summary string of reason counts."""
    counter = Counter(reasons)
    parts = [f"{reason}: {count}" for reason, count in counter.most_common()]
    return ", ".join(parts) if parts else "unknown"


def _reason_to_rule_suffix(reason: str) -> str:
    """Convert a reason string to a rule ID suffix."""
    return reason.lower().replace(" ", "-").replace("_", "-")


def _classify_severity(count: int) -> Severity:
    """Classify severity based on re-render count."""
    if count >= RERENDER_HIGH_THRESHOLD:
        return Severity.HIGH
    if count >= RERENDER_MEDIUM_THRESHOLD:
        return Severity.MEDIUM
    return Severity.LOW


def _classify_effort(reason: str, props: list[str]) -> Effort:
    """Estimate effort based on the re-render reason."""
    reason_lower = reason.lower()

    # Props changes are usually fixable with React.memo + useMemo/useCallback
    if "props" in reason_lower:
        # If the changing prop is a callback, it's likely an easy useCallback fix
        callback_indicators = ("on", "handle", "click", "change", "submit", "callback")
        if any(p.lower().startswith(ind) for p in props for ind in callback_indicators):
            return Effort.LOW
        return Effort.LOW

    # State changes in the same component need logic restructuring
    if "state" in reason_lower:
        return Effort.MEDIUM

    # Hooks changes can be complex
    if "hook" in reason_lower:
        return Effort.MEDIUM

    # Context changes often need architectural refactoring
    if "context" in reason_lower:
        return Effort.HIGH

    return Effort.MEDIUM


def _build_fix_hint(
    name: str, reason: str, props: list[str], count: int
) -> str:
    """Generate a targeted fix hint based on the re-render cause."""
    reason_lower = reason.lower()

    if "props" in reason_lower and props:
        prop_list = ", ".join(f"'{p}'" for p in props[:3])
        callback_props = [
            p for p in props
            if any(p.lower().startswith(x) for x in ("on", "handle", "click", "change"))
        ]
        if callback_props:
            cb_list = ", ".join(f"'{p}'" for p in callback_props)
            return (
                f"'{name}' re-renders {count} times due to changing props ({prop_list}). "
                f"The callback props ({cb_list}) are likely recreated each render. "
                f"Fix: (1) wrap '{name}' with React.memo(), (2) wrap callbacks with "
                "useCallback() in the parent, (3) if passing objects/arrays, wrap "
                "with useMemo(). WDYR confirms these are semantically equal — only "
                "referential identity changes."
            )
        return (
            f"'{name}' re-renders {count} times due to prop changes ({prop_list}). "
            f"Fix: (1) wrap '{name}' with React.memo() to skip renders when props "
            "are shallowly equal, (2) ensure parent memoises object/array props "
            "with useMemo(), (3) if deep equality is needed, pass a custom "
            "areEqual function to React.memo()."
        )

    if "state" in reason_lower:
        return (
            f"'{name}' re-renders {count} times due to state changes. WDYR flagged "
            "these as avoidable, meaning the state updates produce the same value. "
            "Fix: add a guard (if (prev === next) return) in your setState updater, "
            "use useReducer with a comparison check, or restructure state to avoid "
            "unnecessary updates (derived state should use useMemo, not useState)."
        )

    if "hook" in reason_lower:
        return (
            f"'{name}' re-renders {count} times due to hook return value changes. "
            "A custom hook is returning new references each render. Fix: ensure "
            "hooks memoize their return values with useMemo/useCallback, or use "
            "useRef for values that don't need to trigger re-renders."
        )

    if "context" in reason_lower:
        return (
            f"'{name}' re-renders {count} times due to context changes. "
            "Fixes: (1) split context into smaller, focused contexts, (2) use "
            "a context selector library (use-context-selector), (3) memoize the "
            "context value object in the provider, (4) move context consumption "
            "to a wrapper component and pass only needed data as props."
        )

    return (
        f"'{name}' has {count} avoidable re-renders. Apply: React.memo() on "
        "the component, useMemo()/useCallback() for values and handlers passed "
        "as props, and ensure parent components don't trigger cascading re-renders."
    )
