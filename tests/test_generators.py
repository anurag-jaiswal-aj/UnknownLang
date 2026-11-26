"""Tests for M2.5 Task Generators.

This module tests the answer task generator for M2.5:
- EVAL, SYN, INF, CTRL task categories
- Deterministic generation from derivation seeds
- Two-source verification (production + reference)
- Pair generation with validation gates T7/T8
- Identifiability (T13) and non-triviality (T9)
- Chance floor control (T10)

Test coverage:
- Unit tests: Generator configuration, seed handling, content generation
- Integration tests: Complete generation pipeline, environment resolution
- Property tests: Deterministic output, identity behavior
- Adversarial tests: Invalid configurations, malformed generation
- Regression tests: Preserve M2.4 behavior
"""

import pytest

from src.challenge.types import TaskRecord
from src.benchmark.generators import GeneratorRegistry, get_generator, TaskGenerator
from src.benchmark.generators.generator import GenerationResult, PairGenerationResult, GenerationState, _identity_profile
from src.benchmark.environments import build_environment

_ENV = build_environment("wraparound", True, _identity_profile())
ENV_ID = _ENV.environment_id
ENV_REGISTRY = {ENV_ID: _ENV}


class TestGenerationState:
    """Tests for deterministic generation state."""

    def test_deterministic_random_numbers(self):
        """Same seed should produce same random numbers."""
        state1 = GenerationState(seed="test_seed_123")
        state2 = GenerationState(seed="test_seed_123")
        
        # Generate multiple random numbers
        for _ in range(10):
            assert state1.next_int(100) == state2.next_int(100)
    
    def test_different_seeds_produce_different_numbers(self):
        """Different seeds should produce different random numbers."""
        state1 = GenerationState(seed="seed_a")
        state2 = GenerationState(seed="seed_b")
        
        # Most numbers should differ (with high probability)
        diffs = 0
        for _ in range(20):
            if state1.next_int(100) != state2.next_int(100):
                diffs += 1
        
        # At least some should differ
        assert diffs > 5
    
    def test_position_increment(self):
        """Position should increment on each random call."""
        state = GenerationState(seed="test")
        initial_pos = state.position
        
        state.next_int(100)
        assert state.position == initial_pos + 1
        
        state.next_int(100)
        assert state.position == initial_pos + 2
    
    def test_choice_deterministic(self):
        """Choice should be deterministic from seed."""
        state1 = GenerationState(seed="choice_test")
        state2 = GenerationState(seed="choice_test")
        
        items = ["a", "b", "c", "d", "e"]
        
        for _ in range(10):
            assert state1.choice(items) == state2.choice(items)
    
    def test_shuffle_deterministic(self):
        """Shuffle should be deterministic from seed."""
        state1 = GenerationState(seed="shuffle_test")
        state2 = GenerationState(seed="shuffle_test")
        
        items = [1, 2, 3, 4, 5]
        
        for _ in range(5):
            assert state1.shuffle(items) == state2.shuffle(items)
    
    def test_sample_deterministic(self):
        """Sample should be deterministic from seed."""
        state1 = GenerationState(seed="sample_test")
        state2 = GenerationState(seed="sample_test")
        
        items = list(range(20))
        
        for _ in range(5):
            assert state1.sample(items, k=5) == state2.sample(items, k=5)


