"""Tests for task identity calculation and verification."""

import pytest

from src.challenge.types import TaskRecord, Protocol, Difficulty, Prompt, AnswerSpec
from src.challenge.types import Evaluation, Test, Expected, InputDefinitions
from src.challenge.identity import compute_task_id, verify_task_id_determinism
from src.benchmark.canonical import canonical_bytes, sha256_hex


class TestComputeTaskId:
    """Tests for compute_task_id() function."""

    def test_compute_task_id_deterministic(self):
        """Same task should always produce same identity."""
        # Create a minimal task
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
        
        # Compute ID
        task_id = compute_task_id(task)
        
        # Verify determinism
        assert task_id == compute_task_id(task)
        assert task_id == compute_task_id(task)
        
        # Verify format: "task_" (5) + 64 hex chars = 69 total
        assert task_id.startswith("task_")
        assert len(task_id) == 69
        assert all(c in "0123456789abcdef" for c in task_id[5:])

    def test_compute_task_id_changes_with_field(self):
        """Different field values should produce different identities."""
        base_task = TaskRecord(
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
        
        # Change query
        modified_task = base_task.__class__(
            **{
                **base_task.__dict__,
                "prompt": Prompt(
                    template=base_task.prompt.template,
                    example_policy=base_task.prompt.example_policy,
                    public_examples=base_task.prompt.public_examples,
                    query="(add 5 6)",  # Different query
                ),
            }
        )
        
        assert compute_task_id(base_task) != compute_task_id(modified_task)

    def test_compute_task_id_excludes_excluded_fields(self):
        """Excluded fields (verification, provenance, notes) should not affect identity."""
        base_task = TaskRecord(
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
        
        # Create variants with different excluded fields
        task_with_verification = base_task.__class__(
            **{
                **base_task.__dict__,
                "verification": {
                    "sources": ["production", "reference"],
                    "agreement": True,
                },
            }
        )
        
        task_with_provenance = base_task.__class__(
            **{
                **base_task.__dict__,
                "provenance": {
                    "generator": "test",
                    "version": "1.0.0",
                },
            }
        )
        
        task_with_notes = base_task.__class__(
            **{
                **base_task.__dict__,
                "notes": "This is a test note",
            }
        )
        
        # All should have same identity
        base_id = compute_task_id(base_task)
        assert compute_task_id(task_with_verification) == base_id
        assert compute_task_id(task_with_provenance) == base_id
        assert compute_task_id(task_with_notes) == base_id

    def test_verify_task_id_determinism(self):
        """verify_task_id_determinism should confirm identity stability."""
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
        
        assert verify_task_id_determinism(task, iterations=10) is True


class TestTaskIdFormat:
    """Tests for task_id format and validation."""

    def test_task_id_prefix(self):
        """Task ID should start with 'task_'."""
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
        
        task_id = compute_task_id(task)
        assert task_id.startswith("task_")

    def test_task_id_hex_characters(self):
        """Task ID should contain only lowercase hex after prefix."""
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
        
        task_id = compute_task_id(task)
        hex_part = task_id[5:]  # Skip "task_" prefix
        
        assert len(hex_part) == 64
        assert all(c in "0123456789abcdef" for c in hex_part)

    def test_dict_input_produces_same_identity(self):
        """Dict input should produce same identity as TaskRecord."""
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
        
        # Get the canonical dict (without task_id)
        canonical_dict = task.to_canonical_dict()
        
        # Compute ID from TaskRecord
        task_id_from_record = compute_task_id(task)
        
        # Compute ID from canonical dict (same data structure)
        task_id_from_dict = compute_task_id(canonical_dict)
        
        assert task_id_from_record == task_id_from_dict
