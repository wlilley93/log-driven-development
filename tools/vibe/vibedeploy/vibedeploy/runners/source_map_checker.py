"""source_map_checker — custom runner checking for source maps in build output."""

from __future__ import annotations

import urllib.request
import urllib.error
from pathlib import Path

from vibedeploy.models import Category, Effort, Finding, Severity, ToolResult, ToolStatus
from vibedeploy.runners.base import AsyncToolRunner

# Directories where build output typically lives
_BUILD_DIRS = ["build", "dist", ".next", "public", "out", "_next", "static"]

# Source map file extensions
_MAP_PATTERNS = ["*.map", "*.js.map", "*.css.map"]


class SourceMapCheckerRunner(AsyncToolRunner):
    name = "source_map_checker"

    def should_run(self) -> bool:
        # Always runs — no external binary needed
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        findings: list[Finding] = []
        target = Path(self.target)

        # Step 1: Scan local build directories for .map files
        map_files: list[Path] = []
        for build_dir in _BUILD_DIRS:
            build_path = target / build_dir
            if not build_path.exists():
                continue
            for pattern in _MAP_PATTERNS:
                map_files.extend(build_path.rglob(pattern))

        # Also check top-level for stray map files
        for pattern in _MAP_PATTERNS:
            for f in target.glob(pattern):
                if f not in map_files:
                    map_files.append(f)

        # Consolidate: if many map files, report a summary instead of one finding per file
        if len(map_files) > 20:
            total_size = 0
            for mf in map_files:
                try:
                    total_size += mf.stat().st_size
                except OSError:
                    pass
            total_mb = total_size / (1024 * 1024)
            dirs_found = sorted({str(mf.parent.relative_to(self.target)) for mf in map_files[:100]})
            findings.append(Finding(
                tool=self.name,
                severity=Severity.MEDIUM,
                category=Category.BUILD,
                file=dirs_found[0] if dirs_found else "build/",
                rule_id="source-map-in-build",
                rule_name="Source Maps in Build Output",
                message=f"{len(map_files)} source map files found ({total_mb:.1f} MB total) in: {', '.join(dirs_found[:5])}",
                blocks_deploy=False,
                effort=Effort.TRIVIAL,
                fix_hint="Remove source maps from production builds or ensure they are not publicly served",
                fix_command="find build dist .next -name '*.map' -delete",
            ))
        else:
            for map_file in map_files:
                rel_path = str(map_file.relative_to(self.target))
                try:
                    size_kb = map_file.stat().st_size / 1024
                except OSError:
                    size_kb = 0
                findings.append(Finding(
                    tool=self.name,
                    severity=Severity.MEDIUM,
                    category=Category.BUILD,
                    file=rel_path,
                    rule_id="source-map-in-build",
                    rule_name="Source Map in Build Output",
                    message=f"Source map file found in build output: {rel_path} ({size_kb:.0f} KB)",
                    blocks_deploy=False,
                    effort=Effort.TRIVIAL,
                    fix_hint="Remove source maps from production builds or ensure they are not publicly served",
                    fix_command="find build dist .next -name '*.map' -delete",
                ))

        # Step 2: Check for sourceMappingURL references in JS/CSS bundles
        # Sample up to 200 JS files to avoid timeout on large projects
        url_ref_count = 0
        url_ref_dirs: set[str] = set()
        _MAX_URL_SAMPLES = 200

        for build_dir in _BUILD_DIRS:
            build_path = target / build_dir
            if not build_path.exists():
                continue
            sampled = 0
            for js_file in build_path.rglob("*.js"):
                if sampled >= _MAX_URL_SAMPLES:
                    break
                sampled += 1
                try:
                    size = js_file.stat().st_size
                    if size == 0:
                        continue
                    with open(js_file, "r", errors="replace") as f:
                        if size > 500:
                            f.seek(max(0, size - 500))
                        tail = f.read()
                    if "sourceMappingURL=" in tail:
                        url_ref_count += 1
                        url_ref_dirs.add(str(js_file.parent.relative_to(self.target)))
                except OSError:
                    continue

        if url_ref_count > 0:
            findings.append(Finding(
                tool=self.name,
                severity=Severity.LOW,
                category=Category.BUILD,
                file=sorted(url_ref_dirs)[0] if url_ref_dirs else "build/",
                rule_id="source-mapping-url-ref",
                rule_name="sourceMappingURL Reference",
                message=f"{url_ref_count} JS bundles contain sourceMappingURL references in: {', '.join(sorted(url_ref_dirs)[:5])}",
                blocks_deploy=False,
                effort=Effort.TRIVIAL,
                fix_hint="Strip sourceMappingURL comments from production bundles",
            ))

        # Step 3: If --url provided, check if .map files are publicly accessible
        if self.config.url:
            url_findings = self._check_remote_maps(self.config.url)
            findings.extend(url_findings)

        status = ToolStatus.SUCCESS
        return ToolResult(tool=self.name, status=status, findings=findings)

    def _check_remote_maps(self, base_url: str) -> list[Finding]:
        """Check if source maps are publicly accessible via HTTP."""
        findings: list[Finding] = []
        base_url = base_url.rstrip("/")

        # Common paths where source maps might be exposed
        test_paths = [
            "/main.js.map",
            "/app.js.map",
            "/bundle.js.map",
            "/vendor.js.map",
            "/static/js/main.js.map",
            "/static/js/bundle.js.map",
            "/_next/static/chunks/main.js.map",
            "/_next/static/chunks/webpack.js.map",
            "/assets/index.js.map",
            "/dist/bundle.js.map",
        ]

        for path in test_paths:
            url = f"{base_url}{path}"
            try:
                req = urllib.request.Request(url, method="HEAD")
                req.add_header("User-Agent", "vibedeploy-source-map-checker/1.0")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    content_type = resp.headers.get("Content-Type", "")
                    if resp.status == 200 and (
                        "json" in content_type
                        or "javascript" in content_type
                        or "octet-stream" in content_type
                        or path.endswith(".map")
                    ):
                        findings.append(Finding(
                            tool=self.name,
                            severity=Severity.HIGH,
                            category=Category.BUILD,
                            file=url,
                            rule_id="source-map-publicly-served",
                            rule_name="Source Map Publicly Accessible",
                            message=f"Source map is publicly accessible at {url} — source code exposed",
                            blocks_deploy=True,
                            effort=Effort.TRIVIAL,
                            fix_hint=(
                                "Block access to .map files in your web server config "
                                "(nginx: location ~* \\.map$ { return 404; })"
                            ),
                        ))
            except (urllib.error.HTTPError, urllib.error.URLError, OSError, TimeoutError):
                continue

        return findings
