"""Test quality runners — one per analysis type."""

from vibetest.runners.coverage_analyzer import CoverageAnalyzerRunner
from vibetest.runners.assertion_checker import AssertionCheckerRunner
from vibetest.runners.test_smell import TestSmellRunner
from vibetest.runners.missing_tests import MissingTestRunner
from vibetest.runners.flaky_detector import FlakyDetectorRunner

ALL_RUNNERS = [
    CoverageAnalyzerRunner,
    AssertionCheckerRunner,
    TestSmellRunner,
    MissingTestRunner,
    FlakyDetectorRunner,
]

__all__ = [
    "ALL_RUNNERS",
    "CoverageAnalyzerRunner",
    "AssertionCheckerRunner",
    "TestSmellRunner",
    "MissingTestRunner",
    "FlakyDetectorRunner",
]
