"""Tool installer — binary downloads, venv management, checksum verification."""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import stat
import subprocess
import tarfile
import venv
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiohttp
import asyncio

VIBEDEPLOY_HOME = Path.home() / ".vibedeploy"
BIN_DIR = VIBEDEPLOY_HOME / "bin"
VENV_DIR = VIBEDEPLOY_HOME / "venv"


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
    kind: str  # "binary", "pip", "npm", "native", "custom"
    pip_package: str | None = None
    npm_package: str | None = None
    binary_name: str | None = None
    github_repo: str | None = None
    version_cmd: list[str] | None = None
    required: bool = False
    env_var: str | None = None
    requires_url: bool = False
    requires_docker: bool = False
    requires_k8s: bool = False
    requires_cloud: bool = False
    asset_pattern: str | None = None
    extract_binary: str | None = None

    def is_available(self) -> bool:
        if self.env_var and not os.environ.get(self.env_var):
            return False
        return True


# ────────────────────────────────────────────────────────────────
# Tool registry — 84 tools across 16 categories
# ────────────────────────────────────────────────────────────────

TOOLS: list[ToolSpec] = [
    # ── Env & Secrets (6) ──
    ToolSpec(
        name="dotenv_linter",
        kind="binary",
        binary_name="dotenv-linter",
        github_repo="dotenv-linter/dotenv-linter",
        version_cmd=["dotenv-linter", "--version"],
        asset_pattern="dotenv-linter-{os}-{arch}.tar.gz",
        extract_binary="dotenv-linter",
    ),
    ToolSpec(
        name="detect_secrets",
        kind="pip",
        pip_package="detect-secrets",
        version_cmd=["detect-secrets", "--version"],
    ),
    ToolSpec(
        name="git_secrets",
        kind="native",
        version_cmd=["git", "secrets", "--list"],
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
        name="chamber",
        kind="binary",
        binary_name="chamber",
        github_repo="segmentio/chamber",
        version_cmd=["chamber", "version"],
        requires_cloud=True,
    ),
    ToolSpec(
        name="env_validator",
        kind="custom",
    ),

    # ── Database Safety (10) ──
    ToolSpec(
        name="squawk",
        kind="binary",
        binary_name="squawk",
        github_repo="sbdchd/squawk",
        version_cmd=["squawk", "--version"],
        asset_pattern="squawk-{os}-{arch}.tar.gz",
        extract_binary="squawk",
    ),
    ToolSpec(
        name="migra",
        kind="pip",
        pip_package="migra",
        version_cmd=["migra", "--version"],
    ),
    ToolSpec(
        name="sqlfluff",
        kind="pip",
        pip_package="sqlfluff",
        version_cmd=["sqlfluff", "version"],
    ),
    ToolSpec(
        name="atlas",
        kind="binary",
        binary_name="atlas",
        github_repo="ariga/atlas",
        version_cmd=["atlas", "version"],
    ),
    ToolSpec(
        name="pgtap",
        kind="native",
        version_cmd=["pg_prove", "--version"],
    ),
    ToolSpec(
        name="pg_prove",
        kind="native",
        version_cmd=["pg_prove", "--version"],
    ),
    ToolSpec(
        name="flyway",
        kind="native",
        version_cmd=["flyway", "--version"],
    ),
    ToolSpec(
        name="liquibase",
        kind="native",
        version_cmd=["liquibase", "--version"],
    ),
    ToolSpec(
        name="rls_checker",
        kind="custom",
    ),
    ToolSpec(
        name="connection_pool",
        kind="custom",
    ),

    # ── Docker & Containers (7) ──
    ToolSpec(
        name="hadolint",
        kind="binary",
        binary_name="hadolint",
        github_repo="hadolint/hadolint",
        version_cmd=["hadolint", "--version"],
        requires_docker=True,
    ),
    ToolSpec(
        name="dockle",
        kind="binary",
        binary_name="dockle",
        github_repo="goodwithtech/dockle",
        version_cmd=["dockle", "--version"],
        asset_pattern="dockle_{version}_{os}_{arch}.tar.gz",
        extract_binary="dockle",
        requires_docker=True,
    ),
    ToolSpec(
        name="dive",
        kind="binary",
        binary_name="dive",
        github_repo="wagoodman/dive",
        version_cmd=["dive", "version"],
        asset_pattern="dive_{version}_{os}_{arch}.tar.gz",
        extract_binary="dive",
        requires_docker=True,
    ),
    ToolSpec(
        name="docker_bench",
        kind="native",
        version_cmd=["docker", "version"],
        requires_docker=True,
    ),
    ToolSpec(
        name="trivy_image",
        kind="binary",
        binary_name="trivy",
        github_repo="aquasecurity/trivy",
        version_cmd=["trivy", "version"],
        extract_binary="trivy",
        requires_docker=True,
    ),
    ToolSpec(
        name="cosign",
        kind="binary",
        binary_name="cosign",
        github_repo="sigstore/cosign",
        version_cmd=["cosign", "version"],
        requires_docker=True,
    ),
    ToolSpec(
        name="syft",
        kind="binary",
        binary_name="syft",
        github_repo="anchore/syft",
        version_cmd=["syft", "version"],
        asset_pattern="syft_{version}_{os}_{arch}.tar.gz",
        extract_binary="syft",
        requires_docker=True,
    ),

    # ── Infrastructure as Code (8) ──
    ToolSpec(
        name="checkov",
        kind="pip",
        pip_package="checkov",
        version_cmd=["checkov", "--version"],
    ),
    ToolSpec(
        name="tfsec",
        kind="binary",
        binary_name="tfsec",
        github_repo="aquasecurity/tfsec",
        version_cmd=["tfsec", "--version"],
        asset_pattern="tfsec-{os}-{arch}",
    ),
    ToolSpec(
        name="terrascan",
        kind="binary",
        binary_name="terrascan",
        github_repo="tenable/terrascan",
        version_cmd=["terrascan", "version"],
    ),
    ToolSpec(
        name="cfn_lint",
        kind="pip",
        pip_package="cfn-lint",
        version_cmd=["cfn-lint", "--version"],
    ),
    ToolSpec(
        name="ansible_lint",
        kind="pip",
        pip_package="ansible-lint",
        version_cmd=["ansible-lint", "--version"],
    ),
    ToolSpec(
        name="helm_lint",
        kind="native",
        version_cmd=["helm", "version"],
    ),
    ToolSpec(
        name="conftest",
        kind="binary",
        binary_name="conftest",
        github_repo="open-policy-agent/conftest",
        version_cmd=["conftest", "--version"],
    ),
    ToolSpec(
        name="kics",
        kind="binary",
        binary_name="kics",
        github_repo="Checkmarx/kics",
        version_cmd=["kics", "version"],
        extract_binary="kics",
    ),

    # ── Kubernetes (9) ──
    ToolSpec(
        name="kubesec",
        kind="binary",
        binary_name="kubesec",
        github_repo="controlplaneio/kubesec",
        version_cmd=["kubesec", "version"],
        requires_k8s=True,
    ),
    ToolSpec(
        name="kubeval",
        kind="binary",
        binary_name="kubeval",
        github_repo="instrumenta/kubeval",
        version_cmd=["kubeval", "--version"],
        requires_k8s=True,
    ),
    ToolSpec(
        name="polaris",
        kind="binary",
        binary_name="polaris",
        github_repo="FairwindsOps/polaris",
        version_cmd=["polaris", "version"],
        requires_k8s=True,
    ),
    ToolSpec(
        name="popeye",
        kind="binary",
        binary_name="popeye",
        github_repo="derailed/popeye",
        version_cmd=["popeye", "version"],
        requires_k8s=True,
    ),
    ToolSpec(
        name="pluto",
        kind="binary",
        binary_name="pluto",
        github_repo="FairwindsOps/pluto",
        version_cmd=["pluto", "version"],
        requires_k8s=True,
    ),
    ToolSpec(
        name="nova",
        kind="binary",
        binary_name="nova",
        github_repo="FairwindsOps/nova",
        version_cmd=["nova", "version"],
        requires_k8s=True,
    ),
    ToolSpec(
        name="rbac_lookup",
        kind="binary",
        binary_name="rbac-lookup",
        github_repo="FairwindsOps/rbac-lookup",
        version_cmd=["rbac-lookup", "--version"],
        requires_k8s=True,
    ),
    ToolSpec(
        name="kube_score",
        kind="binary",
        binary_name="kube-score",
        github_repo="zegl/kube-score",
        version_cmd=["kube-score", "version"],
        requires_k8s=True,
    ),
    ToolSpec(
        name="kubectl_neat",
        kind="native",
        version_cmd=["kubectl", "neat", "--version"],
        requires_k8s=True,
    ),

    # ── SSL/TLS (5) ──
    ToolSpec(
        name="testssl",
        kind="native",
        version_cmd=["testssl.sh", "--version"],
        requires_url=True,
    ),
    ToolSpec(
        name="certigo",
        kind="binary",
        binary_name="certigo",
        github_repo="square/certigo",
        version_cmd=["certigo", "--version"],
    ),
    ToolSpec(
        name="ssl_checker",
        kind="custom",
        requires_url=True,
    ),
    ToolSpec(
        name="ssllabs",
        kind="custom",
        requires_url=True,
    ),
    ToolSpec(
        name="mkcert",
        kind="binary",
        binary_name="mkcert",
        github_repo="FiloSottile/mkcert",
        version_cmd=["mkcert", "--version"],
    ),

    # ── HTTP Headers (5) ──
    ToolSpec(
        name="observatory",
        kind="custom",
        requires_url=True,
    ),
    ToolSpec(
        name="securityheaders",
        kind="custom",
        requires_url=True,
    ),
    ToolSpec(
        name="webhint",
        kind="npm",
        npm_package="hint",
        version_cmd=["npx", "hint", "--version"],
        requires_url=True,
    ),
    ToolSpec(
        name="mixed_content",
        kind="custom",
        requires_url=True,
    ),
    ToolSpec(
        name="redirect_checker",
        kind="custom",
        requires_url=True,
    ),

    # ── Cloud Config (7) ──
    ToolSpec(
        name="prowler",
        kind="pip",
        pip_package="prowler",
        version_cmd=["prowler", "--version"],
        requires_cloud=True,
    ),
    ToolSpec(
        name="scoutsuite",
        kind="pip",
        pip_package="ScoutSuite",
        version_cmd=["scout", "--version"],
        requires_cloud=True,
    ),
    ToolSpec(
        name="steampipe",
        kind="binary",
        binary_name="steampipe",
        github_repo="turbot/steampipe",
        version_cmd=["steampipe", "--version"],
        requires_cloud=True,
    ),
    ToolSpec(
        name="cloudsplaining",
        kind="pip",
        pip_package="cloudsplaining",
        version_cmd=["cloudsplaining", "--version"],
        requires_cloud=True,
    ),
    ToolSpec(
        name="parliament",
        kind="pip",
        pip_package="parliament",
        version_cmd=["parliament", "--version"],
        requires_cloud=True,
    ),
    ToolSpec(
        name="aws_vault",
        kind="binary",
        binary_name="aws-vault",
        github_repo="99designs/aws-vault",
        version_cmd=["aws-vault", "--version"],
        requires_cloud=True,
    ),
    ToolSpec(
        name="s3scanner",
        kind="binary",
        binary_name="s3scanner",
        github_repo="sa7mon/S3Scanner",
        version_cmd=["s3scanner", "--version"],
        requires_cloud=True,
    ),

    # ── CORS & API (2) ──
    ToolSpec(
        name="cors_checker",
        kind="custom",
        requires_url=True,
    ),
    ToolSpec(
        name="rate_limit_checker",
        kind="custom",
        requires_url=True,
    ),

    # ── Build & Production (3) ──
    ToolSpec(
        name="source_map_checker",
        kind="custom",
    ),
    ToolSpec(
        name="debug_mode_checker",
        kind="custom",
    ),
    ToolSpec(
        name="dependency_audit",
        kind="native",
        version_cmd=["npm", "--version"],
    ),

    # ── Process & Runtime (5) ──
    ToolSpec(
        name="health_check_scanner",
        kind="custom",
    ),
    ToolSpec(
        name="graceful_shutdown",
        kind="custom",
    ),
    ToolSpec(
        name="process_supervisor",
        kind="custom",
    ),
    ToolSpec(
        name="pm2_validator",
        kind="custom",
    ),
    ToolSpec(
        name="procfile_linter",
        kind="custom",
    ),

    # ── Logging & Observability (3) ──
    ToolSpec(
        name="otel_checker",
        kind="custom",
    ),
    ToolSpec(
        name="log_level_checker",
        kind="custom",
    ),
    ToolSpec(
        name="sentry_checker",
        kind="custom",
    ),

    # ── Config Validation (2) ──
    ToolSpec(
        name="yamllint",
        kind="pip",
        pip_package="yamllint",
        version_cmd=["yamllint", "--version"],
    ),
    ToolSpec(
        name="jsonlint",
        kind="npm",
        npm_package="jsonlint",
        version_cmd=["npx", "jsonlint", "--version"],
    ),

    # ── Supply Chain (6) ──
    ToolSpec(
        name="ossf_scorecard",
        kind="binary",
        binary_name="scorecard",
        github_repo="ossf/scorecard",
        version_cmd=["scorecard", "version"],
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
        name="pip_audit",
        kind="pip",
        pip_package="pip-audit",
        version_cmd=["pip-audit", "--version"],
    ),
    ToolSpec(
        name="npm_audit_prod",
        kind="native",
        version_cmd=["npm", "--version"],
    ),
    ToolSpec(
        name="license_checker",
        kind="npm",
        npm_package="license-checker",
        version_cmd=["npx", "license-checker", "--version"],
    ),
    ToolSpec(
        name="pip_licenses",
        kind="pip",
        pip_package="pip-licenses",
        version_cmd=["pip-licenses", "--version"],
    ),

    # ── Web Server (3) ──
    ToolSpec(
        name="nginx_tester",
        kind="native",
        version_cmd=["nginx", "-v"],
    ),
    ToolSpec(
        name="gixy",
        kind="pip",
        pip_package="gixy",
        version_cmd=["gixy", "--version"],
    ),
    ToolSpec(
        name="nginx_analyser",
        kind="custom",
    ),

    # ── DNS & Networking (3) ──
    ToolSpec(
        name="dnsx",
        kind="binary",
        binary_name="dnsx",
        github_repo="projectdiscovery/dnsx",
        version_cmd=["dnsx", "-version"],
    ),
    ToolSpec(
        name="httpx_probe",
        kind="binary",
        binary_name="httpx",
        github_repo="projectdiscovery/httpx",
        version_cmd=["httpx", "-version"],
        requires_url=True,
    ),
    ToolSpec(
        name="nmap_safe",
        kind="native",
        version_cmd=["nmap", "--version"],
        requires_url=True,
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
    """Ensure the vibedeploy venv exists."""
    if not VENV_DIR.exists():
        venv.create(str(VENV_DIR), with_pip=True)
    return VENV_DIR


def _pip_install(package: str, upgrade: bool = False) -> tuple[bool, str]:
    """Install a pip package into the vibedeploy venv."""
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
        # Raw binary
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
        # Loose matching with platform aliases
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

    # Download
    tmp_dir = VIBEDEPLOY_HOME / "tmp"
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
        "requires_url": spec.requires_url,
        "requires_docker": spec.requires_docker,
        "requires_k8s": spec.requires_k8s,
        "requires_cloud": spec.requires_cloud,
    }

    if spec.kind == "custom":
        info["installed"] = True
        info["version"] = "built-in"
        return info

    if spec.env_var and not os.environ.get(spec.env_var):
        info["skip_reason"] = f"{spec.env_var} not set"
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


async def install_all(upgrade: bool = False, callback=None) -> list[tuple[str, bool, str]]:
    """Install all tools. Returns list of (name, success, message)."""
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    results: list[tuple[str, bool, str]] = []

    async with aiohttp.ClientSession() as session:
        for spec in TOOLS:
            if spec.kind == "custom":
                results.append((spec.name, True, f"{spec.name} (built-in)"))
                if callback:
                    callback(spec.name, True, results[-1][2])
                continue

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
        if spec.kind == "custom":
            continue
        if spec.env_var and not os.environ.get(spec.env_var):
            continue
        info = check_tool(spec)
        if not info["installed"]:
            missing.append(spec.name)
    return missing
