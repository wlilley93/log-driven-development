"""All runners registry."""

# Env & Secrets
from vibedeploy.runners.dotenv_linter import DotenvLinterRunner
from vibedeploy.runners.detect_secrets import DetectSecretsRunner
from vibedeploy.runners.git_secrets import GitSecretsRunner
from vibedeploy.runners.trufflehog import TrufflehogRunner
from vibedeploy.runners.chamber import ChamberRunner
from vibedeploy.runners.env_validator import EnvValidatorRunner

# Database Safety
from vibedeploy.runners.squawk import SquawkRunner
from vibedeploy.runners.migra import MigraRunner
from vibedeploy.runners.sqlfluff import SqlfluffRunner
from vibedeploy.runners.atlas import AtlasRunner
from vibedeploy.runners.pgtap import PgtapRunner
from vibedeploy.runners.pg_prove import PgProveRunner
from vibedeploy.runners.flyway import FlywayRunner
from vibedeploy.runners.liquibase import LiquibaseRunner
from vibedeploy.runners.rls_checker import RlsCheckerRunner
from vibedeploy.runners.connection_pool import ConnectionPoolRunner

# Docker & Containers
from vibedeploy.runners.hadolint import HadolintRunner
from vibedeploy.runners.dockle import DockleRunner
from vibedeploy.runners.dive import DiveRunner
from vibedeploy.runners.docker_bench import DockerBenchRunner
from vibedeploy.runners.trivy_image import TrivyImageRunner
from vibedeploy.runners.cosign import CosignRunner
from vibedeploy.runners.syft import SyftRunner

# Infrastructure as Code
from vibedeploy.runners.checkov import CheckovRunner
from vibedeploy.runners.tfsec import TfsecRunner
from vibedeploy.runners.terrascan import TerrascanRunner
from vibedeploy.runners.cfn_lint import CfnLintRunner
from vibedeploy.runners.ansible_lint import AnsibleLintRunner
from vibedeploy.runners.helm_lint import HelmLintRunner
from vibedeploy.runners.conftest import ConftestRunner
from vibedeploy.runners.kics import KicsRunner

# Kubernetes
from vibedeploy.runners.kubesec import KubesecRunner
from vibedeploy.runners.kubeval import KubevalRunner
from vibedeploy.runners.polaris import PolarisRunner
from vibedeploy.runners.popeye import PopeyeRunner
from vibedeploy.runners.pluto import PlutoRunner
from vibedeploy.runners.nova import NovaRunner
from vibedeploy.runners.rbac_lookup import RbacLookupRunner
from vibedeploy.runners.kube_score import KubeScoreRunner
from vibedeploy.runners.kubectl_neat import KubectlNeatRunner

# SSL/TLS
from vibedeploy.runners.testssl import TestsslRunner
from vibedeploy.runners.certigo import CertigoRunner
from vibedeploy.runners.ssl_checker import SslCheckerRunner
from vibedeploy.runners.ssllabs import SsllabsRunner
from vibedeploy.runners.mkcert import MkcertRunner

# HTTP Headers
from vibedeploy.runners.observatory import ObservatoryRunner
from vibedeploy.runners.securityheaders import SecurityHeadersRunner
from vibedeploy.runners.webhint import WebhintRunner
from vibedeploy.runners.mixed_content import MixedContentRunner
from vibedeploy.runners.redirect_checker import RedirectCheckerRunner

# Cloud Config
from vibedeploy.runners.prowler import ProwlerRunner
from vibedeploy.runners.scoutsuite import ScoutSuiteRunner
from vibedeploy.runners.steampipe import SteampipeRunner
from vibedeploy.runners.cloudsplaining import CloudsplainingRunner
from vibedeploy.runners.parliament import ParliamentRunner
from vibedeploy.runners.aws_vault import AwsVaultRunner
from vibedeploy.runners.s3scanner import S3ScannerRunner

# CORS & API
from vibedeploy.runners.cors_checker import CorsCheckerRunner
from vibedeploy.runners.rate_limit_checker import RateLimitCheckerRunner

# Build & Production
from vibedeploy.runners.source_map_checker import SourceMapCheckerRunner
from vibedeploy.runners.debug_mode_checker import DebugModeCheckerRunner
from vibedeploy.runners.dependency_audit import DependencyAuditRunner

