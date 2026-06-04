"""Python AST rules."""

from vibedeploy.ast_rules.python.env_without_default import EnvWithoutDefaultRule
from vibedeploy.ast_rules.python.debug_mode import DebugModeRule
from vibedeploy.ast_rules.python.missing_health_check import MissingHealthCheckRule
from vibedeploy.ast_rules.python.missing_sigterm import MissingSigtermRule
from vibedeploy.ast_rules.python.orm_no_pool import OrmNoPoolRule

ALL_PYTHON_RULES = [
    EnvWithoutDefaultRule(),
    DebugModeRule(),
    MissingHealthCheckRule(),
    MissingSigtermRule(),
    OrmNoPoolRule(),
]