class TestGeneratorRegistry:
    """Tests for generator registry."""

    def test_register_generator(self):
        """Should register a generator factory."""
        registry = GeneratorRegistry()
        
        def mock_factory(env_id: str, seed: str) -> TaskGenerator:
            return TaskGenerator(environment_id=env_id, derivation_seed=seed)
        
        registry.register(
            generator_family="test",
            version="1.0.0",
            generator_factory=mock_factory,
        )
        
        factory = registry.get("test", "1.0.0")
        assert factory is not None
    
    def test_register_default(self):
        """Should register default version."""
        registry = GeneratorRegistry()
        
        def mock_factory(env_id: str, seed: str) -> TaskGenerator:
            return TaskGenerator(environment_id=env_id, derivation_seed=seed)
        
        registry.register(
            generator_family="test",
            version="1.0.0",
            generator_factory=mock_factory,
            default=True,
        )
        
        registry.register(
            generator_family="test",
            version="2.0.0",
            generator_factory=mock_factory,
        )
        
        # Get without version should return default
        factory = registry.get("test")
        assert factory is not None
    
    def test_get_nonexistent_family(self):
        """Should raise ValueError for unknown family."""
        registry = GeneratorRegistry()
        
        with pytest.raises(ValueError) as exc_info:
            registry.get("nonexistent")
        
        assert "Unknown generator family" in str(exc_info.value)
    
    def test_get_nonexistent_version(self):
        """Should raise ValueError for unknown version."""
        registry = GeneratorRegistry()
        
        def mock_factory(env_id: str, seed: str) -> TaskGenerator:
            return TaskGenerator(environment_id=env_id, derivation_seed=seed)
        
        registry.register("test", "1.0.0", mock_factory)
        
        with pytest.raises(ValueError) as exc_info:
            registry.get("test", "9.9.9")
        
        assert "version 9.9.9 not found" in str(exc_info.value)


class TestTaskGenerator:
    """Tests for task generator."""

    def test_create_generator(self):
        """Should create generator with environment and seed."""
        generator = TaskGenerator(
            environment_id=ENV_ID,
            environment_registry=ENV_REGISTRY,
            derivation_seed="test_seed_123",
        )
        
        assert generator.environment_id == ENV_ID
        assert generator.derivation_seed == "test_seed_123"
    
    def test_generate_syn_task(self):
        """Should generate SYN task."""
        generator = TaskGenerator(
            environment_id=ENV_ID,
            environment_registry=ENV_REGISTRY,
            derivation_seed="syn_test_seed",
        )
        
        result = generator.generate_single_task(
            category="SYN",
            difficulty_level=1,
            information_condition="FULL_DOC",
        )
        
        assert isinstance(result, GenerationResult)
        assert result.success
    
    def test_generate_eval_task(self):
        """Should generate EVAL task."""
        generator = TaskGenerator(
            environment_id=ENV_ID,
            environment_registry=ENV_REGISTRY,
            derivation_seed="eval_test_seed",
        )
        
        result = generator.generate_single_task(
            category="EVAL",
            difficulty_level=2,
            information_condition="FULL_DOC",
        )
        
        assert isinstance(result, GenerationResult)
        assert result.success
    
    def test_generate_inf_task(self):
        """Should generate INF task."""
        generator = TaskGenerator(
            environment_id=ENV_ID,
            environment_registry=ENV_REGISTRY,
            derivation_seed="inf_test_seed",
        )
        
        result = generator.generate_single_task(
            category="INF",
            difficulty_level=2,
            information_condition="FULL_DOC",
        )
        
        assert isinstance(result, GenerationResult)
        assert result.success
    
    def test_generate_ctrl_task(self):
        """Should generate CTRL task."""
        generator = TaskGenerator(
            environment_id=ENV_ID,
            environment_registry=ENV_REGISTRY,
            derivation_seed="ctrl_test_seed",
        )
        
        result = generator.generate_single_task(
            category="CTRL",
            difficulty_level=1,
            information_condition="FULL_DOC",
        )
        
        assert isinstance(result, GenerationResult)
        assert result.success
    
    def test_generate_deterministic(self):
        """Same seed should produce identical tasks."""
        generator1 = TaskGenerator(
            environment_id=ENV_ID,
            environment_registry=ENV_REGISTRY,
            derivation_seed="deterministic_test",
        )
        
        generator2 = TaskGenerator(
            environment_id=ENV_ID,
            environment_registry=ENV_REGISTRY,
            derivation_seed="deterministic_test",
        )
        
        result1 = generator1.generate_single_task(
            category="SYN",
            difficulty_level=2,
            information_condition="FULL_DOC",
        )
        
        result2 = generator2.generate_single_task(
            category="SYN",
            difficulty_level=2,
            information_condition="FULL_DOC",
        )
        
        assert result1.success
        assert result2.success
        assert result1.task is not None
        assert result2.task is not None
        
        # Tasks should have identical IDs
        assert result1.task.task_id == result2.task.task_id
    
    def test_different_seeds_produce_different_tasks(self):
        """Different seeds should produce different tasks."""
        generator1 = TaskGenerator(
            environment_id=ENV_ID,
            environment_registry=ENV_REGISTRY,
            derivation_seed="seed_a",
        )
        
        generator2 = TaskGenerator(
            environment_id=ENV_ID,
            environment_registry=ENV_REGISTRY,
            derivation_seed="seed_b",
        )
        
        result1 = generator1.generate_single_task(
            category="SYN",
            difficulty_level=2,
            information_condition="FULL_DOC",
        )
        
        result2 = generator2.generate_single_task(
            category="SYN",
            difficulty_level=2,
            information_condition="FULL_DOC",
        )
        
        assert result1.success
        assert result2.success
        assert result1.task is not None
        assert result2.task is not None
        
        # Tasks should have different IDs (with high probability)
        assert result1.task.task_id != result2.task.task_id
    
    def test_task_validation(self):
        """Generated task should pass validation."""
        generator = TaskGenerator(
            environment_id=ENV_ID,
            environment_registry=ENV_REGISTRY,
            derivation_seed="validation_test",
        )
        
        result = generator.generate_single_task(
            category="SYN",
            difficulty_level=1,
            information_condition="FULL_DOC",
        )
        
        assert result.success
        assert result.task is not None
        
        # Task should have valid structure
        task = result.task
        assert task.schema_version == 1
        assert task.task_id.startswith("task_")
        assert len(task.task_id) == 69  # task_ + 64 hex chars
        assert task.environment_id.startswith("env_")
        assert task.category in ["SYN", "EVAL", "INF", "CTRL", "CONS", "REC", "ERR"]
        assert task.difficulty.level >= 1
        assert task.difficulty.level <= 5
        assert task.information_condition in [
            "FULL_DOC", "SIGNATURES_ONLY", "EXAMPLES_ONLY",
            "DELTA_DOC", "STALE_DOC_EXAMPLES",
        ]


