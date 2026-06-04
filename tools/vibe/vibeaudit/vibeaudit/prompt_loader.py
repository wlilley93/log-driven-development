"""Load and render Jinja2 prompt templates for vulnerability scanning."""

from __future__ import annotations

import hashlib
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from vibeaudit.models import VulnClass

TEMPLATES_DIR = Path(__file__).parent / "prompts"


class PromptLoader:
    """Loads and renders Jinja2 templates for vulnerability scanning."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )

    def render_system(self) -> str:
        """Render the base system prompt."""
        template = self._env.get_template("system.j2")
        return template.render()

    def render_context(self, **kwargs) -> str:
        """Render framework/language context."""
        template = self._env.get_template("context.j2")
        return template.render(**kwargs)

    def render_scan(self, vuln_class: VulnClass, **kwargs) -> str:
        """Render a scan prompt for a specific vulnerability class."""
        template_path = f"classes/{vuln_class.value}/scan.j2"
        template = self._env.get_template(template_path)
        return template.render(**kwargs)

    def get_prompt_version(self, vuln_class: VulnClass) -> str:
        """Compute SHA256 hash of template content as version string."""
        template_path = TEMPLATES_DIR / "classes" / vuln_class.value / "scan.j2"
        content = template_path.read_text()
        return hashlib.sha256(content.encode()).hexdigest()[:12]

    def render_full_prompt(
        self,
        vuln_class: VulnClass,
        code: str,
        file_path: str,
        language: str = "unknown",
        framework: str = "unknown",
        route_path: str = "",
        http_method: str = "",
        additional_context: dict | None = None,
    ) -> tuple[str, str, str]:
        """Render complete prompt: (system_prompt, user_prompt, prompt_version).

        Returns the system prompt, the assembled user message, and the prompt version hash.
        """
        system = self.render_system()

        context = self.render_context(
            language=language,
            framework=framework,
            route_path=route_path,
            http_method=http_method,
        )

        # Strip keys already passed as explicit kwargs to avoid duplicates
        extra = {k: v for k, v in (additional_context or {}).items()
                 if k not in ("code", "file_path", "language", "framework", "route_path", "http_method")}

        scan = self.render_scan(
            vuln_class,
            code=code,
            file_path=file_path,
            language=language,
            framework=framework,
            route_path=route_path,
            http_method=http_method,
            **extra,
        )

        user_prompt = f"{context}\n\n{scan}"
        version = self.get_prompt_version(vuln_class)

        return system, user_prompt, version
