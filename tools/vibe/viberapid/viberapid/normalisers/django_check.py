"""Normaliser for Django check --deploy output."""

from __future__ import annotations

import re
from typing import Any

from viberapid.models import Category, Effort, Finding, Severity
from viberapid.normalisers.base import BaseNormaliser

# Django system check IDs and their performance/security implications
SECURITY_CHECK_IDS = {
    "security.W001": ("SecurityMiddleware missing", Severity.HIGH),
    "security.W002": ("SECURE_HSTS_SECONDS not set", Severity.MEDIUM),
    "security.W003": ("SECURE_CONTENT_TYPE_NOSNIFF not True", Severity.MEDIUM),
    "security.W004": ("SECURE_HSTS_INCLUDE_SUBDOMAINS not True", Severity.LOW),
    "security.W005": ("SECURE_HSTS_PRELOAD not True", Severity.LOW),
    "security.W006": ("SECURE_SSL_REDIRECT not True", Severity.MEDIUM),
    "security.W007": ("SECURE_BROWSER_XSS_FILTER not True", Severity.LOW),
    "security.W008": ("SECURE_SSL_REDIRECT not True", Severity.MEDIUM),
    "security.W009": ("SECRET_KEY has default value", Severity.CRITICAL),
    "security.W012": ("SESSION_COOKIE_SECURE not True", Severity.HIGH),
    "security.W016": ("CSRF_COOKIE_SECURE not True", Severity.HIGH),
    "security.W018": ("DEBUG is True", Severity.CRITICAL),
    "security.W019": ("X_FRAME_OPTIONS not set", Severity.MEDIUM),
    "security.W020": ("ALLOWED_HOSTS is empty", Severity.HIGH),
    "security.W021": ("SECURE_REFERRER_POLICY not set", Severity.MEDIUM),
    "security.W022": ("SECURE_CROSS_ORIGIN_OPENER_POLICY not set", Severity.LOW),
}

# Custom settings issues and their classifications
SETTINGS_ISSUE_MAP = {
    "debug_enabled": {
        "severity": Severity.CRITICAL,
        "rule_name": "Debug Mode Enabled",
        "fix_hint": (
            "Set DEBUG = False in production. Debug mode exposes sensitive "
            "information, disables template caching, and enables verbose error pages."
        ),
    },
    "missing_conn_max_age": {
        "severity": Severity.MEDIUM,
        "rule_name": "Missing Connection Pooling",
        "fix_hint": (
            "Add CONN_MAX_AGE to your DATABASES setting (e.g., 600 for 10 minutes). "
            "This enables persistent database connections and avoids the overhead "
            "of creating a new connection for every request."
        ),
    },
    "no_cache_backend": {
        "severity": Severity.MEDIUM,
        "rule_name": "No Cache Backend Configured",
        "fix_hint": (
            "Configure a CACHES backend. Use Redis or Memcached for production: "
            "CACHES = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache', "
            "'LOCATION': 'redis://127.0.0.1:6379'}}."
        ),
    },
    "no_logging_config": {
        "severity": Severity.LOW,
        "rule_name": "No Logging Configuration",
        "fix_hint": (
            "Add LOGGING configuration to capture slow queries. Enable "
            "'django.db.backends' logger at DEBUG level during profiling to "
            "see all SQL queries and their timing."
        ),
    },
    "no_template_caching": {
        "severity": Severity.MEDIUM,
        "rule_name": "Template Caching Disabled",
        "fix_hint": (
            "Wrap template loaders with cached.Loader in production: "
            "['django.template.loaders.cached.Loader', "
            "['django.template.loaders.filesystem.Loader', "
            "'django.template.loaders.app_directories.Loader']]."
        ),
    },
    "default_session_engine": {
        "severity": Severity.LOW,
        "rule_name": "Default Session Engine",
        "fix_hint": (
            "Switch SESSION_ENGINE to 'django.contrib.sessions.backends.cache' "
            "or 'django.contrib.sessions.backends.cached_db' for better performance. "
            "Database-backed sessions add a query per request."
        ),
    },
}


