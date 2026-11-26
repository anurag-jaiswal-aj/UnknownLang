"""M2.5 Task Generator System.

This package implements the answer task generator for M2.5:
- EVAL, SYN, INF, CTRL task categories
- Deterministic generation from derivation seeds
- Two-source verification (production + reference)
- Pair builder with validation gates T7/T8
- Identifiability (T13) and non-triviality (T9)
- Chance floor control (T10)

Dependencies:
- src/challenge: types, validation, projection, identity
- src/benchmark: canonical, environments, prompts
- src/language: generator, semantics
- src/execution: engine, reference evaluator
"""

from .registry import GeneratorRegistry, get_generator
from .generator import TaskGenerator

__all__ = [
    "GeneratorRegistry",
    "get_generator",
    "TaskGenerator",
]
