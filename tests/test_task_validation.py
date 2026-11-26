"""Tests for task validation gates T1-T15."""

import pytest

from src.challenge.types import (
    TaskRecord, Protocol, Difficulty, Prompt, AnswerSpec,
    Evaluation, Test, Expected, InputDefinitions, Visibility
)
from src.challenge.validation import validate_task, ValidationError
from src.challenge.identity import compute_task_id


class TestValidationT1:
    """Tests for T1: schema_version, required fields, no unknown fields."""

    def test_valid_task_passes_t1(self):
        """Valid task should pass T1 validation."""
        task = TaskRecord(
            schema_version=1,
            task_id="task_placeholder",
            template=("test.template", 1),
            category="SYN",
            protocol=Protocol(kind="standalone"),
            environment_id="env_0000000000000000000000000000000000000000000000000000000000000000",
            difficulty=Difficulty(
                level=1,
                reasoning_steps=1,
                nesting_depth=1,
                control_flow="none",
                state="none",
            ),
            information_condition="FULL_DOC",
            prompt=Prompt(
                template=("prompt.answer", 1),
                example_policy="neutral",
                public_examples=["(add 1 2)"],
                query="(add 3 4)",
            ),
            answer_spec=AnswerSpec(
                type="value",
                kind="int",
                chance_floor_ppm=0,
            ),
            expected=Expected(
                value={"kind": "int", "value": 7}
            ),
            evaluation=Evaluation(
                method="exact_match",
                limits={"max_steps": 100000, "max_call_depth": 100},
                tests=[],
            ),
        )
        
        # Compute correct task_id first
        task_id = compute_task_id(task)
        
        # Create task with correct ID
        task_with_id = task.__class__(
            **{
                **task.__dict__,
                "task_id": task_id,
            }
        )
        
        rules = validate_task(task_with_id)
        rule_ids = [r.rule_id for r in rules]
        assert "T1" in rule_ids

    def test_missing_required_field_fails_t1(self):
        """Missing required field should fail T1 validation."""
        # Use dict input for easier testing of missing fields
        task_dict = {
            "schema_version": 1,
            "task_id": "task_placeholder",
            "template": ["test.template", 1],
            "category": "SYN",
            "protocol": {"kind": "standalone"},
            "environment_id": "env_0000000000000000000000000000000000000000000000000000000000000000",
            "difficulty": {
                "level": 1, "reasoning_steps": 1, "nesting_depth": 1,
                "control_flow": "none", "state": "none"
            },
            "information_condition": "FULL_DOC",
            # Missing prompt
            "answer_spec": {
                "type": "value",
                "kind": "int",
                "chance_floor_ppm": 0,
            },
            "expected": {"kind": "int", "value": 7},
            "evaluation": {
                "method": "exact_match",
                "limits": {"max_steps": 100000, "max_call_depth": 100},
                "tests": [],
            },
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_task(task_dict)
        
        assert exc_info.value.rule == "T1"

    def test_unknown_field_fails_t1(self):
        """Unknown field should fail T1 validation."""
        task_dict = {
            "schema_version": 1,
            "task_id": "task_placeholder",
            "template": ["test.template", 1],
            "category": "SYN",
            "protocol": {"kind": "standalone"},
            "environment_id": "env_0000000000000000000000000000000000000000000000000000000000000000",
            "difficulty": {
                "level": 1, "reasoning_steps": 1, "nesting_depth": 1,
                "control_flow": "none", "state": "none"
            },
            "information_condition": "FULL_DOC",
            "prompt": {
                "template": ["prompt.answer", 1],
                "example_policy": "neutral",
                "public_examples": ["(add 1 2)"],
                "query": "(add 3 4)",
            },
            "answer_spec": {
                "type": "value",
                "kind": "int",
                "chance_floor_ppm": 0,
            },
            "expected": {"kind": "int", "value": 7},
            "evaluation": {
                "method": "exact_match",
                "limits": {"max_steps": 100000, "max_call_depth": 100},
                "tests": [],
            },
            "unknown_field": "should_fail",  # Unknown field
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_task(task_dict)
        
        assert exc_info.value.rule == "T1"

    def test_invalid_schema_version_fails_t1(self):
        """Invalid schema_version should fail T1 validation."""
        task_dict = {
            "schema_version": 2,  # Invalid
            "task_id": "task_placeholder",
            "template": ["test.template", 1],
            "category": "SYN",
            "protocol": {"kind": "standalone"},
            "environment_id": "env_0000000000000000000000000000000000000000000000000000000000000000",
            "difficulty": {
                "level": 1, "reasoning_steps": 1, "nesting_depth": 1,
                "control_flow": "none", "state": "none"
            },
            "information_condition": "FULL_DOC",
            "prompt": {
                "template": ["prompt.answer", 1],
                "example_policy": "neutral",
                "public_examples": ["(add 1 2)"],
                "query": "(add 3 4)",
            },
            "answer_spec": {
                "type": "value",
                "kind": "int",
                "chance_floor_ppm": 0,
            },
            "expected": {"kind": "int", "value": 7},
            "evaluation": {
                "method": "exact_match",
                "limits": {"max_steps": 100000, "max_call_depth": 100},
                "tests": [],
            },
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_task(task_dict)
        
        assert exc_info.value.rule == "T1"


class TestValidationT2:
    """Tests for T2: task_id equals recomputed hash."""

    def test_valid_task_id_passes_t2(self):
        """Task with correct task_id should pass T2 validation."""
        task = TaskRecord(
            schema_version=1,
            task_id="task_placeholder",  # Will be recomputed
            template=("test.template", 1),
            category="SYN",
            protocol=Protocol(kind="standalone"),
            environment_id="env_0000000000000000000000000000000000000000000000000000000000000000",
            difficulty=Difficulty(
                level=1,
                reasoning_steps=1,
                nesting_depth=1,
                control_flow="none",
                state="none",
            ),
            information_condition="FULL_DOC",
            prompt=Prompt(
                template=("prompt.answer", 1),
                example_policy="neutral",
                public_examples=["(add 1 2)"],
                query="(add 3 4)",
            ),
            answer_spec=AnswerSpec(
                type="value",
                kind="int",
                chance_floor_ppm=0,
            ),
            expected=Expected(
                value={"kind": "int", "value": 7}
            ),
            evaluation=Evaluation(
                method="exact_match",
                limits={"max_steps": 100000, "max_call_depth": 100},
                tests=[],
            ),
        )
        
        # Compute correct task_id
        correct_id = compute_task_id(task)
        
        # Create task with correct ID
        task_with_correct_id = task.__class__(
            **{
                **task.__dict__,
                "task_id": correct_id,
            }
        )
        
        # Should pass without error
        rules = validate_task(task_with_correct_id)
        rule_ids = [r.rule_id for r in rules]
        assert "T2" in rule_ids

    def test_invalid_task_id_fails_t2(self):
        """Task with incorrect task_id should fail T2 validation."""
        task = TaskRecord(
            schema_version=1,
            task_id="task_wrong_id",  # Wrong ID
            template=("test.template", 1),
            category="SYN",
            protocol=Protocol(kind="standalone"),
            environment_id="env_0000000000000000000000000000000000000000000000000000000000000000",
            difficulty=Difficulty(
                level=1,
                reasoning_steps=1,
                nesting_depth=1,
                control_flow="none",
                state="none",
            ),
            information_condition="FULL_DOC",
            prompt=Prompt(
                template=("prompt.answer", 1),
                example_policy="neutral",
                public_examples=["(add 1 2)"],
                query="(add 3 4)",
            ),
            answer_spec=AnswerSpec(
                type="value",
                kind="int",
                chance_floor_ppm=0,
            ),
            expected=Expected(
                value={"kind": "int", "value": 7}
            ),
            evaluation=Evaluation(
                method="exact_match",
                limits={"max_steps": 100000, "max_call_depth": 100},
                tests=[],
            ),
        )
        
        with pytest.raises(ValidationError) as exc_info:
            validate_task(task)
        
        assert exc_info.value.rule == "T2"


class TestValidationT6:
    """Tests for T6: Hidden tests are disjoint from public examples and query."""

    def test_valid_hidden_tests_pass_t6(self):
        """Valid hidden tests (disjoint from public) should pass T6."""
        # Use dict input for T6 test to avoid T2 issues
        task_dict = {
            "schema_version": 1,
            "task_id": "task_placeholder",  # Will be computed
            "template": ["test.template", 1],
            "category": "EVAL",
            "protocol": {"kind": "standalone"},
            "environment_id": "env_0000000000000000000000000000000000000000000000000000000000000000",
            "difficulty": {
                "level": 1, "reasoning_steps": 1, "nesting_depth": 1,
                "control_flow": "none", "state": "none"
            },
            "information_condition": "FULL_DOC",
            "prompt": {
                "template": ["prompt.program", 1],
                "example_policy": "neutral",
                "public_examples": ["(add 1 2)"],
                "query": "(add 3 4)",
            },
            "answer_spec": {
                "type": "program",
                "kind": None,
                "form": "definitions_only",
            },
            "expected": {"kind": "int", "value": 7},
            "evaluation": {
                "method": "test_suite",
                "limits": {"max_steps": 100000, "max_call_depth": 100},
                "tests": [
                    {
                        "test_id": "test1",
                        "call": "(add 5 6)",
                        "expected": {"kind": "int", "value": 11},
                        "visibility": "hidden",  # Hidden test, disjoint from public
                    },
                ],
            },
        }
        
        # Compute correct task_id
        task_id = compute_task_id(task_dict)
        task_dict["task_id"] = task_id
        
        rules = validate_task(task_dict)
        rule_ids = [r.rule_id for r in rules]
        assert "T6" in rule_ids

    def test_hidden_test_matches_public_example_fails_t6(self):
        """Hidden test matching public example should fail T6."""
        # Use dict input with hidden test matching public example
        task_dict = {
            "schema_version": 1,
            "task_id": "task_placeholder",
            "template": ["test.template", 1],
            "category": "EVAL",
            "protocol": {"kind": "standalone"},
            "environment_id": "env_0000000000000000000000000000000000000000000000000000000000000000",
            "difficulty": {
                "level": 1, "reasoning_steps": 1, "nesting_depth": 1,
                "control_flow": "none", "state": "none"
            },
            "information_condition": "FULL_DOC",
            "prompt": {
                "template": ["prompt.program", 1],
                "example_policy": "neutral",
                "public_examples": ["(add 1 2)"],
                "query": "(add 3 4)",
            },
            "answer_spec": {
                "type": "program",
                "kind": None,
                "form": "definitions_only",
            },
            "expected": {"kind": "int", "value": 7},
            "evaluation": {
                "method": "test_suite",
                "limits": {"max_steps": 100000, "max_call_depth": 100},
                "tests": [
                    {
                        "test_id": "test1",
                        "call": "(add 1 2)",  # Same as public example - T6 should fail
                        "expected": {"kind": "int", "value": 3},
                        "visibility": "hidden",
                    },
                ],
            },
        }
        
        # Compute correct task_id before validation
        task_id = compute_task_id(task_dict)
        task_dict["task_id"] = task_id
        
        with pytest.raises(ValidationError) as exc_info:
            validate_task(task_dict)
        
        assert exc_info.value.rule == "T6"
        assert "public example" in exc_info.value.message

    def test_hidden_test_matches_query_fails_t6(self):
        """Hidden test matching query should fail T6."""
        # Use dict input with hidden test matching query
        task_dict = {
            "schema_version": 1,
            "task_id": "task_placeholder",
            "template": ["test.template", 1],
            "category": "EVAL",
            "protocol": {"kind": "standalone"},
            "environment_id": "env_0000000000000000000000000000000000000000000000000000000000000000",
            "difficulty": {
                "level": 1, "reasoning_steps": 1, "nesting_depth": 1,
                "control_flow": "none", "state": "none"
            },
            "information_condition": "FULL_DOC",
            "prompt": {
                "template": ["prompt.program", 1],
                "example_policy": "neutral",
                "public_examples": ["(add 1 2)"],
                "query": "(add 3 4)",
            },
            "answer_spec": {
                "type": "program",
                "kind": None,
                "form": "definitions_only",
            },
            "expected": {"kind": "int", "value": 7},
            "evaluation": {
                "method": "test_suite",
                "limits": {"max_steps": 100000, "max_call_depth": 100},
                "tests": [
                    {
                        "test_id": "test1",
                        "call": "(add 3 4)",  # Same as query - T6 should fail
                        "expected": {"kind": "int", "value": 7},
                        "visibility": "hidden",
                    },
                ],
            },
        }
        
        # Compute correct task_id before validation
        task_id = compute_task_id(task_dict)
        task_dict["task_id"] = task_id
        
        with pytest.raises(ValidationError) as exc_info:
            validate_task(task_dict)
        
        assert exc_info.value.rule == "T6"
        assert "query" in exc_info.value.message


class TestValidationT9:
    """Tests for T9: Non-triviality - expected not in query or public examples."""

    def test_valid_non_trivial_passes_t9(self):
        """Non-trivial task (expected not in query) should pass T9."""
        task = TaskRecord(
            schema_version=1,
            task_id="task_placeholder",
            template=("test.template", 1),
            category="SYN",
            protocol=Protocol(kind="standalone"),
            environment_id="env_0000000000000000000000000000000000000000000000000000000000000000",
            difficulty=Difficulty(
                level=1,
                reasoning_steps=1,
                nesting_depth=1,
                control_flow="none",
                state="none",
            ),
            information_condition="FULL_DOC",
            prompt=Prompt(
                template=("prompt.answer", 1),
                example_policy="neutral",
                public_examples=["(add 1 2)"],
                query="(add 3 4)",  # Result is 7
            ),
            answer_spec=AnswerSpec(
                type="value",
                kind="int",
                chance_floor_ppm=0,
            ),
            expected=Expected(
                value={"kind": "int", "value": 100}  # Different from query result
            ),
            evaluation=Evaluation(
                method="exact_match",
                limits={"max_steps": 100000, "max_call_depth": 100},
                tests=[],
            ),
        )
        
        # Compute correct task_id before validation
        task_id = compute_task_id(task)
        task_with_id = task.__class__(
            **{
                **task.__dict__,
                "task_id": task_id,
            }
        )
        
        rules = validate_task(task_with_id)
        rule_ids = [r.rule_id for r in rules]
        assert "T9" in rule_ids

    def test_expected_in_query_fails_t9(self):
        """Expected value in query should fail T9."""
        # Use a query that literally contains the expected value as a literal
        task = TaskRecord(
            schema_version=1,
            task_id="task_placeholder",
            template=("test.template", 1),
            category="SYN",
            protocol=Protocol(kind="standalone"),
            environment_id="env_0000000000000000000000000000000000000000000000000000000000000000",
            difficulty=Difficulty(
                level=1,
                reasoning_steps=1,
                nesting_depth=1,
                control_flow="none",
                state="none",
            ),
            information_condition="FULL_DOC",
            prompt=Prompt(
                template=("prompt.answer", 1),
                example_policy="neutral",
                public_examples=["(add 1 2)"],
                query="(add 3 4)",  # The expected value 7 should appear as a literal
            ),
            answer_spec=AnswerSpec(
                type="value",
                kind="int",
                chance_floor_ppm=0,
            ),
            expected=Expected(
                value={"kind": "int", "value": 4}  # 4 IS a literal in the query "(add 3 4)"
            ),
            evaluation=Evaluation(
                method="exact_match",
                limits={"max_steps": 100000, "max_call_depth": 100},
                tests=[],
            ),
        )
        
        # Compute correct task_id before validation
        task_id = compute_task_id(task)
        task_with_id = task.__class__(
            **{
                **task.__dict__,
                "task_id": task_id,
            }
        )
        
        with pytest.raises(ValidationError) as exc_info:
            validate_task(task_with_id)
        
        assert exc_info.value.rule == "T9"

    def test_expected_in_public_example_fails_t9(self):
        """Expected value in public example should fail T9."""
        task = TaskRecord(
            schema_version=1,
            task_id="task_placeholder",
            template=("test.template", 1),
            category="SYN",
            protocol=Protocol(kind="standalone"),
            environment_id="env_0000000000000000000000000000000000000000000000000000000000000000",
            difficulty=Difficulty(
                level=1,
                reasoning_steps=1,
                nesting_depth=1,
                control_flow="none",
                state="none",
            ),
            information_condition="FULL_DOC",
            prompt=Prompt(
                template=("prompt.answer", 1),
                example_policy="neutral",
                public_examples=["(add 1 2)"],  # Result is 3, which is our expected value
                query="(add 3 4)",
            ),
            answer_spec=AnswerSpec(
                type="value",
                kind="int",
                chance_floor_ppm=0,
            ),
            expected=Expected(
                value={"kind": "int", "value": 3}  # Same as public example result!
            ),
            evaluation=Evaluation(
                method="exact_match",
                limits={"max_steps": 100000, "max_call_depth": 100},
                tests=[],
            ),
        )
        
        # Compute correct task_id before validation
        task_id = compute_task_id(task)
        task_with_id = task.__class__(
            **{
                **task.__dict__,
                "task_id": task_id,
            }
        )
        
        with pytest.raises(ValidationError) as exc_info:
            validate_task(task_with_id)
        
        assert exc_info.value.rule == "T9"


class TestValidationT10:
    """Tests for T10: chance_floor_ppm <= 100000."""

    def test_valid_floor_passes_t10(self):
        """Valid chance_floor_ppm should pass T10."""
        """Valid chance_floor_ppm should pass T10."""
        task = TaskRecord(
            schema_version=1,
            task_id="task_placeholder",
            template=("test.template", 1),
            category="SYN",
            protocol=Protocol(kind="standalone"),
            environment_id="env_0000000000000000000000000000000000000000000000000000000000000000",
            difficulty=Difficulty(
                level=1,
                reasoning_steps=1,
                nesting_depth=1,
                control_flow="none",
                state="none",
            ),
            information_condition="FULL_DOC",
            prompt=Prompt(
                template=("prompt.answer", 1),
                example_policy="neutral",
                public_examples=["(add 1 2)"],
                query="(add 3 4)",
            ),
            answer_spec=AnswerSpec(
                type="value",
                kind="int",
                chance_floor_ppm=50000,  # Below 100000
            ),
            expected=Expected(
                value={"kind": "int", "value": 7}
            ),
            evaluation=Evaluation(
                method="exact_match",
                limits={"max_steps": 100000, "max_call_depth": 100},
                tests=[],
            ),
        )
        
        # Compute correct task_id before validation
        task_id = compute_task_id(task)
        task_with_id = task.__class__(
            **{
                **task.__dict__,
                "task_id": task_id,
            }
        )
        
        rules = validate_task(task_with_id)
        rule_ids = [r.rule_id for r in rules]
        assert "T10" in rule_ids

    def test_floor_too_high_fails_t10(self):
        """chance_floor_ppm > 100000 should fail T10."""
        task = TaskRecord(
            schema_version=1,
            task_id="task_placeholder",
            template=("test.template", 1),
            category="SYN",
            protocol=Protocol(kind="standalone"),
            environment_id="env_0000000000000000000000000000000000000000000000000000000000000000",
            difficulty=Difficulty(
                level=1,
                reasoning_steps=1,
                nesting_depth=1,
                control_flow="none",
                state="none",
            ),
            information_condition="FULL_DOC",
            prompt=Prompt(
                template=("prompt.answer", 1),
                example_policy="neutral",
                public_examples=["(add 1 2)"],
                query="(add 3 4)",
            ),
            answer_spec=AnswerSpec(
                type="value",
                kind="int",
                chance_floor_ppm=100001,  # Above 100000
            ),
            expected=Expected(
                value={"kind": "int", "value": 7}
            ),
            evaluation=Evaluation(
                method="exact_match",
                limits={"max_steps": 100000, "max_call_depth": 100},
                tests=[],
            ),
        )
        
        # Compute correct task_id before validation
        task_id = compute_task_id(task)
        task_with_id = task.__class__(
            **{
                **task.__dict__,
                "task_id": task_id,
            }
        )
        
        with pytest.raises(ValidationError) as exc_info:
            validate_task(task_with_id)
        
        assert exc_info.value.rule == "T10"
        assert "100000" in exc_info.value.message

    def test_no_floor_allowed(self):
        """None chance_floor_ppm should be allowed."""
        task = TaskRecord(
            schema_version=1,
            task_id="task_placeholder",
            template=("test.template", 1),
            category="SYN",
            protocol=Protocol(kind="standalone"),
            environment_id="env_0000000000000000000000000000000000000000000000000000000000000000",
            difficulty=Difficulty(
                level=1,
                reasoning_steps=1,
                nesting_depth=1,
                control_flow="none",
                state="none",
            ),
            information_condition="FULL_DOC",
            prompt=Prompt(
                template=("prompt.answer", 1),
                example_policy="neutral",
                public_examples=["(add 1 2)"],
                query="(add 3 4)",
            ),
            answer_spec=AnswerSpec(
                type="value",
                kind="int",
                chance_floor_ppm=None,  # No floor
            ),
            expected=Expected(
                value={"kind": "int", "value": 7}
            ),
            evaluation=Evaluation(
                method="exact_match",
                limits={"max_steps": 100000, "max_call_depth": 100},
                tests=[],
            ),
        )
        
        # Compute correct task_id before validation
        task_id = compute_task_id(task)
        task_with_id = task.__class__(
            **{
                **task.__dict__,
                "task_id": task_id,
            }
        )
        
        rules = validate_task(task_with_id)
        rule_ids = [r.rule_id for r in rules]
        assert "T10" in rule_ids



    def test_negative_floor_rejected(self):
        """Negative chance_floor_ppm should fail T10."""
        task = TaskRecord(
            schema_version=1,
            task_id="task_placeholder",
            template=("test.template", 1),
            category="SYN",
            protocol=Protocol(kind="standalone"),
            environment_id="env_0000000000000000000000000000000000000000000000000000000000000000",
            difficulty=Difficulty(
                level=1,
                reasoning_steps=1,
                nesting_depth=1,
                control_flow="none",
                state="none",
            ),
            information_condition="FULL_DOC",
            prompt=Prompt(
                template=("prompt.answer", 1),
                example_policy="neutral",
                public_examples=["(add 1 2)"],
                query="(add 3 4)",
            ),
            answer_spec=AnswerSpec(
                type="value",
                kind="int",
                chance_floor_ppm=-1,  # Negative - must fail
            ),
            expected=Expected(
                value={"kind": "int", "value": 7}
            ),
            evaluation=Evaluation(
                method="exact_match",
                limits={"max_steps": 100000, "max_call_depth": 100},
                tests=[],
            ),
        )
        
        task_id = compute_task_id(task)
        task_with_id = task.__class__(**{**task.__dict__, "task_id": task_id})
        
        with pytest.raises(ValidationError) as exc_info:
            validate_task(task_with_id)
        
        assert exc_info.value.rule == "T10"
        assert ">= 0" in exc_info.value.message

    def test_boolean_floor_rejected(self):
        """Boolean chance_floor_ppm should fail T10 (bool is subclass of int)."""
        task = TaskRecord(
            schema_version=1,
            task_id="task_placeholder",
            template=("test.template", 1),
            category="SYN",
            protocol=Protocol(kind="standalone"),
            environment_id="env_0000000000000000000000000000000000000000000000000000000000000000",
            difficulty=Difficulty(
                level=1,
                reasoning_steps=1,
                nesting_depth=1,
                control_flow="none",
                state="none",
            ),
            information_condition="FULL_DOC",
            prompt=Prompt(
                template=("prompt.answer", 1),
                example_policy="neutral",
                public_examples=["(add 1 2)"],
                query="(add 3 4)",
            ),
            answer_spec=AnswerSpec(
                type="value",
                kind="int",
                chance_floor_ppm=True,  # Boolean - must fail
            ),
            expected=Expected(
                value={"kind": "int", "value": 7}
            ),
            evaluation=Evaluation(
                method="exact_match",
                limits={"max_steps": 100000, "max_call_depth": 100},
                tests=[],
            ),
        )
        
        task_id = compute_task_id(task)
        task_with_id = task.__class__(**{**task.__dict__, "task_id": task_id})
        
        with pytest.raises(ValidationError) as exc_info:
            validate_task(task_with_id)
        
        assert exc_info.value.rule == "T10"
        assert "bool" in exc_info.value.message

    def test_floor_at_boundary_passes(self):
        """chance_floor_ppm = 100000 (boundary) should pass T10."""
        task = TaskRecord(
            schema_version=1,
            task_id="task_placeholder",
            template=("test.template", 1),
            category="SYN",
            protocol=Protocol(kind="standalone"),
            environment_id="env_0000000000000000000000000000000000000000000000000000000000000000",
            difficulty=Difficulty(
                level=1,
                reasoning_steps=1,
                nesting_depth=1,
                control_flow="none",
                state="none",
            ),
            information_condition="FULL_DOC",
            prompt=Prompt(
                template=("prompt.answer", 1),
                example_policy="neutral",
                public_examples=["(add 1 2)"],
                query="(add 3 4)",
            ),
            answer_spec=AnswerSpec(
                type="value",
                kind="int",
                chance_floor_ppm=100000,  # Boundary - should pass
            ),
            expected=Expected(
                value={"kind": "int", "value": 7}
            ),
            evaluation=Evaluation(
                method="exact_match",
                limits={"max_steps": 100000, "max_call_depth": 100},
                tests=[],
            ),
        )
        
        task_id = compute_task_id(task)
        task_with_id = task.__class__(**{**task.__dict__, "task_id": task_id})
        
        rules = validate_task(task_with_id)
        rule_ids = [r.rule_id for r in rules]
        assert "T10" in rule_ids

    def test_zero_floor_allowed(self):
        """chance_floor_ppm = 0 should be allowed."""
        task = TaskRecord(
            schema_version=1,
            task_id="task_placeholder",
            template=("test.template", 1),
            category="SYN",
            protocol=Protocol(kind="standalone"),
            environment_id="env_0000000000000000000000000000000000000000000000000000000000000000",
            difficulty=Difficulty(
                level=1,
                reasoning_steps=1,
                nesting_depth=1,
                control_flow="none",
                state="none",
            ),
            information_condition="FULL_DOC",
            prompt=Prompt(
                template=("prompt.answer", 1),
                example_policy="neutral",
                public_examples=["(add 1 2)"],
                query="(add 3 4)",
            ),
            answer_spec=AnswerSpec(
                type="value",
                kind="int",
                chance_floor_ppm=0,  # Zero - should pass
            ),
            expected=Expected(
                value={"kind": "int", "value": 7}
            ),
            evaluation=Evaluation(
                method="exact_match",
                limits={"max_steps": 100000, "max_call_depth": 100},
                tests=[],
            ),
        )
        
        task_id = compute_task_id(task)
        task_with_id = task.__class__(**{**task.__dict__, "task_id": task_id})
        
        rules = validate_task(task_with_id)
        rule_ids = [r.rule_id for r in rules]
        assert "T10" in rule_ids


class TestValidationT2Regression:
    """Regression tests for T2 task identity validation - no bypasses allowed."""


    def test_negative_floor_rejected(self):
        """Negative chance_floor_ppm should fail T10."""
        task = TaskRecord(
            schema_version=1,
            task_id="task_placeholder",
            template=("test.template", 1),
            category="SYN",
            protocol=Protocol(kind="standalone"),
            environment_id="env_0000000000000000000000000000000000000000000000000000000000000000",
            difficulty=Difficulty(
                level=1,
                reasoning_steps=1,
                nesting_depth=1,
                control_flow="none",
                state="none",
            ),
            information_condition="FULL_DOC",
            prompt=Prompt(
                template=("prompt.answer", 1),
                example_policy="neutral",
                public_examples=["(add 1 2)"],
                query="(add 3 4)",
            ),
            answer_spec=AnswerSpec(
                type="value",
                kind="int",
                chance_floor_ppm=-1,  # Negative - must fail
            ),
            expected=Expected(
                value={"kind": "int", "value": 7}
            ),
            evaluation=Evaluation(
                method="exact_match",
                limits={"max_steps": 100000, "max_call_depth": 100},
                tests=[],
            ),
        )
        
        task_id = compute_task_id(task)
        task_with_id = task.__class__(**{**task.__dict__, "task_id": task_id})
        
        with pytest.raises(ValidationError) as exc_info:
            validate_task(task_with_id)
        
        assert exc_info.value.rule == "T10"
        assert ">= 0" in exc_info.value.message

    def test_boolean_floor_rejected(self):
        """Boolean chance_floor_ppm should fail T10 (bool is subclass of int)."""
        task = TaskRecord(
            schema_version=1,
            task_id="task_placeholder",
            template=("test.template", 1),
            category="SYN",
            protocol=Protocol(kind="standalone"),
            environment_id="env_0000000000000000000000000000000000000000000000000000000000000000",
            difficulty=Difficulty(
                level=1,
                reasoning_steps=1,
                nesting_depth=1,
                control_flow="none",
                state="none",
            ),
            information_condition="FULL_DOC",
            prompt=Prompt(
                template=("prompt.answer", 1),
                example_policy="neutral",
                public_examples=["(add 1 2)"],
                query="(add 3 4)",
            ),
            answer_spec=AnswerSpec(
                type="value",
                kind="int",
                chance_floor_ppm=True,  # Boolean - must fail
            ),
            expected=Expected(
                value={"kind": "int", "value": 7}
            ),
            evaluation=Evaluation(
                method="exact_match",
                limits={"max_steps": 100000, "max_call_depth": 100},
                tests=[],
            ),
        )
        
        task_id = compute_task_id(task)
        task_with_id = task.__class__(**{**task.__dict__, "task_id": task_id})
        
        with pytest.raises(ValidationError) as exc_info:
            validate_task(task_with_id)
        
        assert exc_info.value.rule == "T10"
        assert "bool" in exc_info.value.message

    def test_floor_at_boundary_passes(self):
        """chance_floor_ppm = 100000 (boundary) should pass T10."""
        task = TaskRecord(
            schema_version=1,
            task_id="task_placeholder",
            template=("test.template", 1),
            category="SYN",
            protocol=Protocol(kind="standalone"),
            environment_id="env_0000000000000000000000000000000000000000000000000000000000000000",
            difficulty=Difficulty(
                level=1,
                reasoning_steps=1,
                nesting_depth=1,
                control_flow="none",
                state="none",
            ),
            information_condition="FULL_DOC",
            prompt=Prompt(
                template=("prompt.answer", 1),
                example_policy="neutral",
                public_examples=["(add 1 2)"],
                query="(add 3 4)",
            ),
            answer_spec=AnswerSpec(
                type="value",
                kind="int",
                chance_floor_ppm=100000,  # Boundary - should pass
            ),
            expected=Expected(
                value={"kind": "int", "value": 7}
            ),
            evaluation=Evaluation(
                method="exact_match",
                limits={"max_steps": 100000, "max_call_depth": 100},
                tests=[],
            ),
        )
        
        task_id = compute_task_id(task)
        task_with_id = task.__class__(**{**task.__dict__, "task_id": task_id})
        
        rules = validate_task(task_with_id)
        rule_ids = [r.rule_id for r in rules]
        assert "T10" in rule_ids

    def test_zero_floor_allowed(self):
        """chance_floor_ppm = 0 should be allowed."""
        task = TaskRecord(
            schema_version=1,
            task_id="task_placeholder",
            template=("test.template", 1),
            category="SYN",
            protocol=Protocol(kind="standalone"),
            environment_id="env_0000000000000000000000000000000000000000000000000000000000000000",
            difficulty=Difficulty(
                level=1,
                reasoning_steps=1,
                nesting_depth=1,
                control_flow="none",
                state="none",
            ),
            information_condition="FULL_DOC",
            prompt=Prompt(
                template=("prompt.answer", 1),
                example_policy="neutral",
                public_examples=["(add 1 2)"],
                query="(add 3 4)",
            ),
            answer_spec=AnswerSpec(
                type="value",
                kind="int",
                chance_floor_ppm=0,  # Zero - should pass
            ),
            expected=Expected(
                value={"kind": "int", "value": 7}
            ),
            evaluation=Evaluation(
                method="exact_match",
                limits={"max_steps": 100000, "max_call_depth": 100},
                tests=[],
            ),
        )
        
        task_id = compute_task_id(task)
        task_with_id = task.__class__(**{**task.__dict__, "task_id": task_id})
        
        rules = validate_task(task_with_id)
        rule_ids = [r.rule_id for r in rules]
        assert "T10" in rule_ids
    def test_task_placeholder_rejected(self):
        """task_placeholder must be rejected as invalid task_id."""
        task = TaskRecord(
            schema_version=1,
            task_id="task_placeholder",  # Placeholder - must fail
            template=("test.template", 1),
            category="SYN",
            protocol=Protocol(kind="standalone"),
            environment_id="env_0000000000000000000000000000000000000000000000000000000000000000",
            difficulty=Difficulty(
                level=1,
                reasoning_steps=1,
                nesting_depth=1,
                control_flow="none",
                state="none",
            ),
            information_condition="FULL_DOC",
            prompt=Prompt(
                template=("prompt.answer", 1),
                example_policy="neutral",
                public_examples=["(add 1 2)"],
                query="(add 3 4)",
            ),
            answer_spec=AnswerSpec(
                type="value",
                kind="int",
                chance_floor_ppm=0,
            ),
            expected=Expected(
                value={"kind": "int", "value": 7}
            ),
            evaluation=Evaluation(
                method="exact_match",
                limits={"max_steps": 100000, "max_call_depth": 100},
                tests=[],
            ),
        )
        
        # Should fail with T2 error
        with pytest.raises(ValidationError) as exc_info:
            validate_task(task)
        
        assert exc_info.value.rule == "T2"

    def test_arbitrary_task_id_rejected(self):
        """Arbitrary task_ ID must be rejected as invalid."""
        task = TaskRecord(
            schema_version=1,
            task_id="task_arbitrary_12345",  # Arbitrary ID - must fail
            template=("test.template", 1),
            category="SYN",
            protocol=Protocol(kind="standalone"),
            environment_id="env_0000000000000000000000000000000000000000000000000000000000000000",
            difficulty=Difficulty(
                level=1,
                reasoning_steps=1,
                nesting_depth=1,
                control_flow="none",
                state="none",
            ),
            information_condition="FULL_DOC",
            prompt=Prompt(
                template=("prompt.answer", 1),
                example_policy="neutral",
                public_examples=["(add 1 2)"],
                query="(add 3 4)",
            ),
            answer_spec=AnswerSpec(
                type="value",
                kind="int",
                chance_floor_ppm=0,
            ),
            expected=Expected(
                value={"kind": "int", "value": 7}
            ),
            evaluation=Evaluation(
                method="exact_match",
                limits={"max_steps": 100000, "max_call_depth": 100},
                tests=[],
            ),
        )
        
        # Should fail with T2 error
        with pytest.raises(ValidationError) as exc_info:
            validate_task(task)
        
        assert exc_info.value.rule == "T2"

    def test_computed_task_id_accepted(self):
        """Correctly computed task_id must be accepted."""
        task = TaskRecord(
            schema_version=1,
            task_id="task_placeholder",
            template=("test.template", 1),
            category="SYN",
            protocol=Protocol(kind="standalone"),
            environment_id="env_0000000000000000000000000000000000000000000000000000000000000000",
            difficulty=Difficulty(
                level=1,
                reasoning_steps=1,
                nesting_depth=1,
                control_flow="none",
                state="none",
            ),
            information_condition="FULL_DOC",
            prompt=Prompt(
                template=("prompt.answer", 1),
                example_policy="neutral",
                public_examples=["(add 1 2)"],
                query="(add 3 4)",
            ),
            answer_spec=AnswerSpec(
                type="value",
                kind="int",
                chance_floor_ppm=0,
            ),
            expected=Expected(
                value={"kind": "int", "value": 7}
            ),
            evaluation=Evaluation(
                method="exact_match",
                limits={"max_steps": 100000, "max_call_depth": 100},
                tests=[],
            ),
        )
        
        # Compute correct task_id
        task_id = compute_task_id(task)
        
        # Create task with correct ID
        task_with_id = task.__class__(
            **{
                **task.__dict__,
                "task_id": task_id,
            }
        )
        
        # Should pass validation
        rules = validate_task(task_with_id)
        rule_ids = [r.rule_id for r in rules]
        assert "T2" in rule_ids

    def test_modified_field_invalidates_task_id(self):
        """Changing an identity-bearing field must invalidate the old task_id."""
        task = TaskRecord(
            schema_version=1,
            task_id="task_placeholder",
            template=("test.template", 1),
            category="SYN",
            protocol=Protocol(kind="standalone"),
            environment_id="env_0000000000000000000000000000000000000000000000000000000000000000",
            difficulty=Difficulty(
                level=1,
                reasoning_steps=1,
                nesting_depth=1,
                control_flow="none",
                state="none",
            ),
            information_condition="FULL_DOC",
            prompt=Prompt(
                template=("prompt.answer", 1),
                example_policy="neutral",
                public_examples=["(add 1 2)"],
                query="(add 3 4)",
            ),
            answer_spec=AnswerSpec(
                type="value",
                kind="int",
                chance_floor_ppm=0,
            ),
            expected=Expected(
                value={"kind": "int", "value": 7}
            ),
            evaluation=Evaluation(
                method="exact_match",
                limits={"max_steps": 100000, "max_call_depth": 100},
                tests=[],
            ),
        )
        
        # Compute task_id
        task_id = compute_task_id(task)
        
        # Create modified task with same ID (should fail)
        modified_task = task.__class__(
            **{
                **task.__dict__,
                "task_id": task_id,
                "environment_id": "env_modified_00000000000000000000000000000000000000000000000000000000000000",
            }
        )
        
        # Should fail with T2 error because environment_id changed
        with pytest.raises(ValidationError) as exc_info:
            validate_task(modified_task)
        
        assert exc_info.value.rule == "T2"

    def test_dict_input_equivalent_validation(self):
        """Dict and dataclass inputs must follow equivalent T2 rules."""
        task = TaskRecord(
            schema_version=1,
            task_id="task_placeholder",
            template=("test.template", 1),
            category="SYN",
            protocol=Protocol(kind="standalone"),
            environment_id="env_0000000000000000000000000000000000000000000000000000000000000000",
            difficulty=Difficulty(
                level=1,
                reasoning_steps=1,
                nesting_depth=1,
                control_flow="none",
                state="none",
            ),
            information_condition="FULL_DOC",
            prompt=Prompt(
                template=("prompt.answer", 1),
                example_policy="neutral",
                public_examples=["(add 1 2)"],
                query="(add 3 4)",
            ),
            answer_spec=AnswerSpec(
                type="value",
                kind="int",
                chance_floor_ppm=0,
            ),
            expected=Expected(
                value={"kind": "int", "value": 7}
            ),
            evaluation=Evaluation(
                method="exact_match",
                limits={"max_steps": 100000, "max_call_depth": 100},
                tests=[],
            ),
        )
        
        # Compute correct ID for dataclass
        correct_id = compute_task_id(task)
        
        # Test with correct ID - should pass
        task_dict = task.to_canonical_dict()
        task_dict["task_id"] = correct_id
        rules = validate_task(task_dict)
        rule_ids = [r.rule_id for r in rules]
        assert "T2" in rule_ids
        
        # Test with wrong ID - should fail
        task_dict_wrong = task.to_canonical_dict()
        task_dict_wrong["task_id"] = "task_wrong"
        with pytest.raises(ValidationError) as exc_info:
            validate_task(task_dict_wrong)
        assert exc_info.value.rule == "T2"
