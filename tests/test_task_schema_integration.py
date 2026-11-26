"""Integration tests for task schema components."""

import pytest

from src.challenge.types import (
    TaskRecord, Protocol, Difficulty, Prompt, AnswerSpec,
    Evaluation, Test, Expected, InputDefinitions, Visibility
)
from src.challenge.identity import compute_task_id, verify_identity_excludes_fields
from src.challenge.validation import validate_task, ValidationError
from src.challenge.projection import project_public
from src.benchmark.prompts import build_answer_prompt
from src.benchmark.language_reference import generate_language_reference


class TestSchemaIntegration:
    """Integration tests for schema components working together."""

    def test_full_task_lifecycle(self):
        """Test full task lifecycle: create -> compute ID -> validate -> project -> prompt."""
        # Step 1: Create task
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
        
        # Step 2: Compute task ID
        task_id = compute_task_id(task)
        assert task_id.startswith("task_")
        assert len(task_id) == 69
        
        # Step 3: Validate task (with correct ID)
        task_with_id = task.__class__(
            **{
                **task.__dict__,
                "task_id": task_id,
            }
        )
        
        rules = validate_task(task_with_id)
        rule_ids = [r.rule_id for r in rules]
        assert "T1" in rule_ids
        assert "T2" in rule_ids
        
        # Step 4: Project to public view
        public = project_public(task_with_id)
        assert hasattr(public, 'environment_id')
        assert hasattr(public, 'prompt')
        assert not hasattr(public, 'difficulty')
        
        # Step 5: Build prompt
        environment = {
            "environment_id": public.environment_id,
            "surface_profile": {
                "operators": {"add": "add"},
                "keywords": {},
                "literals": {},
            },
            "semantic": {},
        }
        
        from src.benchmark.prompts import PromptBundle
        bundle = build_answer_prompt(public, environment)
        assert isinstance(bundle, PromptBundle)

    def test_task_with_hidden_definitions(self):
        """Test task with hidden definitions flows through pipeline."""
        task = TaskRecord(
            schema_version=1,
            task_id="task_placeholder",
            template=("test.template", 1),
            category="REC",
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
                template=("prompt.program", 1),
                example_policy="neutral",
                public_examples=["(black_box 5)"],
                query="(black_box 10)",
            ),
            answer_spec=AnswerSpec(
                type="program",
                kind=None,
                form="definitions_only",
            ),
            expected=Expected(
                value={"kind": "int", "value": 20}
            ),
            evaluation=Evaluation(
                method="test_suite",
                limits={"max_steps": 100000, "max_call_depth": 100},
                tests=[
                    Test(
                        test_id="test1",
                        call="(black_box 10)",
                        expected={"kind": "int", "value": 20},
                        visibility="public",
                    ),
                ],
            ),
            input=InputDefinitions(
                source="(def black_box (n) (add n n))",  # Hidden implementation
                visibility="hidden",
                must_define=[("black_box", 1)],
            ),
        )
        
        # Compute ID
        task_id = compute_task_id(task)
        
        # Project
        public = project_public(task.__class__(
            **{**task.__dict__, "task_id": task_id}
        ))
        
        # Hidden definition should be filtered
        assert public.input is not None
        assert public.input.source == ""  # Hidden

    def test_task_with_hidden_tests(self):
        """Test task with hidden tests flows through pipeline."""
        task = TaskRecord(
            schema_version=1,
            task_id="task_placeholder",
            template=("test.template", 1),
            category="EVAL",
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
                template=("prompt.program", 1),
                example_policy="neutral",
                public_examples=["(add 1 2)"],
                query="(add 3 4)",
            ),
            answer_spec=AnswerSpec(
                type="program",
                kind=None,
                form="definitions_only",
            ),
            expected=Expected(
                value={"kind": "int", "value": 7}
            ),
            evaluation=Evaluation(
                method="test_suite",
                limits={"max_steps": 100000, "max_call_depth": 100},
                tests=[
                    Test(
                        test_id="public_test",
                        call="(add 5 6)",
                        expected={"kind": "int", "value": 11},
                        visibility="public",
                    ),
                    Test(
                        test_id="hidden_test",
                        call="(mul 3 4)",
                        expected={"kind": "int", "value": 12},
                        visibility="hidden",
                    ),
                ],
            ),
        )
        
        # Project
        public = project_public(task)
        
        # Only public tests should remain
        assert len(public.evaluation.tests) == 1
        assert public.evaluation.tests[0].test_id == "public_test"

    def test_language_reference_generation(self):
        """Test language reference generation respects information conditions."""
        environment = {
            "environment_id": "env_test",
            "surface_profile": {
                "operators": {"add": "add", "sub": "sub"},
                "keywords": {"forge": "def"},
                "literals": {"aye": "true", "nay": "false"},
            },
            "semantic": {
                "arithmetic": "wraparound",
                "short_circuit": True,
            },
        }
        
        # Full doc
        ref_full = generate_language_reference(environment, "FULL_DOC")
        assert "Semantic Configuration" in ref_full
        assert "arithmetic" in ref_full
        
        # Signatures only
        ref_sig = generate_language_reference(environment, "SIGNATURES_ONLY")
        assert "Semantic Configuration" not in ref_sig
        
        # Examples only
        ref_ex = generate_language_reference(environment, "EXAMPLES_ONLY")
        assert "Semantic Configuration" not in ref_ex

    def test_id_determinism_excludes_fields(self):
        """Test that excluded fields don't affect identity."""
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
        
        base_id = compute_task_id(task)
        
        # Add verification
        task_with_verification = task.__class__(
            **{
                **task.__dict__,
                "verification": {
                    "sources": ["production", "reference"],
                    "agreement": True,
                },
            }
        )
        
        # Add provenance
        task_with_provenance = task.__class__(
            **{
                **task.__dict__,
                "provenance": {
                    "generator": "test",
                    "version": "1.0.0",
                },
            }
        )
        
        # Add notes
        task_with_notes = task.__class__(
            **{
                **task.__dict__,
                "notes": "Test note",
            }
        )
        
        # All should have same ID
        assert compute_task_id(task_with_verification) == base_id
        assert compute_task_id(task_with_provenance) == base_id
        assert compute_task_id(task_with_notes) == base_id


class TestValidationGateCoverage:
    """Test that validation gates are properly implemented."""

    def test_t2_implementation(self):
        """T2 should check task_id equals recomputed hash."""
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
        
        # Wrong ID
        task_wrong = task.__class__(
            **{
                **task.__dict__,
                "task_id": "task_wrong_id",
            }
        )
        
        with pytest.raises(ValidationError) as exc_info:
            validate_task(task_wrong)
        
        assert exc_info.value.rule == "T2"
        
        # Correct ID
        task_correct = task.__class__(
            **{
                **task.__dict__,
                "task_id": compute_task_id(task),
            }
        )
        
        # Should not raise
        validate_task(task_correct)

    def test_t6_implementation(self):
        """T6 should check hidden tests disjoint from public."""
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
                        "test_id": "hidden",
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

    def test_t9_implementation(self):
        """T9 should check non-triviality."""
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
                query="(add 3 4)",  # The expected value should appear as a literal
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

    def test_t10_implementation(self):
        """T10 should check chance_floor_ppm <= 100000."""
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
                chance_floor_ppm=100001,  # Too high
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
