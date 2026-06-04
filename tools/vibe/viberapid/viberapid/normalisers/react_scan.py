"""Normaliser for react-scan output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser

# Thresholds for unnecessary re-render severity
RERENDER_HIGH_THRESHOLD = 10
RERENDER_MEDIUM_THRESHOLD = 3

# Ratio of unnecessary to total renders
RATIO_HIGH_THRESHOLD = 0.7
RATIO_MEDIUM_THRESHOLD = 0.4


class ReactScanNormaliser(BaseNormaliser):
    """Convert react-scan output to Finding objects.

    react-scan detects unnecessary re-renders at runtime by instrumenting React's
    reconciler. Each component is tracked with render counts and reasons.

    Expected data shape:
    {
      "components": [
        {
          "component": "Dashboard",
          "file": "src/components/Dashboard.tsx",
          "render_count": 12,
          "unnecessary_count": 8,
          "reasons": ["props changed (onClick)", "context changed"]
        }
      ]
    }

    Or alternative key names:
    {
      "results": [
        {
          "name": "Dashboard",
          "filePath": "src/components/Dashboard.tsx",
          "renderCount": 12,
          "unnecessaryRenders": 8,
          "triggers": [...]
        }
      ]
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        # Support both key naming conventions
        components = raw_data.get("components", raw_data.get("results", []))
        if not isinstance(components, list):
            return []

        findings: list[Finding] = []

        for comp in components:
            if not isinstance(comp, dict):
                continue

            finding = self._normalise_component(comp)
            if finding:
                findings.append(finding)

        return findings

    def _normalise_component(self, comp: dict[str, Any]) -> Finding | None:
        """Convert a single component entry to a Finding."""
        # Normalise key names
        name = comp.get("component", comp.get("name", "<Unknown>"))
        filepath = comp.get("file", comp.get("filePath", "<unknown>"))
        render_count = comp.get("render_count", comp.get("renderCount", 0))
        unnecessary = comp.get("unnecessary_count", comp.get("unnecessaryRenders", 0))
        reasons = comp.get("reasons", comp.get("triggers", []))

        if not isinstance(reasons, list):
            reasons = [str(reasons)] if reasons else []

        if unnecessary < RERENDER_MEDIUM_THRESHOLD:
            return None

        ratio = unnecessary / render_count if render_count > 0 else 0
        severity = self._classify_severity(unnecessary, ratio)
        effort = self._classify_effort(reasons)
        rule_id, rule_name = self._classify_rule(reasons)

        reasons_str = ", ".join(str(r) for r in reasons[:3]) if reasons else "unknown"
        ratio_pct = ratio * 100

        return Finding(
            tool="react-scan",
            severity=severity,
            category=Category.RENDER,
            file=filepath,
            rule_id=rule_id,
            rule_name=rule_name,
            message=(
                f"'{name}' has {unnecessary} unnecessary re-renders out of "
                f"{render_count} total ({ratio_pct:.0f}% wasted). "
                f"Triggers: {reasons_str}."
            ),
            fix_hint=self._build_fix_hint(name, reasons, unnecessary, ratio),
            metric="unnecessary_renders",
            current_value=float(unnecessary),
            target_value=0,
            saving_estimate=(
                f"Eliminating {unnecessary} unnecessary renders of '{name}' "
                f"saves {ratio_pct:.0f}% of its render cycles"
            ),
            effort=effort,
            raw=comp,
        )

    def _classify_severity(self, unnecessary: int, ratio: float) -> Severity:
        """Classify severity based on re-render count and ratio."""
        if unnecessary >= RERENDER_HIGH_THRESHOLD and ratio >= RATIO_HIGH_THRESHOLD:
            return Severity.HIGH
        if unnecessary >= RERENDER_HIGH_THRESHOLD or ratio >= RATIO_HIGH_THRESHOLD:
            return Severity.MEDIUM
        if unnecessary >= RERENDER_MEDIUM_THRESHOLD:
            return Severity.MEDIUM
        return Severity.LOW

    def _classify_rule(self, reasons: list) -> tuple[str, str]:
        """Classify into a specific rule based on re-render reasons."""
        reasons_lower = " ".join(str(r).lower() for r in reasons)

        if "context" in reasons_lower:
            return "react-scan/context-rerender", "Context-triggered re-render"
        if "props" in reasons_lower and ("inline" in reasons_lower or "new" in reasons_lower):
            return "react-scan/inline-prop", "Inline prop causing re-render"
        if "props" in reasons_lower:
            return "react-scan/prop-change", "Prop change re-render"
        if "state" in reasons_lower and "parent" in reasons_lower:
            return "react-scan/parent-state", "Parent state re-render"
        if "hook" in reasons_lower:
            return "react-scan/hook-rerender", "Hook-triggered re-render"

        return "react-scan/unnecessary-rerender", "Unnecessary re-render"

    def _classify_effort(self, reasons: list) -> Effort:
        """Estimate effort based on the re-render trigger."""
        reasons_lower = " ".join(str(r).lower() for r in reasons)

        # Inline props are easy to fix (extract to useMemo/useCallback)
        if "inline" in reasons_lower:
            return Effort.LOW

        # Context re-renders often need architectural changes
        if "context" in reasons_lower:
            return Effort.HIGH

        # Prop changes usually fixable with React.memo
        if "props" in reasons_lower:
            return Effort.LOW

        return Effort.MEDIUM

    def _build_fix_hint(
        self, name: str, reasons: list, unnecessary: int, ratio: float
    ) -> str:
        """Generate a targeted fix hint based on the re-render cause."""
        reasons_lower = " ".join(str(r).lower() for r in reasons)

        if "context" in reasons_lower:
            return (
                f"'{name}' re-renders {unnecessary} times due to context changes. "
                "Fixes: (1) split context into smaller pieces so components subscribe "
                "only to needed values, (2) use a context selector library "
                "(use-context-selector), (3) move the context consumer into a child "
                "component wrapped with React.memo, or (4) consider Zustand/Jotai "
                "for fine-grained subscriptions."
            )

        if "inline" in reasons_lower:
            return (
                f"'{name}' re-renders due to inline objects/functions in JSX. "
                "Fix: extract inline objects to useMemo(), inline functions to "
                "useCallback(), and inline arrays to constants defined outside the "
                "component or memoised with useMemo(). This is usually a quick fix."
            )

        if "props" in reasons_lower:
            return (
                f"'{name}' re-renders {unnecessary} times due to prop changes. "
                "Fix: wrap with React.memo() to skip re-renders when props haven't "
                "changed. If props contain objects/arrays, ensure the parent memoises "
                "them with useMemo()/useCallback(). For deeply nested objects, "
                "consider passing primitive props or using a selector pattern."
            )

        if "parent" in reasons_lower or "state" in reasons_lower:
            return (
                f"'{name}' re-renders when parent state changes. Wrap with "
                "React.memo() to skip unnecessary renders. Also check if the parent "
                "is setting state too broadly — consider splitting state or moving "
                "it closer to where it's used (component composition)."
            )

        return (
            f"'{name}' has {unnecessary} unnecessary re-renders "
            f"({ratio * 100:.0f}% wasted). General fixes: "
            "React.memo() on the component, useMemo() for computed values, "
            "useCallback() for event handlers, and avoid inline object/array "
            "creation in JSX."
        )
