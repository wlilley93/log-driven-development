"""Normaliser for million-lint output."""

from __future__ import annotations

from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser

# Keywords in messages that indicate specific optimisation opportunities
MEMO_KEYWORDS = ("memo", "memoize", "useMemo", "useCallback", "React.memo")
RERENDER_KEYWORDS = ("re-render", "rerender", "render", "unnecessary render")
BLOCK_KEYWORDS = ("block", "million", "compile", "static")
PROP_KEYWORDS = ("prop", "props", "spreading", "inline")


class MillionLintNormaliser(BaseNormaliser):
    """Convert million-lint output to Finding objects.

    million-lint JSON shape (structured):
    {
      "issues": [
        {
          "file": "src/components/Dashboard.tsx",
          "line": 42,
          "component": "Dashboard",
          "message": "Component re-renders on every parent render. Consider React.memo.",
          "type": "unnecessary-rerender",
          "severity": "medium"
        }
      ]
    }

    Or list format:
    [
      {
        "file": "src/App.tsx",
        "line": 10,
        "message": "..."
      }
    ]
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if isinstance(raw_data, dict):
            issues = raw_data.get("issues", [])
        elif isinstance(raw_data, list):
            issues = raw_data
        else:
            return []

        if not isinstance(issues, list):
            return []

        findings: list[Finding] = []

        for issue in issues:
            if not isinstance(issue, dict):
                continue

            finding = self._normalise_issue(issue)
            if finding:
                findings.append(finding)

        return findings

    def _normalise_issue(self, issue: dict[str, Any]) -> Finding | None:
        """Convert a single million-lint issue to a Finding."""
        filepath = issue.get("file", "<unknown>")
        line = issue.get("line")
        component = issue.get("component", "")
        message = issue.get("message", "React component could be optimised")
        issue_type = issue.get("type", "")
        raw_severity = issue.get("severity", "")

        # Classify based on message content and type
        severity = self._classify_severity(message, issue_type, raw_severity)
        rule_id, rule_name = self._classify_rule(message, issue_type)
        fix_hint = self._build_fix_hint(message, issue_type, component, filepath)
        effort = self._classify_effort(message, issue_type)

        component_prefix = f"Component '{component}': " if component else ""

        return Finding(
            tool="million-lint",
            severity=severity,
            category=Category.RENDER,
            file=filepath,
            rule_id=rule_id,
            rule_name=rule_name,
            message=f"{component_prefix}{message}",
            line=line,
            fix_hint=fix_hint,
            effort=effort,
            raw=issue,
        )

    def _classify_severity(self, message: str, issue_type: str, raw_severity: str) -> Severity:
        """Classify severity based on issue content."""
        # Respect explicit severity from the tool
        severity_map = {
            "critical": Severity.CRITICAL,
            "high": Severity.HIGH,
            "medium": Severity.MEDIUM,
            "low": Severity.LOW,
            "info": Severity.INFO,
        }
        if raw_severity.lower() in severity_map:
            return severity_map[raw_severity.lower()]

        msg_lower = message.lower()
        type_lower = issue_type.lower()

        # Unnecessary re-renders are medium-high impact
        if any(kw in msg_lower or kw in type_lower for kw in RERENDER_KEYWORDS):
            return Severity.MEDIUM

        # Missing memoization
        if any(kw.lower() in msg_lower or kw.lower() in type_lower for kw in MEMO_KEYWORDS):
            return Severity.MEDIUM

        # Block-level optimisations (Million.js specific)
        if any(kw in msg_lower or kw in type_lower for kw in BLOCK_KEYWORDS):
            return Severity.LOW

        return Severity.MEDIUM

    def _classify_rule(self, message: str, issue_type: str) -> tuple[str, str]:
        """Classify the finding into a rule ID and name."""
        msg_lower = message.lower()
        type_lower = issue_type.lower()

        if any(kw in type_lower for kw in ("rerender", "re-render", "unnecessary-render")):
            return "million-lint/unnecessary-rerender", "Unnecessary re-render"

        if any(kw.lower() in msg_lower for kw in MEMO_KEYWORDS):
            return "million-lint/missing-memo", "Missing memoization"

        if any(kw in msg_lower for kw in BLOCK_KEYWORDS):
            return "million-lint/block-candidate", "Million.js block candidate"

        if any(kw in msg_lower for kw in PROP_KEYWORDS):
            return "million-lint/prop-issue", "Prop optimisation"

        if any(kw in msg_lower for kw in RERENDER_KEYWORDS):
            return "million-lint/unnecessary-rerender", "Unnecessary re-render"

        return "million-lint/optimisation", "Component optimisation opportunity"

    def _build_fix_hint(
        self, message: str, issue_type: str, component: str, filepath: str
    ) -> str:
        """Generate a targeted fix hint."""
        msg_lower = message.lower()
        type_lower = issue_type.lower()
        comp_name = component or "this component"

        if any(kw in type_lower for kw in ("rerender", "re-render", "unnecessary-render")):
            return (
                f"Wrap {comp_name} with React.memo() to skip re-renders when props "
                "haven't changed. Also check: inline objects/arrays in JSX (create them "
                "outside render), inline event handlers (wrap with useCallback), and "
                "context consumers (split context or use selectors)."
            )

        if any(kw.lower() in msg_lower for kw in MEMO_KEYWORDS):
            return (
                f"Add memoization to {comp_name}: use React.memo() for the component, "
                "useMemo() for expensive computed values, and useCallback() for functions "
                "passed as props. This prevents unnecessary re-renders in child components."
            )

        if any(kw in msg_lower for kw in BLOCK_KEYWORDS):
            return (
                f"Consider converting {comp_name} to a Million.js block component using "
                "the block() HOC. Block components use a virtual DOM diffing optimisation "
                "that can be 70% faster for static or semi-static content."
            )

        if "inline" in msg_lower and "prop" in msg_lower:
            return (
                f"Avoid inline objects, arrays, or functions in {comp_name}'s JSX. "
                "Each render creates new references, causing child re-renders. "
                "Extract to constants, useMemo(), or useCallback()."
            )

        if "context" in msg_lower:
            return (
                f"{comp_name} re-renders due to context changes. Consider splitting "
                "the context into smaller pieces, using context selectors (use-context-selector), "
                "or moving the consuming component closer to where the data is used."
            )

        return (
            f"Review {comp_name} for rendering optimisation opportunities. Common fixes: "
            "React.memo(), useMemo(), useCallback(), extracting static JSX, and avoiding "
            "prop spreading that passes unnecessary values."
        )

    def _classify_effort(self, message: str, issue_type: str) -> Effort:
        """Estimate the effort to apply the optimisation."""
        msg_lower = message.lower()
        type_lower = issue_type.lower()

        # React.memo wrapping is usually low effort
        if any(kw.lower() in msg_lower for kw in MEMO_KEYWORDS):
            return Effort.LOW

        # Block component conversion is medium
        if any(kw in msg_lower or kw in type_lower for kw in BLOCK_KEYWORDS):
            return Effort.MEDIUM

        # Re-render fixes vary but are usually medium
        if any(kw in msg_lower or kw in type_lower for kw in RERENDER_KEYWORDS):
            return Effort.MEDIUM

        return Effort.MEDIUM
