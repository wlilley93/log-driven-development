"""Configuration loader — .viberapid.yml parsing, defaults, validation."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from viberapid.models import Severity

DEFAULT_CONFIG_NAME = ".viberapid.yml"


@dataclass
class ToolConfig:
    """Per-tool configuration."""

    enabled: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.extra.get(key, default)


@dataclass
class Config:
    """viberapid configuration."""

    fail_on: Severity = Severity.HIGH
    ship_fast: bool = False
    threads: int = 0  # 0 = cpu_count
    timeout: int = 120
    load_timeout: int = 300
    output: str = "table"
    output_file: str | None = None
    json_pretty: bool = False
    quiet: bool = False
    verbose: bool = False
    since: str | None = None
    fix: bool = False
    url: str | None = None
    stack: str = "auto"  # auto | node | python | fullstack

    # Tool selection
    tools_include: list[str] | None = None
    tools_exclude: list[str] | None = None

    # Per-tool config
    tool_configs: dict[str, ToolConfig] = field(default_factory=dict)

    # Budget
    budget_file: str | None = None

    # Load testing
    load_duration: str = "30s"
    load_vus: int = 50

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

    @property
    def detected_stack(self) -> str:
        """Return the effective stack — used by scanner to filter runners."""
        return self.stack


def detect_stack(target_dir: str) -> str:
    """Auto-detect project stack from filesystem."""
    target = Path(target_dir)
    has_node = (target / "package.json").exists()
    has_python = (
        (target / "requirements.txt").exists()
        or (target / "pyproject.toml").exists()
        or (target / "setup.py").exists()
    )

    if has_node and has_python:
        return "fullstack"
    if has_node:
        return "node"
    if has_python:
        return "python"
    return "fullstack"  # default to fullstack


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
    if "ship_fast" in raw:
        config.ship_fast = bool(raw["ship_fast"])
    if "url" in raw:
        config.url = raw["url"]
    if "stack" in raw:
        config.stack = raw["stack"]
    if "findings_retention" in raw:
        config.findings_retention = int(raw["findings_retention"])
    if "budget" in raw:
        config.budget_file = raw["budget"]

    # Tool configs
    tools_raw = raw.get("tools", {})
    for tool_name, tool_raw in tools_raw.items():
        if isinstance(tool_raw, dict):
            enabled = tool_raw.pop("enabled", True)
            config.tool_configs[tool_name] = ToolConfig(enabled=enabled, extra=tool_raw)

    # Ignore rules
    config.ignore_rules = raw.get("ignore_rules") or []
    raw_ignore_findings = raw.get("ignore_findings") or []
    config.ignore_findings = [
        str(f.get("id", f) if isinstance(f, dict) else f)
        for f in raw_ignore_findings
    ]

    # Apply CLI overrides
    for key, value in overrides.items():
        if value is not None and hasattr(config, key):
            setattr(config, key, value)

    # Resolve threads
    if config.threads <= 0:
        config.threads = os.cpu_count() or 4

    # Auto-detect stack if needed
    if config.stack == "auto":
        config.stack = detect_stack(target_dir)

    return config
