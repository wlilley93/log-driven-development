"""JavaScript/TypeScript AST rules."""

from vibedeploy.ast_rules.javascript.cors_wildcard import CorsWildcardRule
from vibedeploy.ast_rules.javascript.source_maps_served import SourceMapsServedRule
from vibedeploy.ast_rules.javascript.missing_helmet import MissingHelmetRule
from vibedeploy.ast_rules.javascript.process_env_no_fallback import ProcessEnvNoFallbackRule
from vibedeploy.ast_rules.javascript.missing_graceful_shutdown import MissingGracefulShutdownRule

ALL_JS_RULES = [
    CorsWildcardRule(),
    SourceMapsServedRule(),
    MissingHelmetRule(),
    ProcessEnvNoFallbackRule(),
    MissingGracefulShutdownRule(),
]
