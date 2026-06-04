"""OpenAI-compatible provider implementation.

Serves as base class for OpenAI, Azure, Groq, and Ollama providers since
they all use the OpenAI client API format.
"""

from __future__ import annotations

import json

import openai

from vibeaudit.provider import LLMProvider, LLMResponse, ToolCall, ToolDefinition


class OpenAICompatibleProvider(LLMProvider):
    """Base provider for any OpenAI-compatible API (OpenAI, Azure, Groq, Ollama)."""

    name = "openai"
    default_model = "gpt-4o"

    def __init__(
        self,
        client: openai.AsyncOpenAI | None = None,
        api_key: str = "",
        model: str = "",
        base_url: str = "",
    ) -> None:
        if client is not None:
            self._client = client
        else:
            kwargs: dict = {}
            if api_key:
                kwargs["api_key"] = api_key
            if base_url:
                kwargs["base_url"] = base_url
            # If no api_key provided, openai SDK reads OPENAI_API_KEY from env
            self._client = openai.AsyncOpenAI(**kwargs)
        self._model = model or self.default_model

    async def complete(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> LLMResponse:
        full_messages = self._build_messages(system, messages)
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=full_messages,
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
        full_messages = self._build_messages(system, messages)
        openai_tools = [self._map_tool(t) for t in tools]
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=full_messages,
            tools=openai_tools,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return self._parse_response(response)

    @staticmethod
    def _build_messages(system: str, messages: list[dict]) -> list[dict]:
        """Prepend system message to the messages array."""
        result: list[dict] = []
        if system:
            result.append({"role": "system", "content": system})
        result.extend(messages)
        return result

    @staticmethod
    def _map_tool(tool: ToolDefinition) -> dict:
        """Convert ToolDefinition to OpenAI function-calling format."""
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }

    def _parse_response(
        self, response: openai.types.chat.ChatCompletion
    ) -> LLMResponse:
        """Convert OpenAI ChatCompletion to LLMResponse."""
        choice = response.choices[0] if response.choices else None
        content = ""
        tool_calls: list[ToolCall] = []
        stop_reason = ""

        if choice:
            content = choice.message.content or ""
            stop_reason = choice.finish_reason or ""

            if choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    arguments: dict = {}
                    if tc.function.arguments:
                        try:
                            arguments = json.loads(tc.function.arguments)
                        except json.JSONDecodeError:
                            arguments = {"raw": tc.function.arguments}
                    tool_calls.append(
                        ToolCall(
                            id=tc.id,
                            name=tc.function.name,
                            arguments=arguments,
                        )
                    )

        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0

        return LLMResponse(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=response.model,
            tool_calls=tool_calls,
            stop_reason=stop_reason,
        )


class OpenAIProvider(OpenAICompatibleProvider):
    """Standard OpenAI provider."""

    name = "openai"
    default_model = "gpt-4o"

    def __init__(self, api_key: str = "", model: str = "", base_url: str = "") -> None:
        super().__init__(api_key=api_key, model=model, base_url=base_url)
