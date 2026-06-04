"""Auto-detect project stack from filesystem markers."""

from __future__ import annotations

from pathlib import Path
from typing import Any


# Mapping of file/dir markers to stack components
_MARKERS: list[tuple[str, str, list[str]]] = [
    # (file_or_glob, stack_tag, recommended_tools)
    ("Dockerfile", "docker", ["hadolint", "dockle", "dive", "docker_bench", "trivy_image"]),
    ("docker-compose.yml", "docker-compose", ["checkov", "kics"]),
    ("docker-compose.yaml", "docker-compose", ["checkov", "kics"]),
    (".dockerignore", "docker", []),
    # Terraform
    ("*.tf", "terraform", ["tfsec", "checkov", "terrascan", "conftest"]),
    ("terraform.tfstate", "terraform", []),
    # Kubernetes
    ("k8s/", "kubernetes", ["kubesec", "kubeval", "polaris", "pluto", "kube_score", "popeye", "nova", "kubectl_neat"]),
    ("kubernetes/", "kubernetes", ["kubesec", "kubeval", "polaris", "pluto", "kube_score"]),
    ("kustomization.yaml", "kubernetes", ["kubesec", "kubeval"]),
    ("kustomization.yml", "kubernetes", ["kubesec", "kubeval"]),
    # Helm
    ("Chart.yaml", "helm", ["helm_lint", "conftest"]),
    ("charts/", "helm", ["helm_lint"]),
    # CloudFormation
    ("template.yaml", "cloudformation", ["cfn_lint", "checkov"]),
    ("template.json", "cloudformation", ["cfn_lint"]),
    ("cloudformation/", "cloudformation", ["cfn_lint", "checkov"]),
    # Ansible
    ("playbook.yml", "ansible", ["ansible_lint"]),
    ("ansible.cfg", "ansible", ["ansible_lint"]),
    ("roles/", "ansible", ["ansible_lint"]),
    # Database migrations
    ("migrations/", "database", ["squawk", "sqlfluff", "migra", "atlas", "rls_checker"]),
    ("alembic/", "database", ["squawk", "sqlfluff"]),
    ("prisma/", "database", ["squawk", "sqlfluff", "rls_checker"]),
    ("db/migrate/", "database", ["squawk", "sqlfluff"]),
    ("*.sql", "sql", ["squawk", "sqlfluff", "rls_checker"]),
    # Python
    ("requirements.txt", "python", ["pip_audit", "pip_licenses"]),
    ("Pipfile", "python", ["pip_audit"]),
    ("pyproject.toml", "python", ["pip_audit", "pip_licenses"]),
    ("setup.py", "python", []),
    # JavaScript/Node
    ("package.json", "node", ["npm_audit_prod", "license_checker"]),
    ("package-lock.json", "node", ["npm_audit_prod"]),
    ("yarn.lock", "node", ["npm_audit_prod"]),
    ("pnpm-lock.yaml", "node", []),
    # Web server
    ("nginx.conf", "nginx", ["nginx_tester", "gixy", "nginx_analyser"]),
    ("nginx/", "nginx", ["nginx_tester", "gixy"]),
    ("apache2/", "apache", []),
    # Process managers
    ("Procfile", "procfile", ["procfile_linter"]),
    ("ecosystem.config.js", "pm2", ["pm2_validator"]),
    ("ecosystem.config.cjs", "pm2", ["pm2_validator"]),
    # Config files
    (".env", "env", ["dotenv_linter", "detect_secrets", "env_validator"]),
    (".env.example", "env", ["env_validator"]),
    (".env.production", "env", ["dotenv_linter", "env_validator"]),
    # Git
    (".git/", "git", ["git_secrets", "trufflehog"]),
    # SSL
    ("*.pem", "ssl", ["certigo", "ssl_checker"]),
    ("*.crt", "ssl", ["certigo"]),
    # YAML/JSON config
    ("*.yml", "yaml_config", ["yamllint"]),
    ("*.yaml", "yaml_config", ["yamllint"]),
    # Cloud
    (".aws/", "aws", ["prowler", "scoutsuite", "cloudsplaining", "parliament", "s3scanner"]),
    ("serverless.yml", "aws", ["prowler"]),
    # Observability
    ("otel-collector-config.yaml", "otel", ["otel_checker"]),
    (".sentryclirc", "sentry", ["sentry_checker"]),
    ("sentry.properties", "sentry", ["sentry_checker"]),
    # CI/CD
    (".github/workflows/", "github_actions", []),
    (".gitlab-ci.yml", "gitlab_ci", []),
    ("Jenkinsfile", "jenkins", []),
]


def detect_stack(target: str, config_stack: list[str] | None = None) -> dict[str, Any]:
    """Auto-detect the project stack from filesystem markers.

    Returns a dict with:
    - tags: set of detected stack tags (e.g., {"docker", "node", "database"})
    - recommended_tools: set of tool names relevant for this stack
    - markers_found: list of (marker, tag) tuples for debugging
    """
    target_path = Path(target).resolve()
    tags: set[str] = set()
    recommended_tools: set[str] = set()
    markers_found: list[tuple[str, str]] = []

    # Override with config if provided
    if config_stack:
        tags.update(config_stack)

    for marker, tag, tools in _MARKERS:
        if marker.endswith("/"):
            # Directory check
            if (target_path / marker.rstrip("/")).is_dir():
                tags.add(tag)
                recommended_tools.update(tools)
                markers_found.append((marker, tag))
        elif "*" in marker:
            # Glob check
            matches = list(target_path.glob(marker))
            if matches:
                tags.add(tag)
                recommended_tools.update(tools)
                markers_found.append((marker, tag))
        else:
            # File check
            if (target_path / marker).exists():
                tags.add(tag)
                recommended_tools.update(tools)
                markers_found.append((marker, tag))

    # Always include universal tools
    universal_tools = {
        "detect_secrets", "trufflehog", "git_secrets",
        "env_validator", "source_map_checker", "debug_mode_checker",
        "health_check_scanner", "graceful_shutdown",
        "log_level_checker",
    }
    recommended_tools.update(universal_tools)

    # URL-based tools (only if --url is provided, checked at scanner level)
    url_tools = {
        "testssl", "observatory", "securityheaders", "webhint",
        "ssl_checker", "redirect_checker", "cors_checker",
        "rate_limit_checker", "mixed_content", "httpx_probe",
    }

    return {
        "tags": sorted(tags),
        "recommended_tools": sorted(recommended_tools),
        "url_tools": sorted(url_tools),
        "markers_found": markers_found,
    }
