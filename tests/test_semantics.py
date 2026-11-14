"""Tests for SemanticRegistry."""

import pytest
from hypothesis import given, strategies as st

from src.language.semantics import (
    SemanticRegistry,
    SemanticSpec,
    OperationInfo,
    VALID_ARITHMETIC_MODES,
    VALID_SHORT_CIRCUIT_MODES,
    BUILTIN_OPERATIONS,
)


class TestSemanticRegistryValidation:
    """Tests for SemanticRegistry validation logic."""

    def test_valid_seed_produces_correct_semantic_spec(self):
        """Valid seed should produce correct SemanticSpec."""
        registry = SemanticRegistry()
        seed = registry.validate_seed
        from src.language.seed import LanguageSeed

        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["arithmetic"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        # Should not raise
        registry.validate_seed(seed)

    def test_invalid_arithmetic_mode_raises_validation_error(self):
        """Invalid arithmetic mode should raise ValidationError."""
        registry = SemanticRegistry()
        from src.language.seed import LanguageSeed, ValidationError

        # Create seed with invalid arithmetic mode
        # This raises ValidationError during seed creation
        with pytest.raises(ValidationError, match="Invalid arithmetic"):
            LanguageSeed(
                name="Test",
                syntax_style="lisp",
                features=["arithmetic"],
                difficulty=1,
                arithmetic="invalid-mode",
                short_circuit=True,
            )

    def test_invalid_short_circuit_value_raises_validation_error(self):
        """Invalid short_circuit value should raise ValidationError."""
        from src.language.seed import LanguageSeed, ValidationError

        # Create seed with invalid short_circuit value
        # This raises ValidationError during seed creation
        with pytest.raises(ValidationError, match="Invalid short_circuit"):
            LanguageSeed(
                name="Test",
                syntax_style="lisp",
                features=["arithmetic"],
                difficulty=1,
                arithmetic="wraparound",
                short_circuit="invalid",
            )

    def test_unsupported_feature_raises_validation_error(self):
        """Unsupported feature should raise ValidationError."""
        registry = SemanticRegistry()
        from src.language.seed import LanguageSeed

        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["unsupported-feature"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        with pytest.raises(Exception):  # ValidationError
            registry.validate_seed(seed)


class TestOperationInfoStructure:
    """Tests for OperationInfo dataclass structure."""

    def test_operation_info_has_required_fields(self):
        """OperationInfo should have all required fields."""
        op_info = OperationInfo(
            name="add",
            arity=2,
            arg_types=("int", "int"),
            return_type="int",
            semantic_mode="wraparound",
        )
        assert op_info.name == "add"
        assert op_info.arity == 2
        assert op_info.arg_types == ("int", "int")
        assert op_info.return_type == "int"
        assert op_info.semantic_mode == "wraparound"

    def test_operation_info_is_frozen(self):
        """OperationInfo should be immutable."""
        op_info = OperationInfo(
            name="add",
            arity=2,
            arg_types=("int", "int"),
            return_type="int",
            semantic_mode="wraparound",
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            op_info.name = "sub"

    def test_valid_arithmetic_modes(self):
        """Test all valid arithmetic modes."""
        for mode in VALID_ARITHMETIC_MODES:
            op_info = OperationInfo(
                name="test",
                arity=2,
                arg_types=("int", "int"),
                return_type="int",
                semantic_mode=mode,
            )
            assert op_info.semantic_mode == mode

    def test_valid_short_circuit_modes(self):
        """Test all valid short_circuit modes."""
        for mode in VALID_SHORT_CIRCUIT_MODES:
            op_info = OperationInfo(
                name="test",
                arity=2,
                arg_types=("bool", "bool"),
                return_type="bool",
                semantic_mode="short-circuit" if mode else "strict",
            )
            assert op_info.semantic_mode in ["short-circuit", "strict"]


class TestFeatureCompatibility:
    """Tests for feature compatibility between registry and seeds."""

    def test_registry_supports_arithmetic_feature(self):
        """Registry should support arithmetic feature."""
        registry = SemanticRegistry()
        from src.language.seed import LanguageSeed

        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["arithmetic"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        registry.validate_seed(seed)

    def test_registry_supports_short_circuit_feature(self):
        """Registry should support short_circuit feature."""
        registry = SemanticRegistry()
        from src.language.seed import LanguageSeed

        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["short_circuit"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        registry.validate_seed(seed)

    def test_registry_supports_both_features(self):
        """Registry should support both features together."""
        registry = SemanticRegistry()
        from src.language.seed import LanguageSeed

        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["arithmetic", "short_circuit"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        registry.validate_seed(seed)


class TestArithmeticModeMapping:
    """Tests for arithmetic mode to operation mapping."""

    def test_wraparound_maps_correctly(self):
        """wraparound arithmetic mode should map correctly."""
        registry = SemanticRegistry()
        from src.language.seed import LanguageSeed

        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["arithmetic"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        spec = registry.build_spec(seed)
        
        for op_name in ["add", "sub", "mul"]:
            assert spec.operations[op_name].semantic_mode == "wraparound"

    def test_saturating_maps_correctly(self):
        """saturating arithmetic mode should map correctly."""
        registry = SemanticRegistry()
        from src.language.seed import LanguageSeed

        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["arithmetic"],
            difficulty=1,
            arithmetic="saturating",
            short_circuit=True,
        )
        spec = registry.build_spec(seed)
        
        for op_name in ["add", "sub", "mul"]:
            assert spec.operations[op_name].semantic_mode == "saturating"

    def test_error_on_overflow_maps_correctly(self):
        """error-on-overflow arithmetic mode should map correctly."""
        registry = SemanticRegistry()
        from src.language.seed import LanguageSeed

        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["arithmetic"],
            difficulty=1,
            arithmetic="error-on-overflow",
            short_circuit=True,
        )
        spec = registry.build_spec(seed)
        
        for op_name in ["add", "sub", "mul"]:
            assert spec.operations[op_name].semantic_mode == "error-on-overflow"

    def test_div_mod_always_error_on_overflow(self):
        """Division and modulo should always use error-on-overflow."""
        from src.language.semantics import SemanticRegistry
        from src.language.seed import LanguageSeed

        for mode in VALID_ARITHMETIC_MODES:
            registry = SemanticRegistry()
            seed = LanguageSeed(
                name="Test",
                syntax_style="lisp",
                features=["arithmetic"],
                difficulty=1,
                arithmetic=mode,
                short_circuit=True,
            )
            spec = registry.build_spec(seed)
            
            assert spec.operations["div"].semantic_mode == "error-on-overflow"
            assert spec.operations["mod"].semantic_mode == "error-on-overflow"


class TestShortCircuitModeMapping:
    """Tests for short-circuit mode to operation mapping."""

    def test_short_circuit_true_maps_correctly(self):
        """short_circuit=True should map correctly."""
        registry = SemanticRegistry()
        from src.language.seed import LanguageSeed

        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["arithmetic"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        spec = registry.build_spec(seed)
        
        assert spec.operations["and"].semantic_mode == "short-circuit"
        assert spec.operations["or"].semantic_mode == "short-circuit"
        assert spec.operations["if"].semantic_mode == "short-circuit"

    def test_short_circuit_false_maps_correctly(self):
        """short_circuit=False should map correctly."""
        registry = SemanticRegistry()
        from src.language.seed import LanguageSeed

        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["arithmetic"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=False,
        )
        spec = registry.build_spec(seed)
        
        assert spec.operations["and"].semantic_mode == "eager"
        assert spec.operations["or"].semantic_mode == "eager"
        assert spec.operations["if"].semantic_mode == "eager"

    def test_non_short_circuit_operations_stay_strict(self):
        """Non-short-circuit operations should use strict mode."""
        registry = SemanticRegistry()
        from src.language.seed import LanguageSeed

        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["arithmetic"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        spec = registry.build_spec(seed)
        
        # not, eq, and arithmetic ops should not be short-circuit
        assert spec.operations["not"].semantic_mode == "strict"
        assert spec.operations["eq"].semantic_mode == "strict"
        assert spec.operations["add"].semantic_mode != "short-circuit"


class TestSemanticSpecStructure:
    """Tests for SemanticSpec dataclass structure."""

    def test_semantic_spec_has_required_fields(self):
        """SemanticSpec should have all required fields."""
        registry = SemanticRegistry()
        from src.language.seed import LanguageSeed

        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["arithmetic"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        spec = registry.build_spec(seed)
        
        assert spec.arithmetic_mode == "wraparound"
        assert spec.short_circuit_mode is True
        assert isinstance(spec.operations, dict)

    def test_semantic_spec_is_frozen(self):
        """SemanticSpec should be immutable."""
        registry = SemanticRegistry()
        from src.language.seed import LanguageSeed

        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["arithmetic"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        spec = registry.build_spec(seed)
        
        with pytest.raises(Exception):  # FrozenInstanceError
            spec.arithmetic_mode = "saturating"

    def test_all_builtins_included(self):
        """All built-in operations should be included in spec."""
        registry = SemanticRegistry()
        from src.language.seed import LanguageSeed

        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["arithmetic"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        spec = registry.build_spec(seed)
        
        assert set(spec.operations.keys()) == BUILTIN_OPERATIONS


@given(
    arithmetic=st.sampled_from(list(VALID_ARITHMETIC_MODES)),
    short_circuit=st.booleans(),
)
def test_hypothesis_semantic_spec_consistency(arithmetic, short_circuit):
    """Hypothesis test for semantic spec consistency across many inputs."""
    registry = SemanticRegistry()
    from src.language.seed import LanguageSeed

    seed = LanguageSeed(
        name="Test",
        syntax_style="lisp",
        features=["arithmetic"],
        difficulty=1,
        arithmetic=arithmetic,
        short_circuit=short_circuit,
    )
    
    spec = registry.build_spec(seed)
    
    # Verify structure
    assert spec.arithmetic_mode == arithmetic
    assert spec.short_circuit_mode == short_circuit
    assert set(spec.operations.keys()) == BUILTIN_OPERATIONS
    
    # Verify arithmetic operations use seed's mode
    for op_name in ["add", "sub", "mul"]:
        assert spec.operations[op_name].semantic_mode == arithmetic
    
    # Verify div/mod use error-on-overflow
    assert spec.operations["div"].semantic_mode == "error-on-overflow"
    assert spec.operations["mod"].semantic_mode == "error-on-overflow"
    
    # Verify boolean operations use short_circuit/eager mode
    expected_mode = "short-circuit" if short_circuit else "eager"
    assert spec.operations["and"].semantic_mode == expected_mode
    assert spec.operations["or"].semantic_mode == expected_mode
    assert spec.operations["if"].semantic_mode == expected_mode
    
    # Verify strict operations
    assert spec.operations["not"].semantic_mode == "strict"
    assert spec.operations["eq"].semantic_mode == "strict"
