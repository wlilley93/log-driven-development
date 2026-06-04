"""Base normaliser interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from vibedeploy.models import Finding, Severity


class BaseNormaliser(ABC):
    """Transform raw tool output into normalised Finding objects."""

    tool_name: str = ""

    @abstractmethod
    def normalise(self, raw_data: Any) -> list[Finding]:
        """Convert raw tool output to a list of Findings."""
        ...

    @staticmethod
    def cvss_to_severity(cvss: float | None) -> Severity:
        """Map CVSS score to severity level."""
        if cvss is None:
            return Severity.MEDIUM
        if cvss >= 9.0:
            return Severity.CRITICAL
        if cvss >= 7.0:
            return Severity.HIGH
        if cvss >= 4.0:
            return Severity.MEDIUM
        return Severity.LOW

    @staticmethod
    def text_severity(text: str) -> Severity:
        """Map text severity to Severity enum."""
        mapping = {
            "critical": Severity.CRITICAL,
            "error": Severity.CRITICAL,
            "high": Severity.HIGH,
            "warning": Severity.HIGH,
            "moderate": Severity.MEDIUM,
            "medium": Severity.MEDIUM,
            "info": Severity.INFO,
            "low": Severity.LOW,
            "note": Severity.INFO,
        }
        return mapping.get(text.lower(), Severity.MEDIUM)
