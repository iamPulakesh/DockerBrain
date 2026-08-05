"""Rule registry — auto-discovers all rule classes."""

from dockerbrain.optimizer.rules.base import Rule, Suggestion, Severity
from dockerbrain.optimizer.rules.memory_hog import MemoryHogRule
from dockerbrain.optimizer.rules.no_memory_limit import NoMemoryLimitRule
from dockerbrain.optimizer.rules.high_restart import HighRestartRule
from dockerbrain.optimizer.rules.running_as_root import RunningAsRootRule

RULE_REGISTRY: list[type[Rule]] = [
    MemoryHogRule,
    NoMemoryLimitRule,
    HighRestartRule,
    RunningAsRootRule,
]

__all__ = ["Rule", "Suggestion", "Severity", "RULE_REGISTRY"]
