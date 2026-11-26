"""Tests for prompt generation and language reference."""

import pytest

from src.challenge.types import (
    TaskRecord, Protocol, Difficulty, Prompt, AnswerSpec,
    Evaluation, Test, Expected, PublicTask
)
from src.benchmark.prompts import (
    build_answer_prompt,
    build_program_prompt,
    PromptBundle,
    get_registry,
)
from src.benchmark.language_reference import (
    generate_language_reference,
    get_supported_information_conditions,
)


class TestBuildAnswerPrompt:
    """Tests for build_answer_prompt() function."""

    def test_build_answer_prompt_returns_bundle(self):
        """build_answer_prompt should return PromptBundle."""
        public_task = PublicTask(
            schema_version=1,
            task_id="task_placeholder",
            template=("test.template", 1),
            category="SYN",
            protocol=Protocol(kind="standalone"),
            environment_id="env_0000000000000000000000000000000000000000000000000000000000000000",
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
            evaluation=Evaluation(
                method="exact_match",
                limits={"max_steps": 100000, "max_call_depth": 100},
                tests=[],
            ),
        )
        
        environment = {
            "environment_id": public_task.environment_id,
            "surface_profile": {
                "operators": {"add": "add"},
                "keywords": {},
                "literals": {},
            },
            "semantic": {},
        }
        
        bundle = build_answer_prompt(public_task, environment)
        
        assert isinstance(bundle, PromptBundle)
        assert bundle.system_message
        assert bundle.user_message
        assert bundle.reference_document
        assert bundle.template_id == ("prompt.answer", 1)

    def test_build_answer_prompt_includes_reference(self):
        """Answer prompt should include language reference."""
        public_task = PublicTask(
            schema_version=1,
            task_id="task_placeholder",
            template=("test.template", 1),
            category="SYN",
            protocol=Protocol(kind="standalone"),
            environment_id="env_0000000000000000000000000000000000000000000000000000000000000000",
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
            evaluation=Evaluation(
                method="exact_match",
                limits={"max_steps": 100000, "max_call_depth": 100},
                tests=[],
            ),
        )
        
        environment = {
            "environment_id": public_task.environment_id,
            "surface_profile": {
                "operators": {"add": "add"},
                "keywords": {},
                "literals": {},
            },
            "semantic": {"arithmetic": "wraparound", "short_circuit": True},
        }
        
        bundle = build_answer_prompt(public_task, environment)
        
        assert "Language Reference" in bundle.user_message
        # Check for both lowercase and title case versions
        assert "arithmetic" in bundle.reference_document.lower()
        # Check for short-circuit (could be "short-circuit" or "Short-circuit evaluation")
        assert "short" in bundle.reference_document.lower() and "circuit" in bundle.reference_document.lower()

    def test_build_answer_prompt_with_examples(self):
        """Answer prompt should include public examples."""
        public_task = PublicTask(
            schema_version=1,
            task_id="task_placeholder",
            template=("test.template", 1),
            category="SYN",
            protocol=Protocol(kind="standalone"),
            environment_id="env_0000000000000000000000000000000000000000000000000000000000000000",
            information_condition="EXAMPLES_ONLY",
            prompt=Prompt(
                template=("prompt.answer", 1),
                example_policy="neutral",
                public_examples=["(add 1 2)", "(add 3 4)"],
                query="(add 5 6)",
            ),
            answer_spec=AnswerSpec(
                type="value",
                kind="int",
                chance_floor_ppm=0,
            ),
            evaluation=Evaluation(
                method="exact_match",
                limits={"max_steps": 100000, "max_call_depth": 100},
                tests=[],
            ),
        )
        
        environment = {
            "environment_id": public_task.environment_id,
            "surface_profile": {
                "operators": {"add": "add"},
                "keywords": {},
                "literals": {},
            },
            "semantic": {},
        }
        
        bundle = build_answer_prompt(public_task, environment)
        
        assert "Public Examples" in bundle.user_message
        assert "(add 1 2)" in bundle.user_message
        assert "(add 3 4)" in bundle.user_message
        assert "(add 5 6)" in bundle.user_message  # Query


