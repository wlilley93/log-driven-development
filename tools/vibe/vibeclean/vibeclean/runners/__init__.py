"""Analysis runners -- one per code hygiene check category."""

from vibeclean.runners.dead_code import DeadCodeRunner
from vibeclean.runners.slop_detector import SlopDetectorRunner
from vibeclean.runners.complexity import ComplexityRunner
from vibeclean.runners.duplication import DuplicationRunner
from vibeclean.runners.convention import ConventionRunner

ALL_RUNNERS = [
    DeadCodeRunner,
    SlopDetectorRunner,
    ComplexityRunner,
    DuplicationRunner,
    ConventionRunner,
]

__all__ = [
    "ALL_RUNNERS",
    "DeadCodeRunner",
    "SlopDetectorRunner",
    "ComplexityRunner",
    "DuplicationRunner",
    "ConventionRunner",
]
