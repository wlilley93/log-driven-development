"""rate_limit_checker — custom runner checking rate limiting on auth endpoints."""

from __future__ import annotations

import time
import urllib.request
import urllib.error
from urllib.parse import urlparse

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner

# Auth-related endpoints to check for rate limiting
_AUTH_ENDPOINTS = [
    ("/login", "POST"),
    ("/api/auth/login", "POST"),
    ("/api/auth/signin", "POST"),
    ("/api/login", "POST"),
    ("/auth/login", "POST"),
    ("/register", "POST"),
    ("/api/auth/register", "POST"),
    ("/api/register", "POST"),
    ("/api/auth/forgot-password", "POST"),
    ("/api/auth/reset-password", "POST"),
    ("/api/csrf", "GET"),
]

# Threshold: if this many consecutive requests succeed within this window,
# rate limiting is likely absent
_REQUEST_COUNT = 20
_WINDOW_SECONDS = 5.0


class RateLimitCheckerRunner(AsyncToolRunner):
    name = "rate_limit_checker"
    requires_url = True

    def should_run(self) -> bool:
        if not self.config.url:
            self.skip_reason = "requires --url"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        findings: list[Finding] = []
        base_url = self.config.url.rstrip("/")
        parsed = urlparse(base_url)
        is_production = self._is_production(parsed.hostname or "")

        for path, method in _AUTH_ENDPOINTS:
            url = f"{base_url}{path}"

            # First check if endpoint exists (any response other than 404)
            if not self._endpoint_exists(url, method):
                continue

            # Send rapid requests to check for rate limiting
            rate_limited = self._check_rate_limit(url, method)

            if not rate_limited:
                is_sensitive = any(kw in path.lower() for kw in ("login", "signin", "password", "register"))
                severity = Severity.HIGH if is_sensitive else Severity.MEDIUM
                blocks = is_sensitive and is_production

                findings.append(Finding(
                    tool=self.name,
                    severity=severity,
                    category=Category.CORS_API,
                    file=url,
                    rule_id="no-rate-limit-auth",
                    rule_name="No Rate Limiting on Auth Endpoint",
                    message=(
                        f"No rate limiting detected on {path} after {_REQUEST_COUNT} "
                        f"rapid requests — brute force attacks possible"
                    ),
                    blocks_deploy=blocks,
                    effort=Effort.MEDIUM,
                    fix_hint=(
                        f"Add rate limiting to {path}. "
                        "Use a middleware like express-rate-limit, "
                        "Django Ratelimit, or a reverse proxy (nginx limit_req)"
                    ),
                ))

        status = ToolStatus.SUCCESS
        return ToolResult(tool=self.name, status=status, findings=findings)

    def _endpoint_exists(self, url: str, method: str) -> bool:
        """Check if an endpoint exists (returns any status other than 404/405)."""
        try:
            req = urllib.request.Request(url, method=method if method == "GET" else "GET")
            req.add_header("User-Agent", "vibedeploy-rate-limit-checker/1.0")
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status != 404
        except urllib.error.HTTPError as e:
            # 404 means endpoint doesn't exist; 405 means wrong method but endpoint exists
            return e.code not in (404,)
        except (urllib.error.URLError, OSError, TimeoutError):
            return False

    def _check_rate_limit(self, url: str, method: str) -> bool:
        """Send rapid requests and check if rate limiting kicks in.

        Returns True if rate limiting was detected, False otherwise.
        """
        success_count = 0
        rate_limit_detected = False
        start = time.monotonic()

        # Use a dummy body for POST requests
        body = b'{"email":"test@test.com","password":"test123"}' if method == "POST" else None

        for i in range(_REQUEST_COUNT):
            elapsed = time.monotonic() - start
            if elapsed > _WINDOW_SECONDS:
                break

            try:
                req = urllib.request.Request(
                    url,
                    method=method,
                    data=body,
                )
                req.add_header("User-Agent", "vibedeploy-rate-limit-checker/1.0")
                req.add_header("Content-Type", "application/json")

                with urllib.request.urlopen(req, timeout=5) as resp:
                    # Rate limiting often returns 429 but some servers use 403
                    if resp.status == 429:
                        rate_limit_detected = True
                        break
                    success_count += 1

            except urllib.error.HTTPError as e:
                if e.code == 429:
                    rate_limit_detected = True
                    break
                if e.code == 403 and i > 5:
                    # Likely rate limiting via 403
                    rate_limit_headers = (
                        e.headers.get("Retry-After")
                        or e.headers.get("X-RateLimit-Remaining")
                        or e.headers.get("X-Rate-Limit-Remaining")
                        or e.headers.get("RateLimit-Remaining")
                    )
                    if rate_limit_headers is not None:
                        rate_limit_detected = True
                        break
                # Other errors (400, 401, etc.) still count as successful delivery
                success_count += 1

            except (urllib.error.URLError, OSError, TimeoutError):
                # Connection errors after several successes may indicate rate limiting
                if success_count > 5:
                    rate_limit_detected = True
                break

        # Also check response headers for rate limit indicators
        if not rate_limit_detected and success_count >= _REQUEST_COUNT - 2:
            # All requests succeeded — no rate limiting
            return False

        return rate_limit_detected

    @staticmethod
    def _is_production(hostname: str) -> bool:
        """Heuristic to determine if the target is a production environment."""
        dev_indicators = ("localhost", "127.0.0.1", "0.0.0.0", "dev.", "staging.", "test.", "local")
        return not any(ind in hostname.lower() for ind in dev_indicators)