class TestBuildProgramPrompt:
    """Tests for build_program_prompt() function."""

    def test_build_program_prompt_returns_bundle(self):
        """build_program_prompt should return PromptBundle."""
        public_task = PublicTask(
            schema_version=1,
            task_id="task_placeholder",
            template=("test.template", 1),
            category="CONS",
            protocol=Protocol(kind="standalone"),
            environment_id="env_0000000000000000000000000000000000000000000000000000000000000000",
            information_condition="FULL_DOC",
            prompt=Prompt(
                template=("prompt.program", 1),
                example_policy="neutral",
                public_examples=[],
                query="",
                spec="Write a function that doubles its input",
            ),
            answer_spec=AnswerSpec(
                type="program",
                kind=None,
                form="definitions_only",
            ),
            evaluation=Evaluation(
                method="test_suite",
                limits={"max_steps": 100000, "max_call_depth": 100},
                tests=[],
            ),
        )
        
        environment = {
            "environment_id": public_task.environment_id,
            "surface_profile": {
                "operators": {"add": "add"},
                "keywords": {},
                "literals": {},
            },
            "semantic": {},
        }
        
        bundle = build_program_prompt(public_task, environment)
        
        assert isinstance(bundle, PromptBundle)
        assert bundle.system_message
        assert bundle.user_message
        assert "Specification" in bundle.user_message
        assert "Only include definitions" in bundle.user_message


class TestGenerateLanguageReference:
    """Tests for generate_language_reference() function."""

    def test_full_doc_includes_all_sections(self):
        """FULL_DOC should include all sections."""
        environment = {
            "environment_id": "env_test",
            "surface_profile": {
                "operators": {"add": "add", "sub": "sub"},
                "keywords": {"forge": "def"},
                "literals": {"aye": "true"},
            },
            "semantic": {
                "arithmetic": "wraparound",
                "short_circuit": True,
            },
        }
        
        ref = generate_language_reference(environment, "FULL_DOC")
        
        assert "Lexical Rules" in ref
        assert "Keywords" in ref
        assert "Operators" in ref
        assert "Literals" in ref
        assert "Semantic Configuration" in ref
        assert "arithmetic" in ref
        # Check for short-circuit (case-insensitive)
        ref_lower = ref.lower()
        assert "short" in ref_lower and "circuit" in ref_lower

    def test_signatures_only_excludes_semantics(self):
        """SIGNATURES_ONLY should exclude prose semantics."""
        environment = {
            "environment_id": "env_test",
            "surface_profile": {
                "operators": {"add": "add"},
                "keywords": {},
                "literals": {},
            },
            "semantic": {},
        }
        
        ref = generate_language_reference(environment, "SIGNATURES_ONLY")
        
        assert "Lexical Rules" in ref
        assert "Operators" in ref
        assert "Semantic Configuration" not in ref

    def test_examples_only_minimal(self):
        """EXAMPLES_ONLY should be minimal."""
        environment = {
            "environment_id": "env_test",
            "surface_profile": {
                "operators": {"add": "add"},
                "keywords": {},
                "literals": {},
            },
            "semantic": {},
        }
        
        ref = generate_language_reference(environment, "EXAMPLES_ONLY")
        
        assert "Lexical Rules" in ref
        assert "Keywords" not in ref  # Keywords section should not appear when empty
        # Should not include operator meanings
        assert "add" not in ref or ref.count("add") == 1  # Only in lexical rules

    def test_invalid_condition_raises(self):
        """Invalid information condition should raise ValueError."""
        environment = {
            "environment_id": "env_test",
            "surface_profile": {},
            "semantic": {},
        }
        
        with pytest.raises(ValueError) as exc_info:
            generate_language_reference(environment, "INVALID_CONDITION")
        
        assert "INVALID_CONDITION" in str(exc_info.value)
        assert "FULL_DOC" in str(exc_info.value)

    def test_get_supported_information_conditions(self):
        """Should return set of supported conditions."""
        conditions = get_supported_information_conditions()
        
        assert "FULL_DOC" in conditions
        assert "SIGNATURES_ONLY" in conditions
        assert "EXAMPLES_ONLY" in conditions
        assert "DELTA_DOC" in conditions
        assert "STALE_DOC_EXAMPLES" in conditions


class TestTemplateRegistry:
    """Tests for template registry."""

    def test_get_registry(self):
        """get_registry should return registry instance."""
        registry = get_registry()
        
        assert registry is not None
        assert hasattr(registry, 'get')
        assert hasattr(registry, 'register')

    def test_template_registration(self):
        """Should be able to register templates."""
        registry = get_registry()
        
        # Check that default templates are registered
        assert "prompt.answer" in registry._templates
        assert "prompt.program" in registry._templates

    def test_get_default_version(self):
        """Should get default version."""
        registry = get_registry()
        
        default = registry.get_default_version("prompt.answer")
        
        assert default == 1

    def test_get_template_version(self):
        """Should get template function for version."""
        registry = get_registry()
        
        template_func = registry.get("prompt.answer", 1)
        
        assert callable(template_func)

    def test_invalid_template_raises(self):
        """Invalid template should raise ValueError."""
        registry = get_registry()
        
        with pytest.raises(ValueError) as exc_info:
            registry.get("nonexistent.template")
        
        assert "nonexistent.template" in str(exc_info.value)
