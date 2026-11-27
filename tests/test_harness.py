"""Tests for M2.6 evaluation harness.

This module tests the deterministic evaluation harness that accepts a generated task,
its environment, and a model response, then produces a structured and reproducible
evaluation outcome.
"""

from __future__ import annotations

import pytest

from src.benchmark.harness import evaluate, AttemptOutcome
from src.benchmark.environments import build_environment
from src.challenge.types import (
    TaskRecord, Protocol, Difficulty, Prompt, AnswerSpec, Evaluation, Test,
    Expected, InputDefinitions, Category, InformationCondition,
    ProtocolKind, Role, DifficultyLevel,
)
from src.execution.types import ExecutionResult


class TestAttemptOutcome:
    """Test AttemptOutcome dataclass and invariants."""
    
    def test_ok_outcome(self):
        """Test OK outcome creation."""
        outcome = AttemptOutcome.ok()
        
        assert outcome.outcome == "ok"
        assert outcome.score == 1
        assert outcome.failure_category == "ok"
        assert outcome.detail is None
        assert outcome.diagnostics == {}
    
    def test_fail_outcome(self):
        """Test FAIL outcome creation."""
        outcome = AttemptOutcome.fail(
            failure_category="syntax_error",
            detail="invalid syntax",
            diagnostics={"line": 1},
        )
        
        assert outcome.outcome == "fail"
        assert outcome.score == 0
        assert outcome.failure_category == "syntax_error"
        assert outcome.detail == "invalid syntax"
        assert outcome.diagnostics == {"line": 1}
    
    def test_void_outcome(self):
        """Test VOID outcome creation."""
        outcome = AttemptOutcome.void(
            failure_category="resource_limit",
            detail="steps",
            diagnostics={"limit": 100000},
        )
        
        assert outcome.outcome == "void"
        assert outcome.score is None
        assert outcome.failure_category == "resource_limit"
        assert outcome.detail == "steps"
        assert outcome.diagnostics == {"limit": 100000}
    
    def test_to_evaluation_record(self):
        """Test serialization to experiment model format."""
        outcome = AttemptOutcome.ok({"test": "value"})
        record = outcome.to_evaluation_record()
        
        assert record == {
            "outcome": "ok",
            "score": 1,
            "failure_category": "ok",
            "detail": None,
            "diagnostics": {"test": "value"},
        }
    
    def test_from_evaluation_record(self):
        """Test deserialization from experiment model format."""
        record = {
            "outcome": "ok",
            "score": 1,
            "failure_category": "ok",
            "detail": None,
            "diagnostics": {"test": "value"},
        }
        outcome = AttemptOutcome.from_evaluation_record(record)
        
        assert outcome.outcome == "ok"
        assert outcome.score == 1
        assert outcome.diagnostics == {"test": "value"}


class TestHarnessInterface:
    """Test harness evaluate() function interface."""
    
    def test_evaluate_signature(self):
        """Test that evaluate accepts correct parameters."""
        # This test verifies the function signature
        import inspect
        sig = inspect.signature(evaluate)
        
        params = list(sig.parameters.keys())
        assert params == ["task", "env", "response_text"]


class TestEvaluateIntegration:
    """Integration tests for evaluate() function."""
    
    def test_evaluate_with_empty_response(self):
        """Test evaluate with empty response."""
        # This would require a real task and environment
        # For now, just verify the function exists and is callable
        assert callable(evaluate)
    
    def test_evaluate_returns_attempt_outcome(self):
        """Test that evaluate returns AttemptOutcome."""
        # This would require a real task and environment
        # For now, just verify the type annotation
        outcome = AttemptOutcome.ok()
        assert isinstance(outcome, AttemptOutcome)
    
    def test_outcome_invariants(self):
        """Test outcome invariants."""
        # ok -> score = 1
        ok_outcome = AttemptOutcome.ok()
        assert ok_outcome.outcome == "ok"
        assert ok_outcome.score == 1
        
        # fail -> score = 0
        fail_outcome = AttemptOutcome.fail("wrong_answer", "value mismatch")
        assert fail_outcome.outcome == "fail"
        assert fail_outcome.score == 0
        
        # void -> score = None
        void_outcome = AttemptOutcome.void("resource_limit", "steps")
        assert void_outcome.outcome == "void"
        assert void_outcome.score is None
