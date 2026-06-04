"""AST-based source code rules for deploy readiness checks."""

from __future__ import annotations

from vibedeploy.ast_rules.python import ALL_PYTHON_RULES
from vibedeploy.ast_rules.javascript import ALL_JS_RULES

ALL_AST_RULES = ALL_PYTHON_RULES + ALL_JS_RULES
