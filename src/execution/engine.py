"""ExecutionEngine: the stable public entry point for running UnknownLang programs.

``ExecutionEngine`` is a thin compatibility facade over ``IterativeEvaluator``. All
evaluation is done iteratively, with an explicit frame stack, so user-function calls never
use Python recursion and the language-level call-depth limit is not bounded by Python's
own recursion limit.

Public API (unchanged for existing callers):

    ExecutionEngine(*, max_steps=None, max_ast_depth=None, max_call_depth=None)
    ExecutionEngine().execute(program_text, language_spec) -> ExecutionResult

Constructor limits are optional, keyword-only, and validated by ``IterativeEvaluator``;
``None`` selects the defaults (100_000 steps, AST depth 1_000, call depth 100). The facade
applies no defaults of its own, so there is exactly one source of truth.

The names importable from this module before the facade existed (``ExecutionResult``,
``EvalContext``, the exception classes, ``MIN_INT64`` / ``MAX_INT64`` and the default
limits) are re-exported here and are the SAME objects as in ``src.execution.types`` and
``src.execution.iterative_evaluator``.

The previous recursive interpreter lives on, unchanged except for two documented
corrections, as the independent reference evaluator in
``src.oracle.reference_evaluator``.
"""

from __future__ import annotations

from src.execution.iterative_evaluator import EvalContext, IterativeEvaluator
from src.execution.types import (
    DEFAULT_MAX_AST_DEPTH,
    DEFAULT_MAX_CALL_DEPTH,
    DEFAULT_MAX_OUTPUT_BYTES,
    DEFAULT_MAX_STEPS,
    MAX_INT64,
    MIN_INT64,
    AstDepthExceeded,
    ExecutionError,
    ExecutionResult,
    OutputLimitExceeded,
    RecursionLimitExceeded,
    StepLimitExceeded,
)
from src.language.generator import LanguageSpec

__all__ = [
    "ExecutionEngine",
    "ExecutionResult",
    "EvalContext",
    "ExecutionError",
    "StepLimitExceeded",
    "AstDepthExceeded",
    "OutputLimitExceeded",
    "RecursionLimitExceeded",
    "MIN_INT64",
    "MAX_INT64",
    "DEFAULT_MAX_STEPS",
    "DEFAULT_MAX_AST_DEPTH",
    "DEFAULT_MAX_CALL_DEPTH",
    "DEFAULT_MAX_OUTPUT_BYTES",
]


class ExecutionEngine:
    """Execute programs in generated UnknownLang languages.

    Args:
        max_steps: Execution-step budget (default 100_000).
        max_ast_depth: Static AST-depth limit (default 1_000).
        max_call_depth: Active user-function invocation limit (default 100).

    Each limit is an ``int >= 0`` or ``None`` for the default; invalid values raise
    ``TypeError`` / ``ValueError`` at construction. Every ``execute`` call is independent.
    """

    def __init__(
        self,
        *,
        max_steps: int | None = None,
        max_ast_depth: int | None = None,
        max_call_depth: int | None = None,
    ) -> None:
        self._evaluator = IterativeEvaluator(
            max_steps=max_steps,
            max_ast_depth=max_ast_depth,
            max_call_depth=max_call_depth,
        )

    def execute(self, program_text: str, language_spec: LanguageSpec) -> ExecutionResult:
        """Parse and run ``program_text`` in the language described by ``language_spec``.

        Returns an ``ExecutionResult`` whose ``status`` is one of: success, error,
        step_limit_exceeded, recursion_limit_exceeded, ast_depth_exceeded,
        output_limit_exceeded. Resource limits are never raised as exceptions.
        """
        return self._evaluator.execute(program_text, language_spec)
