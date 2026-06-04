"""Provider factory — create an LLM provider from configuration."""

from __future__ import annotations

import os

from vibeaudit.config import ProviderConfig
from vibeaudit.provider import LLMProvider

# Env var mapping: provider name -> env var for API key
_API_KEY_ENV_VARS: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "azure": "AZURE_OPENAI_KEY",
    "groq": "GROQ_API_KEY",
    # ollama doesn't need an API key
}


def create_provider(config: ProviderConfig) -> LLMProvider:
    """Create an LLM provider from a ProviderConfig.

    Resolves API keys from environment variables if not set in config.

    Args:
        config: Provider configuration with name, model, api_key, base_url.

    Returns:
        An initialized LLMProvider ready for use.

    Raises:
        ValueError: If the provider name is not recognized.
    """
    name = config.name.lower()

    # Auto-resolve API key from env if not provided in config
    api_key = config.api_key
    if not api_key and name in _API_KEY_ENV_VARS:
        api_key = os.environ.get(_API_KEY_ENV_VARS[name], "")

    model = config.model  # empty string means "use provider default"

    if name == "anthropic":
        from vibeaudit.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider(
            api_key=api_key,
            model=model,
            base_url=config.base_url,
        )

    if name == "openai":
        from vibeaudit.providers.openai_provider import OpenAIProvider

        return OpenAIProvider(
            api_key=api_key,
            model=model,
            base_url=config.base_url,
        )

    if name == "azure":
        from vibeaudit.providers.azure_provider import AzureProvider

        return AzureProvider(
            api_key=api_key,
            model=model,
            base_url=config.base_url,
        )

    if name == "ollama":
        from vibeaudit.providers.ollama_provider import OllamaProvider

        return OllamaProvider(
            model=model,
            base_url=config.base_url,
        )

    if name == "groq":
        from vibeaudit.providers.groq_provider import GroqProvider

        return GroqProvider(
            api_key=api_key,
            model=model,
            base_url=config.base_url,
        )

    supported = ", ".join(sorted(_API_KEY_ENV_VARS.keys()) + ["ollama"])
    raise ValueError(
        f"Unknown provider '{name}'. Supported providers: {supported}"
    )
