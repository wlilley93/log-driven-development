"""Base normaliser — converts raw tool output to Finding objects."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from viberapid.models import Finding


class BaseNormaliser(ABC):
    """Base class for all normalisers."""

    @abstractmethod
    def normalise(self, raw_data: Any) -> list[Finding]:
        """Convert raw tool output to normalised findings."""
        ...
