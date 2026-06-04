"""Anthropic Claude provider implementation."""

from __future__ import annotations

import json

import anthropic

from vibeaudit.provider import LLMProvider, LLMResponse, ToolCall, ToolDefinition


class AnthropicProvider(LLMProvider):
    """LLM provider for Anthropic Claude models."""

    name = "anthropic"
    default_model = "claude-sonnet-4-20250514"

    def __init__(self, api_key: str = "", model: str = "", base_url: str = "") -> None:
        kwargs: dict = {}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url
        # If no api_key provided, anthropic SDK reads ANTHROPIC_API_KEY from env
        self._client = anthropic.AsyncAnthropic(**kwargs)
        self._model = model or self.default_model

    async def complete(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> LLMResponse:
        response = await self._client.messages.create(
            model=self._model,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return self._parse_response(response)

    async def complete_with_tools(
        self,
        system: str,
        messages: list[dict],
        tools: list[ToolDefinition],
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> LLMResponse:
        anthropic_tools = [self._map_tool(t) for t in tools]
        response = await self._client.messages.create(
            model=self._model,
            system=system,
            messages=messages,
            tools=anthropic_tools,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return self._parse_response(response)

    @staticmethod
    def _map_tool(tool: ToolDefinition) -> dict:
        """Convert ToolDefinition to Anthropic tool format."""
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.parameters,
        }

    def _parse_response(self, response: anthropic.types.Message) -> LLMResponse:
        """Convert Anthropic Message to LLMResponse."""
        content_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in response.content:
            if block.type == "text":
                content_parts.append(block.text)
            elif block.type == "tool_use":
                # block.input is already a dict from the SDK
                arguments = block.input
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {"raw": arguments}
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=arguments,
                    )
                )

        return LLMResponse(
            content="\n".join(content_parts),
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=response.model,
            tool_calls=tool_calls,
            stop_reason=response.stop_reason or "",
        )
