"""Configuration with layered resolution: file → env vars → CLI flags."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from vibeaudit.models import VulnClass

DEFAULT_CONFIG_FILE = ".vibeaudit.yml"


class ProviderConfig(BaseModel):
    name: str = "anthropic"
    model: str = ""  # empty = use provider default
    api_key: str = ""
    base_url: str = ""
    max_tokens: int = 4096
    temperature: float = 0.1


class ScanConfig(BaseModel):
    target_dir: str = "."
    include: list[str] = Field(default_factory=lambda: ["**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx", "**/*.py", "**/*.go", "**/*.java", "**/*.rs", "**/*.rb"])
    exclude: list[str] = Field(default_factory=lambda: ["node_modules/**", ".next/**", "__pycache__/**", "*.min.js", "dist/**", "build/**", ".git/**", "vendor/**", "*.lock", "package-lock.json"])
    vuln_classes: list[str] = Field(default_factory=lambda: [v.value for v in VulnClass])
    max_file_size_kb: int = 500
    max_snippet_lines: int = 200
    concurrency: int = 4


class AgentConfig(BaseModel):
    enabled: bool = False
    max_tokens_budget: int = 500_000
    max_iterations: int = 25
    warning_threshold: float = 0.9


class CostConfig(BaseModel):
    warn_threshold_usd: float = 1.0
    hard_cap_usd: float = 5.0


class BaselineConfig(BaseModel):
    path: str = ".vibeaudit-baseline.json"


class OutputConfig(BaseModel):
    format: str = "table"
    output_file: str = ""


class VibeauditConfig(BaseModel):
    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    scan: ScanConfig = Field(default_factory=ScanConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    cost: CostConfig = Field(default_factory=CostConfig)
    baseline: BaselineConfig = Field(default_factory=BaselineConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)


def load_config(
    config_path: str | None = None,
    cli_overrides: dict | None = None,
) -> VibeauditConfig:
    """Load config with layered resolution: file → env vars → CLI flags."""
    data: dict = {}

    # 1. Load from YAML file
    path = Path(config_path) if config_path else Path(DEFAULT_CONFIG_FILE)
    if path.exists():
        with open(path) as f:
            file_data = yaml.safe_load(f)
            if isinstance(file_data, dict):
                data = file_data

    # 2. Apply env var overrides
    env_mappings = {
        "VIBEAUDIT_PROVIDER": ("provider", "name"),
        "VIBEAUDIT_MODEL": ("provider", "model"),
        "VIBEAUDIT_CONCURRENCY": ("scan", "concurrency"),
        "VIBEAUDIT_BUDGET": ("cost", "hard_cap_usd"),
    }
    for env_key, (section, field) in env_mappings.items():
        val = os.environ.get(env_key)
        if val is not None:
            data.setdefault(section, {})[field] = _coerce(val, field)

    # Provider API keys from env
    api_key_env = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "azure": "AZURE_OPENAI_KEY",
        "groq": "GROQ_API_KEY",
    }
    provider_name = data.get("provider", {}).get("name", "anthropic")
    env_var = api_key_env.get(provider_name)
    if env_var and os.environ.get(env_var):
        data.setdefault("provider", {})["api_key"] = os.environ[env_var]

    # 3. Apply CLI overrides
    if cli_overrides:
        for key, value in cli_overrides.items():
            if value is None:
                continue
            parts = key.split(".")
            if len(parts) == 2:
                section, field = parts
                data.setdefault(section, {})[field] = value
            elif len(parts) == 1:
                data[key] = value

    return VibeauditConfig(**data)


def _coerce(val: str, field: str) -> str | int | float:
    """Coerce string env values to appropriate types."""
    if field in ("concurrency", "max_tokens", "max_iterations", "max_tokens_budget"):
        return int(val)
    if field in ("hard_cap_usd", "warn_threshold_usd", "temperature", "warning_threshold"):
        return float(val)
    return val
