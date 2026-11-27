"""Attempt outcome data types for the M2.6 evaluation harness.

These types define the in-memory representation of evaluation results.
The outcome schema matches experiment-model.md section 3.3 exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Any

from src.execution.types import ExecutionResult


# Failure categories per evaluation-and-scoring.md section 3.1
# Note: "adapter_unavailable" is handled by runner layer, not harness
FailureCategory = Literal[
    "ok",
    "harness_fault",
    "no_response",
    "extraction_failed",
    "invalid_answer",
    "invalid_submission",
    "syntax_error",
    "name_error",
    "arity_error",
    "type_error",
    "arithmetic_error",
    "literal_range_error",
    "resource_limit",
    "wrong_answer",
]


@dataclass(frozen=True)
class AttemptOutcome:
    """Attempt outcome record matching experiment-model.md section 3.3 evaluation object.
    
    This is the in-memory representation. The experiment model serializes this as:
    ```json
    {
      "evaluation": {
        "outcome": "ok" | "fail" | "void",
        "score": 0 | 1 | null,
        "failure_category": "...",
        "detail": "...",
        "diagnostics": {...}
      }
    }
    ```
    
    Invariants:
    - outcome = "ok" → score = 1
    - outcome = "fail" → score = 0
    - outcome = "void" → score = None
    """
    
    outcome: Literal["ok", "fail", "void"]
    score: int | None
    failure_category: FailureCategory
    detail: str | None
    diagnostics: dict[str, Any]
    
    def to_evaluation_record(self) -> dict[str, Any]:
        """Serialize to experiment model evaluation record format."""
        return {
            "outcome": self.outcome,
            "score": self.score,
            "failure_category": self.failure_category,
            "detail": self.detail,
            "diagnostics": self.diagnostics,
        }
    
    @classmethod
    def from_evaluation_record(cls, record: dict[str, Any]) -> AttemptOutcome:
        """Deserialize from experiment model evaluation record format."""
        return cls(
            outcome=record["outcome"],
            score=record["score"],
            failure_category=record["failure_category"],
            detail=record.get("detail"),
            diagnostics=record.get("diagnostics", {}),
        )
    
    @classmethod
    def ok(cls, diagnostics: dict[str, Any] | None = None) -> AttemptOutcome:
        """Create an OK outcome."""
        return cls(
            outcome="ok",
            score=1,
            failure_category="ok",
            detail=None,
            diagnostics=diagnostics or {},
        )
    
    @classmethod
    def fail(
        cls,
        failure_category: FailureCategory,
        detail: str,
        diagnostics: dict[str, Any] | None = None,
    ) -> AttemptOutcome:
        """Create a FAIL outcome."""
        return cls(
            outcome="fail",
            score=0,
            failure_category=failure_category,
            detail=detail,
            diagnostics=diagnostics or {},
        )
    
    @classmethod
    def void(
        cls,
        failure_category: FailureCategory,
        detail: str,
        diagnostics: dict[str, Any] | None = None,
    ) -> AttemptOutcome:
        """Create a VOID outcome (no score contribution)."""
        return cls(
            outcome="void",
            score=None,
            failure_category=failure_category,
            detail=detail,
            diagnostics=diagnostics or {},
        )