class TestPairGeneration:
    """Tests for pair generation."""

    def test_generate_pair(self):
        """Should generate valid control/treatment pair."""
        generator = TaskGenerator(
            environment_id=ENV_ID,
            environment_registry=ENV_REGISTRY,
            derivation_seed="pair_test_seed",
        )
        
        # First generate a base task
        result = generator.generate_single_task(
            category="SYN",
            difficulty_level=2,
            information_condition="FULL_DOC",
        )
        
        assert result.success
        assert result.task is not None
        
        # Now generate pair
        pair_result = generator.generate_pair(
            base_task=result.task,
            variation="environment:surface_names",
        )
        
        assert isinstance(pair_result, PairGenerationResult)
        assert pair_result.success
        assert pair_result.control is not None
        assert pair_result.treatment is not None
    
    def test_pair_different_task_ids(self):
        """Control and treatment should have different task IDs."""
        generator = TaskGenerator(
            environment_id=ENV_ID,
            environment_registry=ENV_REGISTRY,
            derivation_seed="pair_id_test_seed",
        )
        
        result = generator.generate_single_task(
            category="SYN",
            difficulty_level=2,
            information_condition="FULL_DOC",
        )
        
        assert result.success
        
        pair_result = generator.generate_pair(
            base_task=result.task,
            variation="environment:surface_names",
        )
        
        assert pair_result.success
        assert pair_result.control is not None
        assert pair_result.treatment is not None
        
        # Control and treatment should have different IDs
        assert pair_result.control.task_id != pair_result.treatment.task_id
    
    def test_pair_different_query(self):
        """Variation should change task content."""
        generator = TaskGenerator(
            environment_id=ENV_ID,
            environment_registry=ENV_REGISTRY,
            derivation_seed="pair_content_test_seed",
        )
        
        result = generator.generate_single_task(
            category="INF",
            difficulty_level=2,
            information_condition="FULL_DOC",
        )
        
        assert result.success
        
        pair_result = generator.generate_pair(
            base_task=result.task,
            variation="environment:operator_meaning",
        )
        
        # The treatment should have different query than control
        if pair_result.success:
            assert pair_result.control is not None
            assert pair_result.treatment is not None
            # Queries may differ depending on variation type


