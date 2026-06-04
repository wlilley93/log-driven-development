"""Tool installer — binary downloads, npm/pip/nodeenv management, checksum verification."""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import venv
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiohttp
import asyncio

VIBERAPID_HOME = Path.home() / ".viberapid"
BIN_DIR = VIBERAPID_HOME / "bin"
VENV_DIR = VIBERAPID_HOME / "venv"
NODE_DIR = VIBERAPID_HOME / "node"
NODE_MODULES_DIR = VIBERAPID_HOME / "node_modules"


def _detect_platform() -> tuple[str, str]:
    """Return (os, arch) normalised for GitHub releases."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    os_name = "linux" if system == "linux" else "darwin" if system == "darwin" else system
    arch = "arm64" if machine in ("aarch64", "arm64") else "x86_64" if machine in ("x86_64", "amd64") else machine

    return os_name, arch


@dataclass
class ToolSpec:
    """Specification for an installable tool."""

    name: str
    kind: str  # "binary", "pip", "npm", "npx", "native"
    pip_package: str | None = None
    npm_package: str | None = None
    binary_name: str | None = None
    github_repo: str | None = None
    version_cmd: list[str] | None = None
    required: bool = True
    env_var: str | None = None
    stack: str | None = None  # "node", "python", or None for universal
    asset_pattern: str | None = None
    extract_binary: str | None = None
    is_load_tester: bool = False
    requires_url: bool = False

    def is_available(self) -> bool:
        if self.env_var and not os.environ.get(self.env_var):
            return False
        return True


# Tool registry — all ~60 tools
TOOLS: list[ToolSpec] = [
    # --- Bundle & JS ---
    ToolSpec(name="depcheck", kind="npm", npm_package="depcheck", version_cmd=["npx", "depcheck", "--version"], stack="node"),
    ToolSpec(name="knip", kind="npm", npm_package="knip", version_cmd=["npx", "knip", "--version"], stack="node"),
    ToolSpec(name="jscpd", kind="npm", npm_package="jscpd", version_cmd=["npx", "jscpd", "--version"], stack="node"),
    ToolSpec(name="bundlephobia", kind="npm", npm_package="bundlephobia-cli", stack="node", required=False),
    ToolSpec(name="cost-of-modules", kind="npm", npm_package="cost-of-modules", stack="node", required=False),
    ToolSpec(name="size-limit", kind="npm", npm_package="size-limit", stack="node", required=False),
    ToolSpec(name="bundlewatch", kind="npm", npm_package="bundlewatch", stack="node", required=False),
    ToolSpec(name="duplicate-packages", kind="npm", npm_package="duplicate-package-checker-webpack-plugin", stack="node", required=False),
    ToolSpec(name="npm-check", kind="npm", npm_package="npm-check", stack="node", required=False),
    ToolSpec(name="npm-check-updates", kind="npm", npm_package="npm-check-updates", version_cmd=["npx", "npm-check-updates", "--version"], stack="node", required=False),

    # --- CSS ---
    ToolSpec(name="purgecss", kind="npm", npm_package="purgecss", version_cmd=["npx", "purgecss", "--version"], stack="node"),
    ToolSpec(name="cssnano", kind="npm", npm_package="cssnano", stack="node", required=False),
    ToolSpec(name="parker", kind="npm", npm_package="parker", stack="node", required=False),
    ToolSpec(name="stylestats", kind="npm", npm_package="stylestats", stack="node", required=False),

    # --- Fonts ---
    ToolSpec(name="glyphhanger", kind="npm", npm_package="glyphhanger", stack="node", required=False),
    ToolSpec(name="fonttools", kind="pip", pip_package="fonttools", stack="python", required=False),

    # --- Images ---
    ToolSpec(name="svgo", kind="npm", npm_package="svgo", version_cmd=["npx", "svgo", "--version"], stack="node"),

    # --- Compression ---
    ToolSpec(name="gzip-size", kind="npm", npm_package="gzip-size-cli", stack="node"),

    # --- HTTP & Network ---
    ToolSpec(name="lighthouse", kind="npm", npm_package="lighthouse", version_cmd=["npx", "lighthouse", "--version"], stack="node", requires_url=True),
    ToolSpec(name="webhint", kind="npm", npm_package="hint", stack="node", requires_url=True, required=False),
    ToolSpec(name="sitespeed", kind="npm", npm_package="sitespeed.io", stack="node", requires_url=True, required=False),
    ToolSpec(
        name="h2spec", kind="binary", binary_name="h2spec",
        github_repo="summerwind/h2spec", version_cmd=["h2spec", "--version"],
        asset_pattern="h2spec_{os}_{arch}.tar.gz", extract_binary="h2spec",
        requires_url=True, required=False,
    ),
    ToolSpec(name="psi", kind="npm", npm_package="psi", stack="node", requires_url=True, required=False),
    ToolSpec(name="yellowlab", kind="npm", npm_package="yellowlab-tools", stack="node", requires_url=True, required=False),
    ToolSpec(name="hstspreload", kind="npm", npm_package="hstspreload", stack="node", requires_url=True, required=False),

    # --- Load Testing ---
    ToolSpec(
        name="k6", kind="binary", binary_name="k6",
        github_repo="grafana/k6", version_cmd=["k6", "version"],
        asset_pattern="k6-v{version}-{os}-{arch}.tar.gz", extract_binary="k6",
        is_load_tester=True, requires_url=True,
    ),
    ToolSpec(name="artillery", kind="npm", npm_package="artillery", version_cmd=["npx", "artillery", "--version"],
             is_load_tester=True, requires_url=True, required=False),
    ToolSpec(name="locust", kind="pip", pip_package="locust", version_cmd=["locust", "--version"],
             stack="python", is_load_tester=True, requires_url=True, required=False),
    ToolSpec(
        name="wrk", kind="native", version_cmd=["wrk", "--version"],
        is_load_tester=True, requires_url=True, required=False,
    ),
    ToolSpec(name="autocannon", kind="npm", npm_package="autocannon", version_cmd=["npx", "autocannon", "--version"],
             is_load_tester=True, requires_url=True, required=False),
    ToolSpec(
        name="vegeta", kind="binary", binary_name="vegeta",
        github_repo="tsenart/vegeta", version_cmd=["vegeta", "--version"],
        is_load_tester=True, requires_url=True, required=False,
    ),
    ToolSpec(
        name="bombardier", kind="binary", binary_name="bombardier",
        github_repo="codesenberg/bombardier", version_cmd=["bombardier", "--version"],
        is_load_tester=True, requires_url=True, required=False,
    ),
    ToolSpec(
        name="hyperfine", kind="binary", binary_name="hyperfine",
        github_repo="sharkdp/hyperfine", version_cmd=["hyperfine", "--version"],
        extract_binary="hyperfine", required=False,
    ),

    # --- Database ---
    ToolSpec(name="sqlfluff", kind="pip", pip_package="sqlfluff", version_cmd=["sqlfluff", "version"], stack="python"),

    # --- Python Runtime ---
    ToolSpec(name="scalene", kind="pip", pip_package="scalene", version_cmd=["scalene", "--version"], stack="python", required=False),
    ToolSpec(name="py-spy", kind="pip", pip_package="py-spy", version_cmd=["py-spy", "--version"], stack="python", required=False),
    ToolSpec(name="pyinstrument", kind="pip", pip_package="pyinstrument", version_cmd=["pyinstrument", "--version"], stack="python", required=False),
    ToolSpec(name="memray", kind="pip", pip_package="memray", version_cmd=["memray", "--version"], stack="python", required=False),

    # --- Node Runtime ---
    ToolSpec(name="clinic", kind="npm", npm_package="clinic", stack="node", required=False),
    ToolSpec(name="0x", kind="npm", npm_package="0x", stack="node", required=False),

    # --- React ---
    ToolSpec(name="million-lint", kind="npm", npm_package="@million/lint", stack="node", required=False),

    # --- Python Dependencies ---
    ToolSpec(name="pipdeptree", kind="pip", pip_package="pipdeptree", version_cmd=["pipdeptree", "--version"], stack="python"),
    ToolSpec(name="deptry", kind="pip", pip_package="deptry", version_cmd=["deptry", "--version"], stack="python"),

    # --- Bundle & JS (additional) ---
    ToolSpec(name="bundle-analyzer", kind="npm", npm_package="webpack-bundle-analyzer", stack="node", required=False),
    ToolSpec(name="source-map-explorer", kind="npm", npm_package="source-map-explorer", stack="node", required=False),
    ToolSpec(name="esbuild-bench", kind="npm", npm_package="esbuild", stack="node", required=False),
    ToolSpec(name="webpack-deadcode", kind="npm", npm_package="webpack", stack="node", required=False),

    # --- CSS (additional) ---
    ToolSpec(name="uncss", kind="npm", npm_package="uncss", stack="node", required=False),
    ToolSpec(name="stylelint-perf", kind="npm", npm_package="stylelint", stack="node", required=False),

    # --- Images (additional) ---
    ToolSpec(name="imagemin", kind="npm", npm_package="imagemin-cli", stack="node", required=False),
    ToolSpec(name="sharp-check", kind="npm", npm_package="sharp", stack="node", required=False),

    # --- Compression (additional) ---
    ToolSpec(name="brotli-size", kind="pip", pip_package="brotli", required=False),
    ToolSpec(name="zopfli", kind="pip", pip_package="zopfli", required=False),

    # --- Database (additional) ---
    ToolSpec(name="pghero", kind="native", version_cmd=["pghero", "--version"], required=False),
    ToolSpec(
        name="pgbadger", kind="native", version_cmd=["pgbadger", "--version"],
        required=False,
    ),
    ToolSpec(
        name="pt-query-digest", kind="native", version_cmd=["pt-query-digest", "--version"],
        required=False,
    ),
    ToolSpec(name="django-check", kind="native", stack="python", required=False),
    ToolSpec(name="prisma-inspector", kind="npm", npm_package="prisma", stack="node", required=False),

    # --- Python Runtime (additional) ---
    ToolSpec(name="py-spy", kind="pip", pip_package="py-spy", version_cmd=["py-spy", "--version"], stack="python", required=False),
    ToolSpec(name="memray", kind="pip", pip_package="memray", version_cmd=["memray", "--version"], stack="python", required=False),
    ToolSpec(name="fil", kind="pip", pip_package="filprofiler", version_cmd=["fil-profile", "--version"], stack="python", required=False),
    ToolSpec(name="austin", kind="pip", pip_package="austin-python", stack="python", required=False),
    ToolSpec(name="speedscope", kind="npm", npm_package="speedscope", required=False),

    # --- Node Runtime (additional) ---
    ToolSpec(name="node-prof", kind="npm", npm_package="node-prof", stack="node", required=False),

    # --- React (additional) ---
    ToolSpec(name="react-scan", kind="npm", npm_package="react-scan", stack="node", required=False),
    ToolSpec(name="why-did-you-render", kind="npm", npm_package="@welldone-software/why-did-you-render", stack="node", required=False),

    # --- Custom (no external tool) ---
    ToolSpec(name="ast-analyser", kind="native"),
]


def get_tool_spec(name: str) -> ToolSpec | None:
    for t in TOOLS:
        if t.name == name:
            return t
    return None


def get_tool_bin(name: str) -> str:
    """Get the executable path for a tool."""
    spec = get_tool_spec(name)
    if not spec:
        return name

    if spec.kind == "binary":
        local = BIN_DIR / (spec.binary_name or spec.name)
        if local.exists():
            return str(local)
        return spec.binary_name or spec.name

    if spec.kind == "pip":
        venv_bin = VENV_DIR / "bin" / (spec.pip_package or spec.name)
        if venv_bin.exists():
            return str(venv_bin)
        return spec.pip_package or spec.name

    if spec.kind == "npm":
        # npm tools invoked via npx
        return spec.npm_package or spec.name

    return spec.binary_name or spec.name


def ensure_venv() -> Path:
    """Ensure the viberapid venv exists."""
    if not VENV_DIR.exists():
        venv.create(str(VENV_DIR), with_pip=True)
    return VENV_DIR


def _pip_install(package: str, upgrade: bool = False) -> tuple[bool, str]:
    """Install a pip package into the viberapid venv."""
    ensure_venv()
    pip = str(VENV_DIR / "bin" / "pip")
    cmd = [pip, "install"]
    if upgrade:
        cmd.append("--upgrade")
    cmd.append(package)

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode == 0:
        return True, f"Installed {package}"
    return False, f"Failed to install {package}: {result.stderr.strip()[:200]}"


def _ensure_node() -> bool:
    """Ensure Node.js is available, installing via nodeenv if needed."""
    if shutil.which("node"):
        return True

    # Try viberapid-managed node
    managed_node = NODE_DIR / "bin" / "node"
    if managed_node.exists():
        return True

    # Install via nodeenv
    try:
        ensure_venv()
        pip = str(VENV_DIR / "bin" / "pip")
        subprocess.run([pip, "install", "nodeenv"], capture_output=True, timeout=120)
        nodeenv_bin = str(VENV_DIR / "bin" / "nodeenv")
        subprocess.run([nodeenv_bin, str(NODE_DIR)], capture_output=True, timeout=300)
        return managed_node.exists()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


async def _fetch_latest_release(session: aiohttp.ClientSession, repo: str) -> dict[str, Any] | None:
    """Fetch latest release info from GitHub API."""
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    headers = {}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status == 200:
                return await resp.json()
    except (aiohttp.ClientError, asyncio.TimeoutError):
        pass
    return None


async def _download_file(session: aiohttp.ClientSession, url: str, dest: Path) -> bool:
    """Download a file."""
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
            if resp.status == 200:
                dest.parent.mkdir(parents=True, exist_ok=True)
                with open(dest, "wb") as f:
                    async for chunk in resp.content.iter_chunked(8192):
                        f.write(chunk)
                return True
    except (aiohttp.ClientError, asyncio.TimeoutError):
        pass
    return False


def _verify_checksum(filepath: Path, expected_sha256: str | None) -> bool:
    """Verify SHA256 checksum if available."""
    if not expected_sha256:
        return True
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest() == expected_sha256


def _extract_binary(archive: Path, binary_name: str, dest_dir: Path) -> Path | None:
    """Extract a binary from a tar.gz or zip archive."""
    dest_dir.mkdir(parents=True, exist_ok=True)

    if archive.name.endswith(".tar.gz") or archive.name.endswith(".tgz"):
        with tarfile.open(archive, "r:gz") as tf:
            for member in tf.getmembers():
                if member.name.endswith(binary_name) or Path(member.name).name == binary_name:
                    tf.extract(member, dest_dir)
                    extracted = dest_dir / member.name
                    final = dest_dir / binary_name
                    if extracted != final:
                        shutil.move(str(extracted), str(final))
                    final.chmod(final.stat().st_mode | stat.S_IEXEC)
                    return final
    elif archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as zf:
            for name in zf.namelist():
                if name.endswith(binary_name) or Path(name).name == binary_name:
                    zf.extract(name, dest_dir)
                    extracted = dest_dir / name
                    final = dest_dir / binary_name
                    if extracted != final:
                        shutil.move(str(extracted), str(final))
                    final.chmod(final.stat().st_mode | stat.S_IEXEC)
                    return final
    else:
        final = dest_dir / binary_name
        shutil.copy2(str(archive), str(final))
        final.chmod(final.stat().st_mode | stat.S_IEXEC)
        return final

    return None


async def install_binary(spec: ToolSpec, session: aiohttp.ClientSession, upgrade: bool = False) -> tuple[bool, str]:
    """Install a binary tool from GitHub releases."""
    if not spec.github_repo:
        return False, f"No GitHub repo configured for {spec.name}"

    existing = BIN_DIR / (spec.binary_name or spec.name)
    if existing.exists() and not upgrade:
        return True, f"{spec.name} already installed"

    release = await _fetch_latest_release(session, spec.github_repo)
    if not release:
        return False, f"Could not fetch release for {spec.name}"

    os_name, arch = _detect_platform()
    version = release["tag_name"].lstrip("v")

    target_asset = None
    checksum_asset = None

    if spec.asset_pattern:
        pattern = spec.asset_pattern.format(os=os_name, arch=arch, version=version)
        for asset in release.get("assets", []):
            name = asset["name"]
            if name == pattern or name.lower() == pattern.lower():
                target_asset = asset
            if name.endswith("checksums.txt") or name.endswith("SHA256SUMS"):
                checksum_asset = asset

    if not target_asset:
        os_aliases = [os_name]
        if os_name == "darwin":
            os_aliases.extend(["macos", "macOS", "osx", "apple"])
        elif os_name == "linux":
            os_aliases.extend(["Linux"])

        arch_aliases = [arch]
        if arch == "arm64":
            arch_aliases.extend(["aarch64", "ARM64"])
        elif arch == "x86_64":
            arch_aliases.extend(["amd64", "64bit", "x64"])

        for asset in release.get("assets", []):
            name = asset["name"]
            name_lower = name.lower()
            if name_lower.endswith(("checksums.txt", "sha256sums", "sha256")):
                if not checksum_asset:
                    checksum_asset = asset
                continue
            if name_lower.endswith((".sig", ".asc", ".pem", ".sigstore.json", ".sbom")):
                continue
            has_os = any(alias.lower() in name_lower for alias in os_aliases)
            has_arch = any(alias.lower() in name_lower for alias in arch_aliases)
            if has_os and has_arch:
                target_asset = asset
                break

    if not target_asset:
        return False, f"No matching asset for {spec.name} ({os_name}/{arch})"

    tmp_dir = VIBERAPID_HOME / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    archive_path = tmp_dir / target_asset["name"]

    if not await _download_file(session, target_asset["browser_download_url"], archive_path):
        return False, f"Download failed for {spec.name}"

    if checksum_asset:
        checksum_path = tmp_dir / checksum_asset["name"]
        if await _download_file(session, checksum_asset["browser_download_url"], checksum_path):
            with open(checksum_path) as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) == 2 and parts[1].strip("*") == target_asset["name"]:
                        if not _verify_checksum(archive_path, parts[0]):
                            archive_path.unlink(missing_ok=True)
                            return False, f"Checksum verification failed for {spec.name}"
                        break

    binary_name = spec.extract_binary or spec.binary_name or spec.name
    result = _extract_binary(archive_path, binary_name, BIN_DIR)

    archive_path.unlink(missing_ok=True)
    shutil.rmtree(tmp_dir, ignore_errors=True)

    if result:
        return True, f"Installed {spec.name} {version}"
    return False, f"Failed to extract {spec.name}"


def check_tool(spec: ToolSpec) -> dict[str, Any]:
    """Check if a tool is installed and get its version."""
    info: dict[str, Any] = {
        "name": spec.name,
        "kind": spec.kind,
        "installed": False,
        "version": None,
        "path": None,
        "required": spec.required,
        "stack": spec.stack,
    }

    if spec.env_var and not os.environ.get(spec.env_var):
        info["skip_reason"] = f"{spec.env_var} not set"
        return info

    if spec.kind == "native" and spec.name == "ast-analyser":
        info["installed"] = True
        info["version"] = "built-in"
        return info

    bin_path = get_tool_bin(spec.name)

    if spec.version_cmd:
        cmd = list(spec.version_cmd)
        if cmd[0] in (spec.binary_name, spec.name, spec.pip_package):
            cmd[0] = bin_path

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                version_str = (result.stdout.strip() or result.stderr.strip()).split("\n")[0]
                info["installed"] = True
                info["version"] = version_str
                info["path"] = shutil.which(cmd[0]) or bin_path
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    return info


async def install_all(
    upgrade: bool = False,
    stack: str | None = None,
    callback=None,
) -> list[tuple[str, bool, str]]:
    """Install all tools. Returns list of (name, success, message)."""
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    results: list[tuple[str, bool, str]] = []

    # Ensure node is available for npm tools
    _ensure_node()

    async with aiohttp.ClientSession() as session:
        for spec in TOOLS:
            # Filter by stack
            if stack and stack != "both" and spec.stack and spec.stack != stack:
                continue

            if spec.kind == "native":
                info = check_tool(spec)
                if info["installed"]:
                    msg = f"{spec.name} available: {info['version']}"
                    results.append((spec.name, True, msg))
                else:
                    results.append((spec.name, False, f"{spec.name} not found (install externally)"))
                if callback:
                    callback(spec.name, results[-1][1], results[-1][2])
                continue

            if spec.kind == "binary":
                ok, msg = await install_binary(spec, session, upgrade=upgrade)
                results.append((spec.name, ok, msg))
                if callback:
                    callback(spec.name, ok, msg)
                continue

            if spec.kind == "pip":
                ok, msg = _pip_install(spec.pip_package or spec.name, upgrade=upgrade)
                results.append((spec.name, ok, msg))
                if callback:
                    callback(spec.name, ok, msg)
                continue

            if spec.kind in ("npm", "npx"):
                results.append((spec.name, True, f"{spec.name} available via npx"))
                if callback:
                    callback(spec.name, True, results[-1][2])
                continue

    return results


def check_all(stack: str | None = None) -> list[dict[str, Any]]:
    """Check status of all tools."""
    results = []
    for spec in TOOLS:
        if stack and stack != "both" and spec.stack and spec.stack != stack:
            continue
        results.append(check_tool(spec))
    return results


def tools_missing(stack: str | None = None) -> list[str]:
    """Return names of required tools that are not installed."""
    missing = []
    for spec in TOOLS:
        if not spec.required:
            continue
        if stack and stack != "both" and spec.stack and spec.stack != stack:
            continue
        if spec.env_var and not os.environ.get(spec.env_var):
            continue
        info = check_tool(spec)
        if not info["installed"]:
            missing.append(spec.name)
    return missing
