"""Tests for public projection and hidden data filtering."""

import pytest

from src.challenge.types import (
    TaskRecord, Protocol, Difficulty, Prompt, AnswerSpec,
    Evaluation, Test, Expected, InputDefinitions, Visibility, PublicTask
)
from src.challenge.projection import project_public, _project_input_public
from src.challenge.identity import compute_task_id


class TestProjectPublic:
    """Tests for project_public() function."""

    def test_public_view_excludes_expected(self):
        """Public view should not contain expected value."""
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
                value={"kind": "int", "value": 7}  # Private
            ),
            evaluation=Evaluation(
                method="exact_match",
                limits={"max_steps": 100000, "max_call_depth": 100},
                tests=[],
            ),
        )
        
        public = project_public(task)
        
        # PublicTask should not have expected attribute
        assert not hasattr(public, 'expected') or public.__dict__.get('expected') is None

    def test_public_view_excludes_hidden_tests(self):
        """Public view should only include public tests."""
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
                        visibility="hidden",  # Should be filtered
                    ),
                ],
            ),
        )
        
        public = project_public(task)
        
        # Only public tests should remain
        assert len(public.evaluation.tests) == 1
        assert public.evaluation.tests[0].test_id == "public_test"
        assert public.evaluation.tests[0].visibility == "public"

    def test_public_view_excludes_hidden_definitions(self):
        """Public view should filter hidden definitions."""
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
                public_examples=["(my_func 5)"],
                query="(my_func 10)",
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
                        call="(my_func 10)",
                        expected={"kind": "int", "value": 20},
                        visibility="public",
                    ),
                ],
            ),
            input=InputDefinitions(
                source="(def my_func (n) (if (eq n 0) 0 (add n (my_func (sub n 1)))))",
                visibility="hidden",  # Should be filtered
                must_define=[("my_func", 1)],
            ),
        )
        
        public = project_public(task)
        
        # Hidden definition should be filtered
        assert public.input is not None
        assert public.input.source == ""  # Hidden source should be empty
        assert public.input.visibility == "hidden"
        assert public.input.must_define is None  # Must define should be cleared for hidden

    def test_public_view_excludes_public_definitions(self):
        """Public view should keep public definitions."""
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
                public_examples=["(my_func 5)"],
                query="(my_func 10)",
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
                        call="(my_func 10)",
                        expected={"kind": "int", "value": 20},
                        visibility="public",
                    ),
                ],
            ),
            input=InputDefinitions(
                source="(def my_func (n) (add n n))",
                visibility="public",  # Should be kept
                must_define=[("my_func", 1)],
            ),
        )
        
        public = project_public(task)
        
        # Public definition should be kept
        assert public.input is not None
        assert public.input.source == "(def my_func (n) (add n n))"
        assert public.input.visibility == "public"

    def test_public_view_excludes_difficulty(self):
        """PublicTask should not include difficulty field (per spec 5.2)."""
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
        
        public = project_public(task)
        
        # PublicTask should not have difficulty
        assert not hasattr(public, 'difficulty') or public.__dict__.get('difficulty') is None


class TestProjectInputPublic:
    """Tests for _project_input_public() helper."""

    def test_filters_hidden_source(self):
        """Hidden source should be filtered to empty string."""
        result = _project_input_public({
            "source": "some secret code",
            "visibility": "hidden",
            "must_define": [("func", 1)],
        })
        
        assert result["source"] == ""
        assert result["visibility"] == "hidden"
        assert result["must_define"] is None

    def test_keeps_public_source(self):
        """Public source should be kept."""
        result = _project_input_public({
            "source": "public code",
            "visibility": "public",
            "must_define": [("func", 1)],
        })
        
        assert result["source"] == "public code"
        assert result["visibility"] == "public"

    def test_dataclass_input(self):
        """Should handle InputDefinitions dataclass."""
        from src.challenge.types import InputDefinitions
        
        input_defs = InputDefinitions(
            source="test source",
            visibility="hidden",
            must_define=[("func", 1)],
        )
        
        result = _project_input_public(input_defs)
        
        # Result should be InputDefinitions dataclass with filtered source
        assert result.source == ""
        assert result.visibility == "hidden"
        assert result.must_define is None


class TestLeakTest:
    """Tests for leak_test() function."""

    def test_no_leak_passes(self):
        """Task with no leaks should pass leak_test."""
        from src.challenge.types import InputDefinitions
        
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
        
        # Create a version with sentinel in hidden field
        task_with_sentinel = task.__class__(
            **{
                **task.__dict__,
                "input": InputDefinitions(
                    source="PRIVATE_SENTINEL",
                    visibility="hidden",
                ),
            }
        )
        
        # Should pass - sentinel is not in public view
        result = _project_input_public(task_with_sentinel.input)
        assert result.source == ""


class TestProjectPublicPairedTasks:
    """Tests for project_public() with paired tasks."""

    def test_protocol_role_excluded_for_paired_control(self):
        """Protocol.role should be None for paired control tasks in public view."""
        task = TaskRecord(
            schema_version=1,
            task_id="task_placeholder",
            template=("test.template", 1),
            category="SYN",
            protocol=Protocol(
                kind="paired",
                pair_group_id="pair_abc123",
                role="control",
                varies=("environment:surface_names",),
            ),
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
        
        public = project_public(task)
        
        # Protocol.role should be None in public view
        assert public.protocol.role is None
        assert public.protocol.kind == "paired"
        assert public.protocol.pair_group_id == "pair_abc123"

    def test_protocol_role_excluded_for_paired_treatment(self):
        """Protocol.role should be None for paired treatment tasks in public view."""
        task = TaskRecord(
            schema_version=1,
            task_id="task_placeholder",
            template=("test.template", 1),
            category="SYN",
            protocol=Protocol(
                kind="paired",
                pair_group_id="pair_abc123",
                role="treatment",
                varies=("environment:surface_names",),
            ),
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
        
        public = project_public(task)
        
        # Protocol.role should be None in public view
        assert public.protocol.role is None
        assert public.protocol.kind == "paired"
        assert public.protocol.pair_group_id == "pair_abc123"
