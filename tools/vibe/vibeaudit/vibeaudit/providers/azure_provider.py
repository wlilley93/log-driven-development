"""Azure OpenAI provider implementation."""

from __future__ import annotations

import os

import openai

from vibeaudit.providers.openai_provider import OpenAICompatibleProvider


class AzureProvider(OpenAICompatibleProvider):
    """Provider for Azure-hosted OpenAI models."""

    name = "azure"
    default_model = "gpt-4o"

    def __init__(
        self,
        api_key: str = "",
        model: str = "",
        base_url: str = "",
        api_version: str = "",
    ) -> None:
        resolved_api_version = (
            api_version
            or os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21")
        )

        kwargs: dict = {}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["azure_endpoint"] = base_url
        # If no api_key, the Azure SDK reads AZURE_OPENAI_API_KEY from env

        client = openai.AsyncAzureOpenAI(
            api_version=resolved_api_version,
            **kwargs,
        )

        super().__init__(client=client, model=model)
