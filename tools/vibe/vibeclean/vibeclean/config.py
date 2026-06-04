"""Configuration loader -- .vibeclean.yml parsing, defaults, validation."""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from vibeclean.models import Severity

DEFAULT_CONFIG_NAME = ".vibeclean.yml"


@dataclass
class RunnerConfig:
    """Per-runner configuration."""

    enabled: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.extra.get(key, default)


@dataclass
class Config:
    """Vibeclean configuration."""

    fail_on: Severity = Severity.HIGH
    output: str = "table"
    output_file: str | None = None
    json_pretty: bool = False
    quiet: bool = False
    verbose: bool = False
    fix: bool = False

    # Runner selection
    runners_include: list[str] | None = None
    runners_exclude: list[str] | None = None

    # Per-runner config
    runner_configs: dict[str, RunnerConfig] = field(default_factory=dict)

    # Global path exclusions
    exclude: list[str] = field(default_factory=list)

    # Ignore rules and findings
    ignore_rules: list[str] = field(default_factory=list)
    ignore_findings: list[str] = field(default_factory=list)

    def get_runner_config(self, runner_name: str) -> RunnerConfig:
        return self.runner_configs.get(runner_name, RunnerConfig())

    def is_runner_enabled(self, runner_name: str) -> bool:
        if self.runners_include is not None:
            return runner_name in self.runners_include
        if self.runners_exclude is not None:
            return runner_name not in self.runners_exclude
        rc = self.get_runner_config(runner_name)
        return rc.enabled

    def is_path_excluded(self, file_path: str) -> bool:
        """Check if a file path matches any global exclude pattern."""
        for pattern in self.exclude:
            if fnmatch.fnmatch(file_path, pattern):
                return True
            parts = Path(file_path).parts
            for part in parts:
                if fnmatch.fnmatch(part, pattern):
                    return True
        return False

    def should_ignore_rule(self, runner: str, rule_id: str) -> bool:
        return f"{runner}:{rule_id}" in self.ignore_rules

    def should_ignore_finding(self, finding_id: str) -> bool:
        return finding_id in self.ignore_findings


def load_config(
    config_path: str | None = None,
    target_dir: str = ".",
    **overrides: Any,
) -> Config:
    """Load config from file and apply CLI overrides."""
    raw: dict[str, Any] = {}

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

    # Runner configs
    runners_raw = raw.get("runners", {})
    for runner_name, runner_raw in runners_raw.items():
        if isinstance(runner_raw, dict):
            enabled = runner_raw.pop("enabled", True)
            config.runner_configs[runner_name] = RunnerConfig(
                enabled=enabled, extra=runner_raw
            )

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

    return config
