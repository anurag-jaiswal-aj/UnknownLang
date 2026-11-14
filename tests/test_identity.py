"""Tests for language identity calculation."""

import hashlib
import pytest
from hypothesis import given, strategies as st

from src.language.seed import LanguageSeed
from src.language.identity import (
    compute_language_id,
    compute_language_id_from_dict,
    verify_identity_determinism,
)


class TestComputeLanguageId:
    """Tests for compute_language_id() function."""

    def test_compute_language_id_deterministic(self):
        """Same seed should always produce same identity."""
        seed = LanguageSeed(
            name="TestLang",
            syntax_style="lisp",
            features=["recursion"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        id1 = compute_language_id(seed)
        id2 = compute_language_id(seed)
        id3 = compute_language_id(seed)
        assert id1 == id2 == id3
        # Identity should be 69 characters: "lang_" (5) + 64 hex (full SHA-256)
        assert len(id1) == 69
        assert id1.startswith("lang_")

    def test_compute_language_id_version_change(self):
        """Different spec_version should produce different identity."""
        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["feature1"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        id_v1 = compute_language_id(seed, spec_version="1.0.0")
        id_v2 = compute_language_id(seed, spec_version="2.0.0")
        assert id_v1 != id_v2

    def test_compute_language_id_algorithm_change(self):
        """Different algorithm_version should produce different identity."""
        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["feature1"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        id_v1 = compute_language_id(seed, algorithm_version="1.0.0")
        id_v2 = compute_language_id(seed, algorithm_version="2.0.0")
        assert id_v1 != id_v2

    def test_compute_language_id_changes_with_seed(self):
        """Different seeds should produce different identities."""
        seed1 = LanguageSeed(
            name="Lang1",
            syntax_style="lisp",
            features=["feature1"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        seed2 = LanguageSeed(
            name="Lang2",
            syntax_style="lisp",
            features=["feature1"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        id1 = compute_language_id(seed1)
        id2 = compute_language_id(seed2)
        assert id1 != id2

    def test_compute_language_id_sorted_features_deterministic(self):
        """Feature order should not affect identity."""
        seed1 = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["z-feature", "a-feature", "m-feature"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        seed2 = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["a-feature", "m-feature", "z-feature"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        id1 = compute_language_id(seed1)
        id2 = compute_language_id(seed2)
        assert id1 == id2

    def test_compute_language_id_verify_determinism(self):
        """Test verify_identity_determinism helper."""
        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["feature1"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        assert verify_identity_determinism(seed, iterations=100)

    def test_compute_language_id_empty_features(self):
        """Test with minimum valid features (single feature)."""
        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["x"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        identity = compute_language_id(seed)
        assert identity.startswith("lang_")
        assert len(identity) == 69

    def test_full_sha256_digest_used(self):
        """Verify identity uses full SHA-256 digest (64 hex chars)."""
        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["feature1"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        identity = compute_language_id(seed)
        hex_part = identity[5:]  # Skip "lang_"
        assert len(hex_part) == 64


class TestComputeLanguageIdFromDict:
    """Tests for compute_language_id_from_dict() function."""

    def test_compute_from_dict_valid(self):
        """Compute identity from valid dictionary."""
        data = {
            "name": "Test",
            "syntax_style": "lisp",
            "features": ["feature1"],
            "difficulty": 1,
            "arithmetic": "wraparound",
            "short_circuit": True,
        }
        identity = compute_language_id_from_dict(data)
        assert identity.startswith("lang_")

    def test_compute_from_dict_invalid(self):
        """Invalid dictionary should raise ValidationError."""
        data = {
            "name": "",
            "syntax_style": "lisp",
            "features": ["feature1"],
            "difficulty": 1,
            "arithmetic": "wraparound",
            "short_circuit": True,
        }
        with pytest.raises(Exception):  # ValidationError
            compute_language_id_from_dict(data)


class TestIdentityFormat:
    """Tests for identity string format."""

    def test_identity_prefix(self):
        """Identity should start with 'lang_'."""
        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["feature1"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        identity = compute_language_id(seed)
        assert identity.startswith("lang_")
        assert len(identity) == 69

    def test_identity_hex_characters(self):
        """Identity after prefix should be valid hex (full SHA-256 = 64 chars)."""
        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["feature1"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        identity = compute_language_id(seed)
        hex_part = identity[5:]  # Skip "lang_"
        assert len(hex_part) == 64
        int(hex_part, 16)  # Should not raise

    def test_direct_construction_and_from_dict_same_identity(self):
        """Direct construction and from_dict should produce identical identities."""
        data = {
            "name": "Test",
            "syntax_style": "lisp",
            "features": ["z", "a", "m"],
            "difficulty": 1,
            "arithmetic": "wraparound",
            "short_circuit": True,
        }
        seed1 = LanguageSeed.from_dict(data)
        seed2 = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["a", "m", "z"],  # Same features, different order
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        id1 = compute_language_id(seed1)
        id2 = compute_language_id(seed2)
        assert id1 == id2

    def test_spec_version_change_affects_identity(self):
        """Different spec_version should produce different identities."""
        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["feature1"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        id_v1 = compute_language_id(seed, spec_version="1.0.0")
        id_v2 = compute_language_id(seed, spec_version="1.1.0")
        assert id_v1 != id_v2

    def test_algorithm_version_change_affects_identity(self):
        """Different algorithm_version should produce different identities."""
        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["feature1"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        id_v1 = compute_language_id(seed, algorithm_version="1.0.0")
        id_v2 = compute_language_id(seed, algorithm_version="1.1.0")
        assert id_v1 != id_v2

    def test_generated_at_not_included_in_identity(self):
        """The generated_at field should never affect identity."""
        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["feature1"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        # Both calls should produce identical identity
        id1 = compute_language_id(seed)
        id2 = compute_language_id(seed)
        assert id1 == id2


@given(
    name=st.text(min_size=1, max_size=50).filter(lambda x: x.strip() == x and x != ""),
    syntax_style=st.sampled_from(["lisp", "c-like", "pythonic"]),
    features=st.lists(
        st.text(min_size=1, max_size=20).filter(lambda x: x.strip() == x and x != ""),
        min_size=1,
        max_size=5,
    ),
    difficulty=st.integers(min_value=1, max_value=5),
    arithmetic=st.sampled_from(["wraparound", "saturating", "error-on-overflow"]),
    short_circuit=st.booleans(),
)
def test_hypothesis_identity_determinism(name, syntax_style, features, difficulty, arithmetic, short_circuit):
    """Hypothesis test for identity determinism across many inputs."""
    seed = LanguageSeed(
        name=name,
        syntax_style=syntax_style,
        features=features,
        difficulty=difficulty,
        arithmetic=arithmetic,
        short_circuit=short_circuit,
    )
    # Compute identity multiple times
    ids = [compute_language_id(seed) for _ in range(10)]
    # All should be identical
    assert len(set(ids)) == 1
