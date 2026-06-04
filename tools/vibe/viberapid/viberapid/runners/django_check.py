"""Runner for django_check — Django deployment and configuration checker."""

from __future__ import annotations

import json
from pathlib import Path

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.django_check import DjangoCheckNormaliser
from viberapid.runners.base import AsyncToolRunner


class DjangoCheckRunner(AsyncToolRunner):
    """Run Django's manage.py check --deploy to detect deployment and performance issues.

    Detects a Django project by the presence of manage.py and a settings module.
    """

    name = "django_check"
    requires_python = True

    def should_run(self) -> bool:
        if not self._file_exists("manage.py"):
            self.skip_reason = "no manage.py found (not a Django project)"
            return False

        # Verify it looks like a Django project
        manage_py = Path(self.target) / "manage.py"
        try:
            content = manage_py.read_text(errors="ignore")
            if "django" not in content.lower():
                self.skip_reason = "manage.py does not appear to be a Django management script"
                return False
        except OSError:
            self.skip_reason = "cannot read manage.py"
            return False

        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        tc = self.tool_config
        settings_module = tc.get("settings_module")

        # --- Run manage.py check --deploy ---
        cmd = ["python", "manage.py", "check", "--deploy", "--fail-level", "WARNING"]

        env: dict[str, str] = {}
        if settings_module:
            env["DJANGO_SETTINGS_MODULE"] = settings_module

        deploy_result = self._exec(cmd, env=env if env else None)
        deploy_output = deploy_result.stdout + "\n" + deploy_result.stderr

        # --- Run manage.py check for general issues ---
        cmd_general = ["python", "manage.py", "check"]
        general_result = self._exec(cmd_general, env=env if env else None)
        general_output = general_result.stdout + "\n" + general_result.stderr

        # --- Try to get database-related checks ---
        db_checks_output = ""
        cmd_db = ["python", "manage.py", "check", "--database", "default"]
        try:
            db_result = self._exec(cmd_db, env=env if env else None, timeout=30)
            db_checks_output = db_result.stdout + "\n" + db_result.stderr
        except Exception:
            pass  # Database check is optional

        # --- Try to detect DEBUG mode and missing settings ---
        settings_issues = _detect_settings_issues(self.target, settings_module)

        raw_data = {
            "deploy_output": deploy_output,
            "general_output": general_output,
            "db_checks_output": db_checks_output,
            "settings_issues": settings_issues,
            "deploy_exit_code": deploy_result.returncode,
            "general_exit_code": general_result.returncode,
        }

        normaliser = DjangoCheckNormaliser()
        findings = normaliser.normalise(raw_data)

        # Count warnings and errors from outputs
        warning_count = deploy_output.count("WARNING") + general_output.count("WARNING")
        error_count = deploy_output.count("ERROR") + general_output.count("ERROR")

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "deploy_warnings": warning_count,
                "deploy_errors": error_count,
                "deploy_exit_code": deploy_result.returncode,
                "general_exit_code": general_result.returncode,
                "settings_issues": len(settings_issues),
            },
        )


def _detect_settings_issues(target: str, settings_module: str | None) -> list[dict]:
    """Scan Django settings files for common performance/security issues."""
    issues: list[dict] = []
    target_path = Path(target)

    # Find settings files
    settings_files = list(target_path.rglob("settings.py"))
    settings_files.extend(target_path.rglob("settings/*.py"))

    for settings_file in settings_files:
        try:
            content = settings_file.read_text(errors="ignore")
        except OSError:
            continue

        rel_path = str(settings_file.relative_to(target_path))

        # Check for DEBUG = True
        if "DEBUG = True" in content or "DEBUG=True" in content:
            issues.append({
                "file": rel_path,
                "issue": "debug_enabled",
                "message": "DEBUG = True is set — must be False in production",
            })

        # Check for missing CONN_MAX_AGE (persistent connections)
        if "DATABASES" in content and "CONN_MAX_AGE" not in content:
            issues.append({
                "file": rel_path,
                "issue": "missing_conn_max_age",
                "message": (
                    "DATABASES missing CONN_MAX_AGE — connections are created "
                    "and destroyed per request, adding latency"
                ),
            })

        # Check for missing CACHES configuration
        if "CACHES" not in content:
            issues.append({
                "file": rel_path,
                "issue": "no_cache_backend",
                "message": (
                    "No CACHES configuration found — Django defaults to "
                    "local-memory cache which does not persist across processes"
                ),
            })

        # Check for missing LOGGING configuration
        if "LOGGING" not in content:
            issues.append({
                "file": rel_path,
                "issue": "no_logging_config",
                "message": "No LOGGING configuration — slow queries may go unnoticed",
            })

        # Check for template caching (cached.Loader)
        if "TEMPLATES" in content and "cached.Loader" not in content:
            issues.append({
                "file": rel_path,
                "issue": "no_template_caching",
                "message": (
                    "Templates not using cached.Loader — templates are "
                    "re-read from disk on every request in production"
                ),
            })

        # Check for missing SESSION_ENGINE
        if "SESSION_ENGINE" not in content and "django.contrib.sessions" in content:
            issues.append({
                "file": rel_path,
                "issue": "default_session_engine",
                "message": (
                    "Using default database session engine — consider "
                    "django.contrib.sessions.backends.cache for performance"
                ),
            })

    return issues
