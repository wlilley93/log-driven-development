"""Abstract LLM provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolDefinition:
    """A tool the LLM can call."""

    name: str
    description: str
    parameters: dict  # JSON Schema


@dataclass
class ToolCall:
    """A tool call from the LLM."""

    id: str
    name: str
    arguments: dict


@dataclass
class ToolResult:
    """Result of executing a tool."""

    tool_call_id: str
    content: str
    is_error: bool = False


@dataclass
class LLMResponse:
    """Response from an LLM provider."""

    content: str
    input_tokens: int
    output_tokens: int
    model: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = ""


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    name: str
    default_model: str

    @abstractmethod
    async def complete(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> LLMResponse:
        ...

    @abstractmethod
    async def complete_with_tools(
        self,
        system: str,
        messages: list[dict],
        tools: list[ToolDefinition],
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> LLMResponse:
        ...