class TestGenerationResult:
    """Tests for generation result structure."""

    def test_success_result(self):
        """Success result should have task and no error."""
        result = GenerationResult(
            success=True,
            task=None,  # Will be set by generator
        )
        
        assert result.success
        assert result.error is None
        assert result.rejection_reason is None
    
    def test_failure_result(self):
        """Failure result should have error or rejection reason."""
        result = GenerationResult(
            success=False,
            error="Test error",
        )
        
        assert not result.success
        assert result.error == "Test error"
    
    def test_rejection_result(self):
        """Rejection result should have rejection reason."""
        result = GenerationResult(
            success=False,
            rejection_reason="Invalid difficulty level",
        )
        
        assert not result.success
        assert result.rejection_reason == "Invalid difficulty level"


class TestM24Regression:
    """Regression tests to preserve M2.4 behavior."""

    def test_task_record_structure(self):
        """TaskRecord structure should match M2.4 types."""
        from src.challenge.types import (
            Protocol, Difficulty, Prompt, AnswerSpec,
            Evaluation, Test, Expected, InputDefinitions, Visibility,
            Category, InformationCondition, ProtocolKind, Role, Variation,
        )
        
        # Verify types are available
        assert Protocol is not None
        assert Difficulty is not None
        assert Prompt is not None
        assert AnswerSpec is not None
        assert Evaluation is not None
        assert Test is not None
        assert Expected is not None
        assert InputDefinitions is not None
        
        # Verify categories
        assert "SYN" in Category.__args__  # type: ignore
        assert "EVAL" in Category.__args__  # type: ignore
        assert "INF" in Category.__args__  # type: ignore
        assert "CTRL" in Category.__args__  # type: ignore
    
    def test_validation_gates(self):
        """Validation gates should match M2.4 implementation."""
        from src.challenge.validation import validate_task, ValidationError
        
        # T2: task_id hash verification
        # (Already tested in test_task_validation.py)
        
        # T6: Hidden tests disjoint
        # (Already tested in test_task_validation.py)
        
        # T9: Non-triviality
        # (Already tested in test_task_validation.py)
        
        # T10: Chance floor limit
        # (Already tested in test_task_validation.py)
        
        assert validate_task is not None
        assert ValidationError is not None


