"""Coverage analyzer — parses existing coverage reports or runs pytest --cov."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

from vibetest.models import Category, Finding, RunnerResult, RunnerStatus, Severity
from vibetest.runners.base import BaseRunner


class CoverageAnalyzerRunner(BaseRunner):
    name = "coverage_analyzer"

    def should_run(self) -> bool:
        target = Path(self.target)
        # Run if coverage data exists or pytest is available
        has_coverage = (
            (target / ".coverage").exists()
            or (target / "coverage.xml").exists()
            or (target / "coverage.json").exists()
            or (target / "htmlcov").exists()
        )
        has_pytest = shutil.which("pytest") is not None
        has_tests = bool(self._find_test_files())

        if not has_coverage and not (has_pytest and has_tests):
            self.skip_reason = "no coverage data and pytest not available"
            return False
        return True

    def run(self) -> RunnerResult:
        start = time.monotonic()
        tc = self.runner_config

        threshold_high = tc.get("threshold_high", 0)
        threshold_medium = tc.get("threshold_medium", 50)
        threshold_low = tc.get("threshold_low", 80)

        # Try to load existing coverage JSON first
        coverage_data = self._load_existing_coverage()

        # If no existing data, try running pytest --cov
        if coverage_data is None:
            coverage_data = self._run_pytest_cov()

        if coverage_data is None:
            return RunnerResult(
                runner=self.name,
                status=RunnerStatus.SKIPPED,
                error="could not obtain coverage data",
                duration_seconds=time.monotonic() - start,
            )

        findings = self._analyze_coverage(coverage_data, threshold_high, threshold_medium, threshold_low)

        return RunnerResult(
            runner=self.name,
            status=RunnerStatus.SUCCESS,
            findings=findings,
            duration_seconds=time.monotonic() - start,
        )

    def _load_existing_coverage(self) -> dict | None:
        """Try to load coverage.json or convert .coverage to JSON."""
        target = Path(self.target)

        # Direct JSON
        json_path = target / "coverage.json"
        if json_path.exists():
            try:
                return json.loads(json_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass

        # .coverage SQLite database — convert via coverage json
        dot_coverage = target / ".coverage"
        if dot_coverage.exists() and shutil.which("coverage"):
            try:
                result = subprocess.run(
                    ["coverage", "json", "-o", "-"],
                    cwd=self.target,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0 and result.stdout.strip():
                    return json.loads(result.stdout)
            except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
                pass

        return None

    def _run_pytest_cov(self) -> dict | None:
        """Run pytest --cov and capture JSON coverage report."""
        if not shutil.which("pytest"):
            return None

        try:
            result = subprocess.run(
                ["pytest", "--cov", "--cov-report=json:/dev/stdout", "--no-header", "-q"],
                cwd=self.target,
                capture_output=True,
                text=True,
                timeout=120,
            )
            # Extract JSON from stdout (pytest may print test results before it)
            stdout = result.stdout.strip()
            json_start = stdout.find("{")
            if json_start >= 0:
                return json.loads(stdout[json_start:])
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
            pass

        return None

    def _analyze_coverage(self, data: dict, t_high: int, t_medium: int, t_low: int) -> list[Finding]:
        findings = []
        files = data.get("files", {})

        for file_path, file_data in files.items():
            if self.config.is_path_excluded(file_path):
                continue

            summary = file_data.get("summary", {})
            pct = summary.get("percent_covered", 100)

            if pct <= t_high:
                severity = Severity.HIGH
                msg = f"0% test coverage"
            elif pct < t_medium:
                severity = Severity.MEDIUM
                msg = f"{pct:.0f}% coverage (below {t_medium}%)"
            elif pct < t_low:
                severity = Severity.LOW
                msg = f"{pct:.0f}% coverage (below {t_low}%)"
            else:
                continue

            findings.append(Finding(
                runner=self.name,
                severity=severity,
                category=Category.COVERAGE,
                file=file_path,
                rule_id="low-coverage",
                message=msg,
                fix_hint=f"Add tests to improve coverage above {t_low}%",
            ))

        return findings
