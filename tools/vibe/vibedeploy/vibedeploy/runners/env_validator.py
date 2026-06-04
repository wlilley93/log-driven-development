"""env_validator — custom runner that checks .env files for deploy issues."""

from __future__ import annotations
import re
from pathlib import Path
from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner


class EnvValidatorRunner(AsyncToolRunner):
    name = "env_validator"

    def should_run(self) -> bool:
        if not self._file_exists(".env", ".env.example", ".env.production"):
            self.skip_reason = "no .env files found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        findings = []
        target = Path(self.target)

        # Check for .env.example
        env_example = target / ".env.example"
        env_file = target / ".env"
        env_prod = target / ".env.production"

        # Check if .env is in .gitignore
        gitignore = target / ".gitignore"
        if env_file.exists():
            env_in_gitignore = False
            if gitignore.exists():
                content = gitignore.read_text(errors="replace")
                env_in_gitignore = ".env" in content
            if not env_in_gitignore:
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.CRITICAL,
                    category=Category.ENV_SECRETS,
                    file=".env",
                    rule_id="env-not-gitignored",
                    rule_name="Env Not Gitignored",
                    message=".env file is not in .gitignore — secrets may be committed",
                    blocks_deploy=True,
                    effort=Effort.TRIVIAL,
                    fix_hint="Add .env to .gitignore",
                    fix_command="echo '.env' >> .gitignore",
                ))

        # Compare .env.example with .env for missing vars
        if env_example.exists() and env_file.exists():
            example_vars = self._parse_env_keys(env_example)
            actual_vars = self._parse_env_keys(env_file)
            missing = example_vars - actual_vars
            for var in sorted(missing):
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.HIGH,
                    category=Category.ENV_SECRETS,
                    file=".env",
                    rule_id="env-missing-var",
                    rule_name="Missing Env Var",
                    message=f"Environment variable {var} defined in .env.example but missing from .env",
                    blocks_deploy=True,
                    effort=Effort.TRIVIAL,
                    fix_hint=f"Add {var}=<value> to .env",
                ))

        # Check for placeholder/default values
        if env_file.exists():
            self._check_placeholder_values(env_file, findings)
        if env_prod.exists():
            self._check_placeholder_values(env_prod, findings)

        # Check for DEBUG/dev-only settings in production env
        for env_path in [env_prod, env_file]:
            if env_path.exists():
                self._check_debug_settings(env_path, findings)

        return ToolResult(tool=self.name, status=ToolStatus.SUCCESS, findings=findings)

    def _parse_env_keys(self, path: Path) -> set[str]:
        keys = set()
        for line in path.read_text(errors="replace").split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key = line.split("=", 1)[0].strip()
                keys.add(key)
        return keys

    def _check_placeholder_values(self, path: Path, findings: list[Finding]) -> None:
        placeholders = {"changeme", "TODO", "FIXME", "replace_me", "your_secret_here",
                       "xxx", "CHANGE_ME", "placeholder", "secret", "password123",
                       "admin", "test", "example"}
        rel = str(path.relative_to(self.target))
        for i, line in enumerate(path.read_text(errors="replace").split("\n"), 1):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                value = line.split("=", 1)[1].strip().strip("'\"")
                if value.lower() in {p.lower() for p in placeholders}:
                    key = line.split("=", 1)[0].strip()
                    findings.append(Finding(
                        tool=self.name,
                        severity=Severity.HIGH,
                        category=Category.ENV_SECRETS,
                        file=rel,
                        line=i,
                        rule_id="env-placeholder",
                        rule_name="Placeholder Value",
                        message=f"{key} has a placeholder value: '{value}'",
                        blocks_deploy=True,
                        effort=Effort.TRIVIAL,
                        fix_hint=f"Set {key} to a real value",
                    ))

    def _check_debug_settings(self, path: Path, findings: list[Finding]) -> None:
        rel = str(path.relative_to(self.target))
        debug_patterns = {
            "DEBUG": ["true", "1", "yes"],
            "NODE_ENV": ["development", "test"],
            "FLASK_DEBUG": ["1", "true"],
            "DJANGO_DEBUG": ["true", "1"],
        }
        for i, line in enumerate(path.read_text(errors="replace").split("\n"), 1):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip("'\"").lower()
                if key in debug_patterns and value in debug_patterns[key]:
                    findings.append(Finding(
                        tool=self.name,
                        severity=Severity.CRITICAL,
                        category=Category.BUILD,
                        file=rel,
                        line=i,
                        rule_id="env-debug-mode",
                        rule_name="Debug Mode",
                        message=f"{key}={value} — debug mode enabled in production config",
                        blocks_deploy=True,
                        effort=Effort.TRIVIAL,
                        fix_hint=f"Set {key} to production value",
                    ))
