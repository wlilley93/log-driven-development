"""Tool runners — one per security scanning tool."""

from vibescan.runners.bandit import BanditRunner
from vibescan.runners.codeql import CodeqlRunner
from vibescan.runners.detect_secrets import DetectSecretsRunner
from vibescan.runners.gitleaks import GitleaksRunner
from vibescan.runners.grype import GrypeRunner
from vibescan.runners.kics import KicsRunner
from vibescan.runners.licence import LicenceRunner
from vibescan.runners.npm_audit import NpmAuditRunner
from vibescan.runners.pip_audit import PipAuditRunner
from vibescan.runners.semgrep import SemgrepRunner
from vibescan.runners.snyk import SnykRunner
from vibescan.runners.trivy import TrivyRunner
from vibescan.runners.trufflehog import TrufflehogRunner

ALL_RUNNERS = [
    GitleaksRunner,
    TrufflehogRunner,
    DetectSecretsRunner,
    SemgrepRunner,
    BanditRunner,
    CodeqlRunner,
    TrivyRunner,
    GrypeRunner,
    NpmAuditRunner,
    PipAuditRunner,
    SnykRunner,
    KicsRunner,
    LicenceRunner,
]

__all__ = [
    "ALL_RUNNERS",
    "BanditRunner",
    "CodeqlRunner",
    "DetectSecretsRunner",
    "GitleaksRunner",
    "GrypeRunner",
    "KicsRunner",
    "LicenceRunner",
    "NpmAuditRunner",
    "PipAuditRunner",
    "SemgrepRunner",
    "SnykRunner",
    "TrivyRunner",
    "TrufflehogRunner",
]
