"""Tool installer — binary downloads, venv management, checksum verification."""

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

VIBESCAN_HOME = Path.home() / ".vibescan"
BIN_DIR = VIBESCAN_HOME / "bin"
VENV_DIR = VIBESCAN_HOME / "venv"


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
    kind: str  # "binary", "pip", "npm", "native"
    pip_package: str | None = None
    npm_package: str | None = None
    binary_name: str | None = None
    github_repo: str | None = None
    version_cmd: list[str] | None = None
    required: bool = True
    env_var: str | None = None  # required env var (skip if absent)
    deep_only: bool = False
    asset_pattern: str | None = None  # pattern with {os}, {arch}, {version}
    extract_binary: str | None = None  # binary name inside archive

    def is_available(self) -> bool:
        if self.env_var and not os.environ.get(self.env_var):
            return False
        return True


# Tool registry
TOOLS: list[ToolSpec] = [
    # Secret detection
    ToolSpec(
        name="gitleaks",
        kind="binary",
        binary_name="gitleaks",
        github_repo="gitleaks/gitleaks",
        version_cmd=["gitleaks", "version"],
        asset_pattern="gitleaks_{version}_{os}_{arch}.tar.gz",
        extract_binary="gitleaks",
    ),
    ToolSpec(
        name="trufflehog",
        kind="binary",
        binary_name="trufflehog",
        github_repo="trufflesecurity/trufflehog",
        version_cmd=["trufflehog", "--version"],
        asset_pattern="trufflehog_{version}_{os}_{arch}.tar.gz",
        extract_binary="trufflehog",
    ),
    ToolSpec(
        name="detect-secrets",
        kind="pip",
        pip_package="detect-secrets",
        version_cmd=["detect-secrets", "--version"],
    ),
    # SAST
    ToolSpec(
        name="semgrep",
        kind="pip",
        pip_package="semgrep",
        version_cmd=["semgrep", "--version"],
    ),
    ToolSpec(
        name="bandit",
        kind="pip",
        pip_package="bandit",
        version_cmd=["bandit", "--version"],
    ),
    ToolSpec(
        name="codeql",
        kind="native",
        version_cmd=["codeql", "version"],
        required=False,
        deep_only=True,
    ),
    # Dependency/CVE
    ToolSpec(
        name="trivy",
        kind="binary",
        binary_name="trivy",
        github_repo="aquasecurity/trivy",
        version_cmd=["trivy", "version"],
        asset_pattern=None,  # naming varies by platform; loose matching handles it
        extract_binary="trivy",
    ),
    ToolSpec(
        name="grype",
        kind="binary",
        binary_name="grype",
        github_repo="anchore/grype",
        version_cmd=["grype", "version"],
        asset_pattern="grype_{version}_{os}_{arch}.tar.gz",
        extract_binary="grype",
    ),
    ToolSpec(
        name="npm-audit",
        kind="native",
        version_cmd=["npm", "--version"],
    ),
    ToolSpec(
        name="pip-audit",
        kind="pip",
        pip_package="pip-audit",
        version_cmd=["pip-audit", "--version"],
    ),
    ToolSpec(
        name="snyk",
        kind="binary",
        binary_name="snyk",
        github_repo="snyk/cli",
        version_cmd=["snyk", "version"],
        env_var="SNYK_TOKEN",
        required=False,
        asset_pattern=None,  # naming varies by platform; loose matching handles it
    ),
    # IaC
    ToolSpec(
        name="kics",
        kind="binary",
        binary_name="kics",
        github_repo="Checkmarx/kics",
        version_cmd=["kics", "version"],
        asset_pattern=None,  # naming varies by platform; loose matching handles it
        extract_binary="kics",
    ),
    # Licence
    ToolSpec(
        name="license-checker",
        kind="npm",
        npm_package="license-checker",
        version_cmd=["npx", "license-checker", "--version"],
        required=False,
    ),
    ToolSpec(
        name="pip-licenses",
        kind="pip",
        pip_package="pip-licenses",
        version_cmd=["pip-licenses", "--version"],
        required=False,
    ),
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

    return spec.binary_name or spec.name


def ensure_venv() -> Path:
    """Ensure the vibescan venv exists."""
    if not VENV_DIR.exists():
        venv.create(str(VENV_DIR), with_pip=True)
    return VENV_DIR


def _pip_install(package: str, upgrade: bool = False) -> tuple[bool, str]:
    """Install a pip package into the vibescan venv."""
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
        # Raw binary (e.g. snyk)
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

    # Find matching asset
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
        # Try looser matching with platform aliases
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
            # Collect checksum files
            if name_lower.endswith(("checksums.txt", "sha256sums", "sha256")):
                if not checksum_asset:
                    checksum_asset = asset
                continue
            # Skip signature/metadata files
            if name_lower.endswith((".sig", ".asc", ".pem", ".sigstore.json", ".sbom")):
                continue
            has_os = any(alias.lower() in name_lower for alias in os_aliases)
            has_arch = any(alias.lower() in name_lower for alias in arch_aliases)
            if has_os and has_arch:
                target_asset = asset
                break

    if not target_asset:
        return False, f"No matching asset for {spec.name} ({os_name}/{arch})"

    # Download
    tmp_dir = VIBESCAN_HOME / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    archive_path = tmp_dir / target_asset["name"]

    if not await _download_file(session, target_asset["browser_download_url"], archive_path):
        return False, f"Download failed for {spec.name}"

    # Verify checksum if available
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

    # Extract
    binary_name = spec.extract_binary or spec.binary_name or spec.name
    result = _extract_binary(archive_path, binary_name, BIN_DIR)

    # Cleanup
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
        "deep_only": spec.deep_only,
    }

    if spec.env_var and not os.environ.get(spec.env_var):
        info["skip_reason"] = f"{spec.env_var} not set"
        return info

    bin_path = get_tool_bin(spec.name)

    if spec.version_cmd:
        cmd = list(spec.version_cmd)
        # Replace tool name with resolved path
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


async def install_all(upgrade: bool = False, callback=None) -> list[tuple[str, bool, str]]:
    """Install all tools. Returns list of (name, success, message)."""
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    results: list[tuple[str, bool, str]] = []

    async with aiohttp.ClientSession() as session:
        for spec in TOOLS:
            if spec.kind == "native":
                info = check_tool(spec)
                if info["installed"]:
                    msg = f"{spec.name} available (native): {info['version']}"
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

            if spec.kind == "npm":
                # npm tools are invoked via npx, no explicit install needed
                results.append((spec.name, True, f"{spec.name} available via npx"))
                if callback:
                    callback(spec.name, True, results[-1][2])
                continue

    return results


def check_all() -> list[dict[str, Any]]:
    """Check status of all tools."""
    return [check_tool(spec) for spec in TOOLS]


def tools_missing() -> list[str]:
    """Return names of required tools that are not installed."""
    missing = []
    for spec in TOOLS:
        if not spec.required:
            continue
        if spec.deep_only:
            continue
        if spec.env_var and not os.environ.get(spec.env_var):
            continue
        info = check_tool(spec)
        if not info["installed"]:
            missing.append(spec.name)
    return missing
