"""Domain exception hierarchy for Nexis.

Use these instead of bare ``except Exception`` in business logic to
distinguish expected failures from unexpected bugs.
"""


class NexisError(Exception):
    """Base for all domain errors."""


class ThinkingError(NexisError):
    """Agent thinking pipeline failure (Thinker, Matcher, Controller)."""


class PipelineError(NexisError):
    """News/value fetch or processing pipeline failure."""


class GraphError(NexisError):
    """Neo4j/Graphiti read or write failure."""


class ConfigError(NexisError):
    """Startup configuration validation failure."""