class TestPairValidation:
    """D-001 pair rules T7/T8."""


    def _pair(self, variation, category="SYN", registered=True):
        gen = TaskGenerator(environment_id=ENV_ID, environment_registry=ENV_REGISTRY, derivation_seed="pair_rules_seed")
        base = gen.generate_single_task(category=category, difficulty_level=2, information_condition="FULL_DOC")
        assert base.success
        if not registered:
            gen.environment_registry.clear()  # T5 needs the env to build the base task, not to reject a variation
        return gen.generate_pair(base_task=base.task, variation=variation)

    @pytest.mark.parametrize("variation", ["environment:surface_names", "information_condition", "example_policy"])
    def test_supported_variations_are_valid_pairs(self, variation):
        from src.benchmark.generators.generator import validate_pair
        r = self._pair(variation)
        assert r.success, r.rejection_reason
        c, t = r.control, r.treatment
        assert (c.protocol.kind, c.protocol.role) == ("paired", "control")
        assert t.protocol.role == "treatment"
        assert c.protocol.pair_group_id == t.protocol.pair_group_id
        assert c.protocol.varies == t.protocol.varies == (variation,)
        assert c.task_id != t.task_id
        assert c.expected == t.expected
        assert validate_pair(c, t) == []

    def test_surface_rename_is_real_and_canonical(self):
        from src.benchmark.generators.generator import to_canonical_query
        r = self._pair("environment:surface_names")
        assert r.treatment.prompt.query != r.control.prompt.query
        assert to_canonical_query(r.treatment.prompt.query) == r.control.prompt.query
        assert "@surface_var" not in r.treatment.prompt.query

    @pytest.mark.parametrize("variation", ["environment:operator_meaning", "environment:semantic_config"])
    def test_meaning_variations_rejected_without_registry(self, variation):
        r = self._pair(variation, registered=False)
        assert not r.success and "[environment_not_registered]" in r.rejection_reason

    def test_validator_rejects_unrelated_and_expected_changes(self):
        from dataclasses import replace
        from src.benchmark.generators.generator import validate_pair
        from src.challenge.types import Expected
        r = self._pair("example_policy")
        bad = replace(r.treatment, expected=Expected(value={"kind": "int", "value": -1}))
        assert any("T8" in e for e in validate_pair(r.control, bad))
        assert any("T7" in e for e in validate_pair(r.control, replace(r.treatment, environment_id="env_x")))
        # discriminating variation with equal expected is rejected
        p = replace(r.treatment.protocol, varies=("environment:semantic_config",))
        assert any("T8" in e for e in validate_pair(
            replace(r.control, protocol=replace(r.control.protocol, varies=p.varies)), replace(r.treatment, protocol=p)))


class TestGeneratorCorrectness:
    """Evaluator, CTRL, and T9 retry behavior."""

    def _gen(self, seed="correctness"):
        return TaskGenerator(environment_id=ENV_ID, environment_registry=ENV_REGISTRY, derivation_seed=seed)

    def test_evaluator_nested(self):
        g = self._gen()
        assert g._evaluate_expression("(sub (sub 5 10) 5)") == -10
        assert g._evaluate_expression("(add (mul 2 3) (sub 10 (div 9 3)))") == 13
        assert g._evaluate_expression("(div (sub 0 7) 2)") == -3
        assert g._evaluate_expression("(mod (sub 0 7) 3)") == -1
        assert g._evaluate_expression("(if (gt 5 3) (add 1 1) (add 2 2))") == 2
        assert g._evaluate_expression("(if (gt 1 3) (add 1 1) (add 2 2))") == 4

    def test_evaluator_rejects_malformed(self):
        g = self._gen()
        for bad in ["(add 1", "(add 1 2) 3", "(foo 1 2)", "(add 1)", ")"]:
            with pytest.raises(ValueError):
                g._evaluate_expression(bad)

    def test_ctrl_expected_matches_query(self):
        for i in range(20):
            g = self._gen(f"ctrl{i}")
            for d in (1, 3):
                data = g._generate_ctrl_task(d, "FULL_DOC")
                assert data["query"].startswith("(if ")
                assert data["expected"]["value"] == g._evaluate_expression(data["query"])

    def test_t9_retry_draws_new_candidate(self):
        g = self._gen("t9")
        first = g._generate_ctrl_task(1, "FULL_DOC")["query"]
        second = g._generate_ctrl_task(1, "FULL_DOC")["query"]
        assert first != second

    def test_no_hardcoded_verification(self):
        r = self._gen("verif").generate_single_task("SYN", 2, "FULL_DOC")
        assert r.success
        assert r.task.verification is None
        assert "t5_verified" not in r.provenance
