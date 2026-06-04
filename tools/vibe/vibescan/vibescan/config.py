"""Configuration loader — .vibescan.yml parsing, defaults, validation."""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from vibescan.models import Severity

DEFAULT_CONFIG_NAME = ".vibescan.yml"

DEFAULT_LICENCE_BLOCKLIST = ["GPL-2.0", "GPL-3.0", "AGPL-3.0", "SSPL"]
DEFAULT_LICENCE_ALLOWLIST = [
    "MIT",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "ISC",
    "0BSD",
    "Unlicense",
    "CC0-1.0",
]

DEFAULT_SEMGREP_RULESETS = [
    "p/owasp-top-ten",
    "p/secrets",
]


@dataclass
class ToolConfig:
    """Per-tool configuration."""

    enabled: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.extra.get(key, default)


@dataclass
class Config:
    """Vibescan configuration."""

    fail_on: Severity = Severity.HIGH
    ship_safe: bool = False
    deep: bool = False
    threads: int = 0  # 0 = cpu_count
    timeout: int = 120
    output: str = "table"
    output_file: str | None = None
    json_pretty: bool = False
    quiet: bool = False
    verbose: bool = False
    since: str | None = None
    fix: bool = False
    no_secrets: bool = False

    # Tool selection
    tools_include: list[str] | None = None
    tools_exclude: list[str] | None = None

    # Per-tool config
    tool_configs: dict[str, ToolConfig] = field(default_factory=dict)

    # Licence
    licence_blocklist: list[str] = field(default_factory=lambda: list(DEFAULT_LICENCE_BLOCKLIST))
    licence_allowlist: list[str] = field(default_factory=lambda: list(DEFAULT_LICENCE_ALLOWLIST))

    # Global path exclusions (applied across all tools)
    exclude: list[str] = field(default_factory=list)

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

    def is_path_excluded(self, file_path: str) -> bool:
        """Check if a file path matches any global exclude pattern.

        Supports glob-style patterns (fnmatch).  Both the raw path and
        each of its path components are tested so that a pattern like
        ``node_modules`` matches ``node_modules/foo/bar.js`` and a pattern
        like ``*.min.js`` matches ``dist/app.min.js``.
        """
        for pattern in self.exclude:
            if fnmatch.fnmatch(file_path, pattern):
                return True
            # Also check each path component (allows "node_modules" to match
            # any file under a node_modules directory)
            parts = Path(file_path).parts
            for part in parts:
                if fnmatch.fnmatch(part, pattern):
                    return True
        return False

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

    # Tool configs
    tools_raw = raw.get("tools", {})
    for tool_name, tool_raw in tools_raw.items():
        if isinstance(tool_raw, dict):
            enabled = tool_raw.pop("enabled", True)
            config.tool_configs[tool_name] = ToolConfig(enabled=enabled, extra=tool_raw)

    # Licence config
    licence_raw = tools_raw.get("licence", raw.get("licence", {}))
    if isinstance(licence_raw, dict):
        if "blocklist" in licence_raw:
            config.licence_blocklist = licence_raw["blocklist"]
        if "allowlist" in licence_raw:
            config.licence_allowlist = licence_raw["allowlist"]

    # Global exclude paths
    config.exclude = raw.get("exclude", [])

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