# Process & Runtime
from vibedeploy.runners.health_check_scanner import HealthCheckScannerRunner
from vibedeploy.runners.graceful_shutdown import GracefulShutdownRunner
from vibedeploy.runners.process_supervisor import ProcessSupervisorRunner
from vibedeploy.runners.pm2_validator import Pm2ValidatorRunner
from vibedeploy.runners.procfile_linter import ProcfileLinterRunner

# Logging & Observability
from vibedeploy.runners.otel_checker import OtelCheckerRunner
from vibedeploy.runners.log_level_checker import LogLevelCheckerRunner
from vibedeploy.runners.sentry_checker import SentryCheckerRunner

# Config Validation
from vibedeploy.runners.yamllint import YamllintRunner
from vibedeploy.runners.jsonlint import JsonlintRunner

# Supply Chain
from vibedeploy.runners.ossf_scorecard import OssfScorecardRunner
from vibedeploy.runners.grype import GrypeRunner
from vibedeploy.runners.pip_audit import PipAuditRunner
from vibedeploy.runners.npm_audit_prod import NpmAuditProdRunner
from vibedeploy.runners.license_checker import LicenseCheckerRunner
from vibedeploy.runners.pip_licenses import PipLicensesRunner

# Web Server
from vibedeploy.runners.nginx_tester import NginxTesterRunner
from vibedeploy.runners.gixy import GixyRunner
from vibedeploy.runners.nginx_analyser import NginxAnalyserRunner

# DNS & Networking
from vibedeploy.runners.dnsx import DnsxRunner
from vibedeploy.runners.httpx_probe import HttpxProbeRunner
from vibedeploy.runners.nmap_safe import NmapSafeRunner

ALL_RUNNERS = [
    # Env & Secrets
    DotenvLinterRunner,
    DetectSecretsRunner,
    GitSecretsRunner,
    TrufflehogRunner,
    ChamberRunner,
    EnvValidatorRunner,
    # Database Safety
    SquawkRunner,
    MigraRunner,
    SqlfluffRunner,
    AtlasRunner,
    PgtapRunner,
    PgProveRunner,
    FlywayRunner,
    LiquibaseRunner,
    RlsCheckerRunner,
    ConnectionPoolRunner,
    # Docker & Containers
    HadolintRunner,
    DockleRunner,
    DiveRunner,
    DockerBenchRunner,
    TrivyImageRunner,
    CosignRunner,
    SyftRunner,
    # Infrastructure as Code
    CheckovRunner,
    TfsecRunner,
    TerrascanRunner,
    CfnLintRunner,
    AnsibleLintRunner,
    HelmLintRunner,
    ConftestRunner,
    KicsRunner,
    # Kubernetes
    KubesecRunner,
    KubevalRunner,
    PolarisRunner,
    PopeyeRunner,
    PlutoRunner,
    NovaRunner,
    RbacLookupRunner,
    KubeScoreRunner,
    KubectlNeatRunner,
    # SSL/TLS
    TestsslRunner,
    CertigoRunner,
    SslCheckerRunner,
    SsllabsRunner,
    MkcertRunner,
    # HTTP Headers
    ObservatoryRunner,
    SecurityHeadersRunner,
    WebhintRunner,
    MixedContentRunner,
    RedirectCheckerRunner,
    # Cloud Config
    ProwlerRunner,
    ScoutSuiteRunner,
    SteampipeRunner,
    CloudsplainingRunner,
    ParliamentRunner,
    AwsVaultRunner,
    S3ScannerRunner,
    # CORS & API
    CorsCheckerRunner,
    RateLimitCheckerRunner,
    # Build & Production
    SourceMapCheckerRunner,
    DebugModeCheckerRunner,
    DependencyAuditRunner,
    # Process & Runtime
    HealthCheckScannerRunner,
    GracefulShutdownRunner,
    ProcessSupervisorRunner,
    Pm2ValidatorRunner,
    ProcfileLinterRunner,
    # Logging & Observability
    OtelCheckerRunner,
    LogLevelCheckerRunner,
    SentryCheckerRunner,
    # Config Validation
    YamllintRunner,
    JsonlintRunner,
    # Supply Chain
    OssfScorecardRunner,
    GrypeRunner,
    PipAuditRunner,
    NpmAuditProdRunner,
    LicenseCheckerRunner,
    PipLicensesRunner,
    # Web Server
    NginxTesterRunner,
    GixyRunner,
    NginxAnalyserRunner,
    # DNS & Networking
    DnsxRunner,
    HttpxProbeRunner,
    NmapSafeRunner,
]
