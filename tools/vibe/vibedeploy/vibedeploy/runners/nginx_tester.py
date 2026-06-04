"""nginx_tester runner — validate nginx configuration with nginx -t."""

from __future__ import annotations

from vibedeploy.models import ToolResult, ToolStatus
from vibedeploy.normalisers.nginx_tester import NginxTesterNormaliser
from vibedeploy.runners.base import AsyncToolRunner


class NginxTesterRunner(AsyncToolRunner):
    name = "nginx_tester"

    @property
    def bin_path(self) -> str:
        from vibedeploy.installer import get_tool_bin
        path = get_tool_bin(self.name)
        if path == self.name:
            return "nginx"
        return path

    def should_run(self) -> bool:
        if not self._tool_exists():
            self.skip_reason = "nginx not installed"
            return False
        if not self._file_exists("nginx.conf", "conf/nginx.conf", "etc/nginx/nginx.conf"):
            nginx_files = self._scan_files("**/*.conf")
            has_nginx_conf = any("nginx" in str(f).lower() for f in nginx_files)
            if not has_nginx_conf:
                self.skip_reason = "no nginx configuration found"
                return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        # Find the nginx config file
        config_file = None
        for candidate in ("nginx.conf", "conf/nginx.conf", "etc/nginx/nginx.conf"):
            if self._file_exists(candidate):
                config_file = candidate
                break

        if not config_file:
            # Search for any nginx config
            nginx_files = self._scan_files("**/*.conf")
            for f in nginx_files:
                if "nginx" in str(f).lower():
                    try:
                        config_file = str(f.relative_to(self.target))
                    except ValueError:
                        config_file = str(f)
                    break

        if not config_file:
            return ToolResult(tool=self.name, status=ToolStatus.SKIPPED)

        cmd = [self.bin_path, "-t", "-c", config_file]

        try:
            result = self._exec(cmd, timeout=30)
        except Exception as e:
            return self._make_error_result(f"nginx -t execution failed: {e}")

        # nginx -t output goes to stderr
        output = result.stderr.strip() or result.stdout.strip()
        normaliser = NginxTesterNormaliser()
        findings = normaliser.normalise({
            "output": output,
            "returncode": result.returncode,
            "config_file": config_file,
        })

        status = ToolStatus.SUCCESS if result.returncode == 0 else ToolStatus.PARTIAL

        return ToolResult(
            tool=self.name,
            status=status,
            findings=findings,
        )
