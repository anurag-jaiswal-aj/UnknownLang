"""Tests for LanguageSeed model and validation."""

import pytest
from hypothesis import given, strategies as st

from src.language.seed import (
    LanguageSeed,
    VALID_SEMANTICS,
    VALID_SYNTAX_STYLES,
    ValidationError,
    validate_seed,
)


class TestLanguageSeedValidation:
    """Tests for seed validation logic."""

    def test_valid_seed_creation(self):
        """Create a valid seed with all required fields."""
        seed = LanguageSeed(
            name="TestLang",
            syntax_style="lisp",
            features=["recursion", "functions"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        assert seed.name == "TestLang"
        assert seed.syntax_style == "lisp"
        # Features are normalized to sorted tuple for determinism
        assert isinstance(seed.features, tuple)
        assert seed.features == ("functions", "recursion")  # Sorted alphabetically
        assert seed.difficulty == 1
        assert seed.arithmetic == "wraparound"
        assert seed.short_circuit is True

    @pytest.mark.parametrize("syntax_style", list(VALID_SYNTAX_STYLES))
    def test_valid_syntax_styles(self, syntax_style):
        """Test that all valid syntax styles are accepted."""
        seed = LanguageSeed(
            name="Test",
            syntax_style=syntax_style,
            features=["feature1"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        assert seed.syntax_style == syntax_style

    @pytest.mark.parametrize("arithmetic", list(VALID_SEMANTICS["arithmetic"]))
    def test_valid_arithmetic_modes(self, arithmetic):
        """Test that all valid arithmetic modes are accepted."""
        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["feature1"],
            difficulty=1,
            arithmetic=arithmetic,
            short_circuit=True,
        )
        assert seed.arithmetic == arithmetic

    @pytest.mark.parametrize("short_circuit", list(VALID_SEMANTICS["short_circuit"]))
    def test_valid_short_circuit_modes(self, short_circuit):
        """Test that both short_circuit modes are accepted."""
        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["feature1"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=short_circuit,
        )
        assert seed.short_circuit == short_circuit

    @pytest.mark.parametrize("difficulty", [1, 2, 3, 4, 5])
    def test_valid_difficulty_range(self, difficulty):
        """Test that difficulty values 1-5 are accepted."""
        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["feature1"],
            difficulty=difficulty,
            arithmetic="wraparound",
            short_circuit=True,
        )
        assert seed.difficulty == difficulty

    def test_invalid_empty_name(self):
        """Test that empty name is rejected."""
        with pytest.raises(ValidationError, match="name must be a non-empty string"):
            LanguageSeed(
                name="",
                syntax_style="lisp",
                features=["feature1"],
                difficulty=1,
                arithmetic="wraparound",
                short_circuit=True,
            )

    def test_invalid_whitespace_name(self):
        """Test that whitespace-only name is rejected."""
        with pytest.raises(ValidationError, match="name cannot be whitespace-only"):
            LanguageSeed(
                name="   ",
                syntax_style="lisp",
                features=["feature1"],
                difficulty=1,
                arithmetic="wraparound",
                short_circuit=True,
            )

    def test_invalid_syntax_style(self):
        """Test that invalid syntax style is rejected."""
        with pytest.raises(ValidationError, match="Invalid syntax_style"):
            LanguageSeed(
                name="Test",
                syntax_style="invalid-style",
                features=["feature1"],
                difficulty=1,
                arithmetic="wraparound",
                short_circuit=True,
            )

    def test_invalid_arithmetic_mode(self):
        """Test that invalid arithmetic mode is rejected."""
        with pytest.raises(ValidationError, match="Invalid arithmetic"):
            LanguageSeed(
                name="Test",
                syntax_style="lisp",
                features=["feature1"],
                difficulty=1,
                arithmetic="invalid-mode",
                short_circuit=True,
            )

    def test_invalid_short_circuit_value(self):
        """Test that invalid short_circuit value is rejected."""
        with pytest.raises(ValidationError, match="Invalid short_circuit"):
            LanguageSeed(
                name="Test",
                syntax_style="lisp",
                features=["feature1"],
                difficulty=1,
                arithmetic="wraparound",
                short_circuit="invalid",
            )

    def test_invalid_difficulty_too_low(self):
        """Test that difficulty below 1 is rejected."""
        with pytest.raises(ValidationError, match="difficulty must be between"):
            LanguageSeed(
                name="Test",
                syntax_style="lisp",
                features=["feature1"],
                difficulty=0,
                arithmetic="wraparound",
                short_circuit=True,
            )

    def test_invalid_difficulty_too_high(self):
        """Test that difficulty above 5 is rejected."""
        with pytest.raises(ValidationError, match="difficulty must be between"):
            LanguageSeed(
                name="Test",
                syntax_style="lisp",
                features=["feature1"],
                difficulty=6,
                arithmetic="wraparound",
                short_circuit=True,
            )

    def test_invalid_difficulty_not_integer(self):
        """Test that non-integer difficulty is rejected."""
        with pytest.raises(ValidationError, match="difficulty must be an integer"):
            LanguageSeed(
                name="Test",
                syntax_style="lisp",
                features=["feature1"],
                difficulty=1.5,
                arithmetic="wraparound",
                short_circuit=True,
            )

    def test_invalid_empty_features(self):
        """Test that empty features list is rejected."""
        with pytest.raises(ValidationError, match="features must contain at least one feature"):
            LanguageSeed(
                name="Test",
                syntax_style="lisp",
                features=[],
                difficulty=1,
                arithmetic="wraparound",
                short_circuit=True,
            )

    def test_invalid_non_string_feature(self):
        """Test that non-string features are rejected."""
        with pytest.raises(ValidationError, match="Each feature must be a non-empty string"):
            LanguageSeed(
                name="Test",
                syntax_style="lisp",
                features=["valid", 123],
                difficulty=1,
                arithmetic="wraparound",
                short_circuit=True,
            )


class TestLanguageSeedFromDict:
    """Tests for LanguageSeed.from_dict() class method."""

    def test_from_dict_valid_seed(self):
        """Create seed from valid dictionary."""
        data = {
            "name": "TestLang",
            "syntax_style": "lisp",
            "features": ["recursion", "functions"],
            "difficulty": 1,
            "arithmetic": "wraparound",
            "short_circuit": True,
        }
        seed = LanguageSeed.from_dict(data)
        assert seed.name == "TestLang"
        assert seed.syntax_style == "lisp"
        # from_dict sorts features alphabetically
        assert seed.features == ("functions", "recursion")

    def test_direct_construction_and_from_dict_equivalent(self):
        """Direct construction and from_dict produce identical features (both sorted)."""
        data = {
            "name": "TestLang",
            "syntax_style": "lisp",
            "features": ["functions", "recursion"],
            "difficulty": 1,
            "arithmetic": "wraparound",
            "short_circuit": True,
        }
        seed1 = LanguageSeed.from_dict(data)
        seed2 = LanguageSeed(
            name="TestLang",
            syntax_style="lisp",
            features=["recursion", "functions"],  # Different order - should still be sorted
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        assert seed1.features == seed2.features

    def test_from_dict_missing_field(self):
        """Test that missing fields raise ValidationError."""
        data = {
            "name": "Test",
            "syntax_style": "lisp",
            # Missing required fields
        }
        with pytest.raises(ValidationError, match="Missing required fields"):
            LanguageSeed.from_dict(data)

    def test_mutable_input_list_not_affected_by_mutation(self):
        """Mutating the original input list after construction does not change the seed."""
        original_list = ["feature1", "feature2"]
        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=original_list,
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        # Mutate the original list
        original_list[0] = "mutated"
        # Seed's features should remain unchanged
        assert seed.features == ("feature1", "feature2")

    def test_from_dict_sorts_features(self):
        """Test that features are sorted and converted to tuple."""
        data = {
            "name": "Test",
            "syntax_style": "lisp",
            "features": ["z-feature", "a-feature", "m-feature"],
            "difficulty": 1,
            "arithmetic": "wraparound",
            "short_circuit": True,
        }
        seed = LanguageSeed.from_dict(data)
        # Features should be sorted alphabetically
        assert seed.features == ("a-feature", "m-feature", "z-feature")


class TestValidateSeedFunction:
    """Tests for validate_seed() standalone function."""

    def test_validate_seed_valid(self):
        """Valid seed should not raise."""
        data = {
            "name": "TestLang",
            "syntax_style": "lisp",
            "features": ["recursion"],
            "difficulty": 1,
            "arithmetic": "wraparound",
            "short_circuit": True,
        }
        # Should not raise
        validate_seed(data)

    def test_validate_seed_invalid_name(self):
        """Invalid name should raise ValidationError."""
        data = {
            "name": "",
            "syntax_style": "lisp",
            "features": ["recursion"],
            "difficulty": 1,
            "arithmetic": "wraparound",
            "short_circuit": True,
        }
        with pytest.raises(ValidationError, match="name must be a non-empty string"):
            validate_seed(data)

    def test_validate_seed_missing_fields(self):
        """Missing fields should raise ValidationError."""
        data = {
            "name": "Test",
            # Missing other fields
        }
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_seed(data)


class TestLanguageSeedToDict:
    """Tests for LanguageSeed.to_dict() method."""

    def test_to_dict_sorted_features(self):
        """Test that to_dict returns sorted features."""
        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["z-feature", "a-feature"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        result = seed.to_dict()
        assert result["features"] == ["a-feature", "z-feature"]

    def test_to_dict_contains_all_fields(self):
        """Test that to_dict contains all required fields."""
        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["feature1"],
            difficulty=3,
            arithmetic="saturating",
            short_circuit=False,
        )
        result = seed.to_dict()
        assert set(result.keys()) == {
            "name", "syntax_style", "features", "difficulty",
            "arithmetic", "short_circuit"
        }


class TestLanguageSeedToCanonicalBytes:
    """Tests for LanguageSeed.to_canonical_bytes() method."""

    def test_canonical_bytes_deterministic(self):
        """Same seed should produce identical canonical bytes."""
        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["feature1", "feature2"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        bytes1 = seed.to_canonical_bytes()
        bytes2 = seed.to_canonical_bytes()
        assert bytes1 == bytes2

    def test_canonical_bytes_version_change(self):
        """Different spec_version should produce different bytes."""
        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["feature1"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        bytes_v1 = seed.to_canonical_bytes(spec_version="1.0.0")
        bytes_v2 = seed.to_canonical_bytes(spec_version="2.0.0")
        assert bytes_v1 != bytes_v2

    def test_canonical_bytes_algorithm_change(self):
        """Different algorithm_version should produce different bytes."""
        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["feature1"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        bytes_v1 = seed.to_canonical_bytes(algorithm_version="1.0.0")
        bytes_v2 = seed.to_canonical_bytes(algorithm_version="2.0.0")
        assert bytes_v1 != bytes_v2

    def test_canonical_bytes_no_timestamps(self):
        """Canonical bytes should not contain timestamps."""
        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["feature1"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        canonical = seed.to_canonical_bytes()
        assert b"timestamp" not in canonical
        assert b"generated_at" not in canonical


@given(
    name=st.text(min_size=1, max_size=50).filter(lambda x: x.strip() == x),
    syntax_style=st.sampled_from(list(VALID_SYNTAX_STYLES)),
    features=st.lists(
        st.text(min_size=1, max_size=20).filter(lambda x: x.strip() == x),
        min_size=1,
        max_size=10,
        unique=True,
    ),
    difficulty=st.integers(min_value=1, max_value=5),
    arithmetic=st.sampled_from(list(VALID_SEMANTICS["arithmetic"])),
    short_circuit=st.booleans(),
)
def test_hypothesis_valid_seed_creation(name, syntax_style, features, difficulty, arithmetic, short_circuit):
    """Hypothesis test for valid seed creation across many input combinations."""
    # This test verifies that valid seeds can be created with random but valid inputs
    seed = LanguageSeed(
        name=name,
        syntax_style=syntax_style,
        features=features,
        difficulty=difficulty,
        arithmetic=arithmetic,
        short_circuit=short_circuit,
    )
    # Verify all fields are set correctly
    assert seed.name == name
    assert seed.syntax_style == syntax_style
    assert seed.difficulty == difficulty
    assert seed.arithmetic == arithmetic
    assert seed.short_circuit == short_circuit
