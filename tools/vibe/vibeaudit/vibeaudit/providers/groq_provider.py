"""Groq provider implementation using OpenAI-compatible API."""

from __future__ import annotations

import openai

from vibeaudit.providers.openai_provider import OpenAICompatibleProvider


class GroqProvider(OpenAICompatibleProvider):
    """Provider for Groq-hosted models via OpenAI-compatible API."""

    name = "groq"
    default_model = "llama-3.3-70b-versatile"

    def __init__(self, api_key: str = "", model: str = "", base_url: str = "") -> None:
        resolved_base_url = base_url or "https://api.groq.com/openai/v1"

        kwargs: dict = {}
        if api_key:
            kwargs["api_key"] = api_key
        # If no api_key, reads OPENAI_API_KEY from env — caller should set GROQ_API_KEY
        # and the factory in __init__.py maps it

        client = openai.AsyncOpenAI(
            base_url=resolved_base_url,
            **kwargs,
        )

        super().__init__(client=client, model=model)
