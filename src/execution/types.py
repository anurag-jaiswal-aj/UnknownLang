"""Shared execution data types for UnknownLang.

This module holds the data that every evaluator must agree on: the result type, the
exception hierarchy, the signed 64-bit bounds and the default resource limits.

Dependency boundary
-------------------
* This module imports NO project modules (standard library only), so it can be imported
  from anywhere without creating a cycle.
* ``iterative_evaluator`` and the ``engine`` facade import from here.
* The independent reference evaluator (``src.oracle.reference_evaluator``) may import
  this module, ``src.language.*``, Lark and the standard library. It must NOT import
  ``src.execution.engine``, ``src.execution.iterative_evaluator`` or any other
  production execution helper. It shares data types only, never evaluation logic.

Execution *state* (``EvalContext``, step charging, frames) deliberately does not live here.
It belongs to the iterative evaluator; sharing it would share the very accounting logic the
reference evaluator exists to check independently.

Note: because this file is named ``types.py``, do not run modules in this directory as
scripts (``python src/execution/x.py``); that would put this directory first on ``sys.path``
and shadow the standard-library ``types``. Use ``python -m`` instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Signed 64-bit integer bounds.
MIN_INT64: int = -9223372036854775808
MAX_INT64: int = 9223372036854775807

# Default resource limits (requirements.md, interpreter resource limits).
DEFAULT_MAX_STEPS: int = 100_000
DEFAULT_MAX_AST_DEPTH: int = 1_000
DEFAULT_MAX_CALL_DEPTH: int = 100
DEFAULT_MAX_OUTPUT_BYTES: int = 1_048_576  # 1 MB
# Observable execution behavior version used by Wave 2 environment identity.
RUNTIME_SEMANTICS_VERSION: int = 1


class ExecutionError(Exception):
    """Base exception for execution errors."""


class StepLimitExceeded(ExecutionError):
    """Raised when execution exceeds max_steps."""


class AstDepthExceeded(ExecutionError):
    """Raised when AST depth exceeds max_ast_depth."""


class OutputLimitExceeded(ExecutionError):
    """Raised when output size exceeds max_output_bytes."""


class RecursionLimitExceeded(ExecutionError):
    """Raised when call depth exceeds max_call_depth."""


@dataclass(frozen=True)
class ExecutionResult:
    """Result of program execution.

    ``status`` is one of: success, error, step_limit_exceeded, recursion_limit_exceeded,
    output_limit_exceeded, ast_depth_exceeded, invalid_program.
    """

    status: str
    value: Any = None
    output: str = ""
    error_message: str = ""
    # Wave 2 fields are appended so existing positional construction remains valid.
    error_kind: str | None = None
    error_detail: str | None = None
    steps_used: int | None = None
    ast_depth_reached: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return the legacy four-field dictionary for existing callers."""
        return {
            "status": self.status,
            "value": self.value,
            "output": self.output,
            "error_message": self.error_message,
        }

    def to_diagnostic_dict(self) -> dict[str, Any]:
        """Return the versioned Wave 2 diagnostic representation."""
        return {
            **self.to_dict(),
            "error_kind": self.error_kind,
            "error_detail": self.error_detail,
            "steps_used": self.steps_used,
            "ast_depth_reached": self.ast_depth_reached,
        }