class DjangoCheckNormaliser(BaseNormaliser):
    """Convert Django check --deploy output to Finding objects.

    Expected raw_data shape:
    {
      "deploy_output": "System check identified 3 issues...",
      "general_output": "System check identified no issues...",
      "db_checks_output": "...",
      "settings_issues": [
        {"file": "myapp/settings.py", "issue": "debug_enabled", "message": "..."}
      ],
      "deploy_exit_code": 1,
      "general_exit_code": 0
    }
    """

    def normalise(self, raw_data: Any) -> list[Finding]:
        if not isinstance(raw_data, dict):
            return []

        findings: list[Finding] = []

        # --- Parse Django system check output ---
        for output_key in ("deploy_output", "general_output", "db_checks_output"):
            output = raw_data.get(output_key, "")
            if not output:
                continue

            parsed_checks = _parse_django_check_output(output)
            for check in parsed_checks:
                check_id = check.get("id", "")
                level = check.get("level", "WARNING")
                message = check.get("message", "")
                hint = check.get("hint", "")

                # Look up known check IDs
                if check_id in SECURITY_CHECK_IDS:
                    rule_name, severity = SECURITY_CHECK_IDS[check_id]
                else:
                    rule_name = check_id or "Django System Check"
                    severity = (
                        Severity.HIGH if level == "ERROR"
                        else Severity.MEDIUM if level == "WARNING"
                        else Severity.LOW
                    )

                findings.append(Finding(
                    tool="django_check",
                    severity=severity,
                    category=Category.DATABASE,
                    file="<django>",
                    rule_id=f"django/{check_id}" if check_id else "django/check",
                    rule_name=rule_name,
                    message=message,
                    effort=Effort.LOW,
                    fix_hint=hint if hint else f"Address Django check {check_id}: {message}",
                    raw=check,
                ))

        # --- Settings file issues ---
        settings_issues = raw_data.get("settings_issues", [])
        if isinstance(settings_issues, list):
            for issue in settings_issues:
                if not isinstance(issue, dict):
                    continue

                issue_type = issue.get("issue", "")
                file_path = issue.get("file", "<settings>")
                message = issue.get("message", "")

                config = SETTINGS_ISSUE_MAP.get(issue_type, {})
                severity = config.get("severity", Severity.MEDIUM)
                rule_name = config.get("rule_name", "Django Settings Issue")
                fix_hint = config.get("fix_hint", message)

                findings.append(Finding(
                    tool="django_check",
                    severity=severity,
                    category=Category.DATABASE,
                    file=file_path,
                    rule_id=f"django/{issue_type}",
                    rule_name=rule_name,
                    message=message,
                    effort=Effort.LOW,
                    fix_hint=fix_hint,
                    raw=issue,
                ))

        return findings


def _parse_django_check_output(output: str) -> list[dict]:
    """Parse Django system check text output into structured items.

    Django check output format:
    ?: (security.W001) You do not have ...
        HINT: Add 'django.middleware.security.SecurityMiddleware' to ...
    myapp.MyModel: (models.W042) Auto-created primary key ...
    """
    checks: list[dict] = []

    # Pattern: optional_source: (check_id) message
    check_pattern = re.compile(
        r"^(?:(\S+?):\s+)?\(([^)]+)\)\s+(.+)",
        re.MULTILINE,
    )
    hint_pattern = re.compile(r"^\s+HINT:\s+(.+)", re.MULTILINE)

    lines = output.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        match = check_pattern.match(line)
        if match:
            source = match.group(1) or "?"
            check_id = match.group(2)
            message = match.group(3).strip()

            # Determine level from check output context
            level = "WARNING"
            if "ERROR" in output[:output.index(line)] if line in output else "":
                level = "ERROR"

            # Look ahead for HINT
            hint = ""
            if i + 1 < len(lines):
                hint_match = hint_pattern.match(lines[i + 1])
                if hint_match:
                    hint = hint_match.group(1).strip()
                    i += 1

            checks.append({
                "source": source,
                "id": check_id,
                "level": level,
                "message": message,
                "hint": hint,
            })

        i += 1

    return checks
