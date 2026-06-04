"""Ollama provider implementation using OpenAI-compatible API."""

from __future__ import annotations

import openai

from vibeaudit.providers.openai_provider import OpenAICompatibleProvider


class OllamaProvider(OpenAICompatibleProvider):
    """Provider for locally-running Ollama models via OpenAI-compatible API."""

    name = "ollama"
    default_model = "llama3.3"

    def __init__(self, model: str = "", base_url: str = "") -> None:
        resolved_base_url = base_url or "http://localhost:11434/v1"

        client = openai.AsyncOpenAI(
            base_url=resolved_base_url,
            api_key="ollama",  # Ollama doesn't need a real key
        )

        super().__init__(client=client, model=model)
