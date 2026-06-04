"""Configuration loader — .vibedeploy.yml parsing, defaults, validation."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from vibedeploy.models import Severity

DEFAULT_CONFIG_NAME = ".vibedeploy.yml"


@dataclass
class ToolConfig:
    """Per-tool configuration."""

    enabled: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.extra.get(key, default)


@dataclass
class Config:
    """vibedeploy configuration."""

    # Thresholds
    fail_on: Severity = Severity.HIGH
    ship_safe: bool = False
    threads: int = 0  # 0 = cpu_count
    timeout: int = 120
    output: str = "table"
    output_file: str | None = None
    json_pretty: bool = False
    quiet: bool = False
    verbose: bool = False
    fix: bool = False
    dry_run: bool = False

    # Target URL for live checks (SSL, headers, CORS)
    url: str | None = None

    # Environment hint (production, staging, development)
    env: str | None = None

    # Stack override (auto-detected if not set)
    stack: list[str] | None = None

    # Cloud provider override
    cloud: str | None = None

    # Database type override
    db: str | None = None

    # Tool selection
    tools_include: list[str] | None = None
    tools_exclude: list[str] | None = None

    # Per-tool config
    tool_configs: dict[str, ToolConfig] = field(default_factory=dict)

    # Ignore rules and findings
    ignore_rules: list[str] = field(default_factory=list)
    ignore_findings: list[str] = field(default_factory=list)

    # History retention
    findings_retention: int = 30

    def get_tool_config(self, tool_name: str) -> ToolConfig:
        return self.tool_configs.get(tool_name, ToolConfig())

    def is_tool_enabled(self, tool_name: str) -> bool:
        if self.tools_include is not None:
            return tool_name in self.tools_include
        if self.tools_exclude is not None:
            return tool_name not in self.tools_exclude
        tc = self.get_tool_config(tool_name)
        return tc.enabled

    def should_ignore_rule(self, tool: str, rule_id: str) -> bool:
        return f"{tool}:{rule_id}" in self.ignore_rules

    def should_ignore_finding(self, finding_id: str) -> bool:
        return finding_id in self.ignore_findings


def load_config(
    config_path: str | None = None,
    target_dir: str = ".",
    **overrides: Any,
) -> Config:
    """Load config from file and apply CLI overrides."""
    raw: dict[str, Any] = {}

    # Find config file
    if config_path:
        path = Path(config_path)
    else:
        path = Path(target_dir) / DEFAULT_CONFIG_NAME

    if path.exists():
        with open(path) as f:
            raw = yaml.safe_load(f) or {}

    config = Config()

    # Map YAML keys
    if "fail_on" in raw:
        config.fail_on = Severity(raw["fail_on"].upper())
    if "ship_safe" in raw:
        config.ship_safe = bool(raw["ship_safe"])
    if "findings_retention" in raw:
        config.findings_retention = int(raw["findings_retention"])
    if "url" in raw:
        config.url = raw["url"]
    if "env" in raw:
        config.env = raw["env"]
    if "stack" in raw:
        config.stack = raw["stack"] if isinstance(raw["stack"], list) else [raw["stack"]]
    if "cloud" in raw:
        config.cloud = raw["cloud"]
    if "db" in raw:
        config.db = raw["db"]

    # Tool configs
    tools_raw = raw.get("tools", {})
    for tool_name, tool_raw in tools_raw.items():
        if isinstance(tool_raw, dict):
            enabled = tool_raw.pop("enabled", True)
            config.tool_configs[tool_name] = ToolConfig(enabled=enabled, extra=tool_raw)

    # Ignore rules
    config.ignore_rules = raw.get("ignore_rules", [])
    config.ignore_findings = [
        str(f.get("id", f) if isinstance(f, dict) else f)
        for f in raw.get("ignore_findings", [])
    ]

    # Apply CLI overrides
    for key, value in overrides.items():
        if value is not None and hasattr(config, key):
            setattr(config, key, value)

    # Resolve threads
    if config.threads <= 0:
        config.threads = os.cpu_count() or 4

    return config
