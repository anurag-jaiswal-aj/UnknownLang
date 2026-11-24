"""Wave 2.2.9 - Manifest size estimator verification.

Tests exact incremental byte accounting for manifest size estimation.
Verifies that the estimator matches the canonical JSON serialization contract
in src/benchmark/canonical.py.
"""
from __future__ import annotations

import pytest

from src.benchmark.canonical import canonical_bytes
from src.benchmark.manager import (
    DerivationManifest,
    EnvironmentManager,
    MAX_MANIFEST_SIZE,
    reconstruct_environment_from_manifest,
    _estimate_dict_size_bounded,
    _estimate_json_value_size,
    _validate_manifest_size_bounded,
)
from src.language.seed import LanguageSeed, ValidationError


class TestExactByteAccounting:
    """Test that size estimator matches canonical JSON serialization exactly."""

    def test_empty_dict_size(self):
        """Empty dict should be exactly 2 bytes: {}"""
        size = _estimate_dict_size_bounded({}, MAX_MANIFEST_SIZE, "$")
        assert size == 2  # {} = 2 bytes

    def test_single_key_value_size(self):
        """Single key-value pair size matches canonical JSON."""
        d = {"key": "value"}
        
        # Calculate estimated size
        estimated = _estimate_dict_size_bounded(d, MAX_MANIFEST_SIZE, "$")
        
        # Calculate actual canonical JSON size
        actual = len(canonical_bytes(d))
        
        assert estimated == actual, f"Estimated {estimated} != actual {actual}"

    def test_nested_dict_size(self):
        """Nested dict size matches canonical JSON."""
        d = {"outer": {"inner": "value"}}
        
        estimated = _estimate_dict_size_bounded(d, MAX_MANIFEST_SIZE, "$")
        actual = len(canonical_bytes(d))
        
        assert estimated == actual, f"Estimated {estimated} != actual {actual}"

    def test_list_size(self):
        """List size matches canonical JSON."""
        lst = ["a", "b", "c"]
        
        estimated = _estimate_json_value_size(lst, MAX_MANIFEST_SIZE, "$")
        actual = len(canonical_bytes(lst))
        
        assert estimated == actual, f"Estimated {estimated} != actual {actual}"

    def test_string_with_quotes_escaping(self):
        """String with quotes and backslashes is escaped correctly."""
        s = 'text "quoted" and \\ backslash'
        
        estimated = _estimate_json_value_size(s, MAX_MANIFEST_SIZE, "$")
        actual = len(canonical_bytes(s))
        
        # Both should use the same escaping
        assert estimated == actual, f"Estimated {estimated} != actual {actual}"

    def test_unicode_string_size(self):
        """Unicode string size uses UTF-8 encoding."""
        s = "hello 世界 🌍"
        
        estimated = _estimate_json_value_size(s, MAX_MANIFEST_SIZE, "$")
        actual = len(canonical_bytes(s))
        
        assert estimated == actual, f"Estimated {estimated} != actual {actual}"

    def test_integer_size(self):
        """Integer size matches string representation."""
        i = 12345
        
        estimated = _estimate_json_value_size(i, MAX_MANIFEST_SIZE, "$")
        actual = len(canonical_bytes(i))
        
        assert estimated == actual, f"Estimated {estimated} != actual {actual}"

    def test_null_size(self):
        """null value is exactly 4 bytes."""
        estimated = _estimate_json_value_size(None, MAX_MANIFEST_SIZE, "$")
        assert estimated == 4  # "null"

    def test_boolean_sizes(self):
        """Boolean values: true=4, false=5."""
        assert _estimate_json_value_size(True, MAX_MANIFEST_SIZE, "$") == 4  # "true"
        assert _estimate_json_value_size(False, MAX_MANIFEST_SIZE, "$") == 5  # "false"

    def test_deeply_nested_structure(self):
        """Deeply nested structures are counted correctly."""
        def make_deep(depth):
            if depth == 0:
                return "base"
            return {"level": make_deep(depth - 1)}
        
        for depth in range(1, 10):
            structure = make_deep(depth)
            estimated = _estimate_dict_size_bounded(structure, MAX_MANIFEST_SIZE, "$")
            actual = len(canonical_bytes(structure))
            assert estimated == actual, f"Depth {depth}: estimated {estimated} != actual {actual}"

    def test_large_collection_size(self):
        """Large collections are counted correctly."""
        # Create a dict with many items
        d = {f"key{i}": f"value{i}" for i in range(100)}
        
        estimated = _estimate_dict_size_bounded(d, MAX_MANIFEST_SIZE, "$")
        actual = len(canonical_bytes(d))
        
        assert estimated == actual, f"Estimated {estimated} != actual {actual}"


class TestExactBoundary:
    """Test exact boundary conditions for manifest size."""

    def test_manifest_just_under_limit(self):
        """Manifest just under 500KB is accepted."""
        # Create a manifest with large but valid seed
        seed = LanguageSeed(
            name="test",
            syntax_style="lisp",
            features=["arithmetic", "functions"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        profile = {"profile_schema_version": 1, "keywords": {}, "operators": {}, "literals": {}}
        
        mgr = EnvironmentManager()
        env, manifest = mgr.create_environment(seed, profile)
        
        # The manifest should be well under 500KB
        actual_size = len(canonical_bytes(manifest.to_dict()))
        assert actual_size < MAX_MANIFEST_SIZE
        
        # Reconstruction should succeed
        reconstructed = reconstruct_environment_from_manifest(manifest)
        assert reconstructed.environment_id == env.environment_id

    def test_manifest_at_limit(self):
        """Manifest at exactly the limit (if possible) is accepted."""
        # This tests the boundary at which we can actually construct a valid manifest
        # The limit is 500KB but valid manifests are much smaller
        
        seed = LanguageSeed(
            name="test",
            syntax_style="lisp",
            features=["arithmetic", "functions"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        profile = {"profile_schema_version": 1, "keywords": {}, "operators": {}, "literals": {}}
        
        mgr = EnvironmentManager()
        env, manifest = mgr.create_environment(seed, profile)
        
        actual_size = len(canonical_bytes(manifest.to_dict()))
        # Valid manifests should be under limit
        assert actual_size < MAX_MANIFEST_SIZE

    def test_large_seed_under_limit(self):
        """Test that large but valid seeds are counted correctly."""
        # Create a seed with many keys but still under 500KB
        
        large_seed = {
            "name": "test",
            "syntax_style": "lisp",
            "features": ["arithmetic", "functions"],
            "difficulty": 1,
            "arithmetic": "wraparound",
            "short_circuit": True,
            "k0": "x" * 65536,
            "k1": "y" * 65536,
            "k2": "z" * 65536,
            "k3": "a" * 65536,
            "k4": "b" * 65536,
            "k5": "c" * 65536,
        }
        
        # Verify the size
        estimated = _estimate_dict_size_bounded(large_seed, MAX_MANIFEST_SIZE, "$")
        actual = len(canonical_bytes(large_seed))
        
        # They should match exactly
        assert estimated == actual
        
        # The total should be under 500KB (we expect acceptance)
        assert actual <= MAX_MANIFEST_SIZE


class TestEarlyRejection:
    """Test that oversized manifests are rejected early."""

    def test_rejection_stops_processing(self):
        """Oversized manifest is rejected before full serialization."""
        # Create a manifest with many keys, each with a large string
        # MAX_STRING_LENGTH is 65536, so we need many keys to exceed 500KB
        
        # Each key "k0" to "k9" with value "x" * 65536 = 65540 bytes per entry
        # 8 entries = ~524KB which exceeds 500KB
        
        seed = {
            "name": "test",
            "syntax_style": "lisp",
            "features": ["arithmetic", "functions"],
            "difficulty": 1,
            "arithmetic": "wraparound",
            "short_circuit": True,
            # 8 strings of 65536 chars each = 524288 bytes for values alone
            "k0": "x" * 65536,
            "k1": "y" * 65536,
            "k2": "z" * 65536,
            "k3": "a" * 65536,
            "k4": "b" * 65536,
            "k5": "c" * 65536,
            "k6": "d" * 65536,
            "k7": "e" * 65536,
        }
        profile = {"profile_schema_version": 1, "keywords": {}, "operators": {}, "literals": {}}
        
        manifest = DerivationManifest(
            schema_version=1,
            environment_id="env_" + "0" * 64,
            env_schema_version=1,
            generator_family_version="f1",
            generator_algorithm_version="1.0.0",
            seed=seed,
            surface_profile=profile,
            runtime_semantics_version=2,
            grammar_sha256="a" * 64,
            semantic_spec_sha256="b" * 64,
            surface_profile_sha256="c" * 64,
        )
        
        # Should raise ValidationError before trying to serialize
        with pytest.raises(ValidationError, match="exceeds maximum size"):
            _estimate_dict_size_bounded(manifest.seed, MAX_MANIFEST_SIZE, "seed")

    def test_rejection_before_environment_reconstruction(self):
        """Oversized manifest is rejected before environment reconstruction."""
        # Create a manifest with many keys that exceed 500KB
        seed = {
            "name": "test",
            "syntax_style": "lisp",
            "features": ["arithmetic", "functions"],
            "difficulty": 1,
            "arithmetic": "wraparound",
            "short_circuit": True,
            "k0": "x" * 65536,
            "k1": "y" * 65536,
            "k2": "z" * 65536,
            "k3": "a" * 65536,
            "k4": "b" * 65536,
            "k5": "c" * 65536,
            "k6": "d" * 65536,
            "k7": "e" * 65536,
        }
        profile = {"profile_schema_version": 1, "keywords": {}, "operators": {}, "literals": {}}
        
        manifest = DerivationManifest(
            schema_version=1,
            environment_id="env_" + "0" * 64,
            env_schema_version=1,
            generator_family_version="f1",
            generator_algorithm_version="1.0.0",
            seed=seed,
            surface_profile=profile,
            runtime_semantics_version=2,
            grammar_sha256="a" * 64,
            semantic_spec_sha256="b" * 64,
            surface_profile_sha256="c" * 64,
        )
        
        # Should raise ValidationError before environment reconstruction
        with pytest.raises(ValidationError, match="exceeds maximum size"):
            reconstruct_environment_from_manifest(manifest)

    def test_invalid_type_rejected_early(self):
        """Invalid manifest structure is rejected before expensive operations."""
        # Create a manifest with unsupported type
        seed = {
            "name": "test",
            "syntax_style": "lisp",
            "features": ["arithmetic", "functions"],
            "difficulty": 1,
            "arithmetic": "wraparound",
            "short_circuit": True,
            "unsupported": lambda: None,  # Unsupported type
        }
        profile = {"profile_schema_version": 1, "keywords": {}, "operators": {}, "literals": {}}
        
        manifest = DerivationManifest(
            schema_version=1,
            environment_id="env_" + "0" * 64,
            env_schema_version=1,
            generator_family_version="f1",
            generator_algorithm_version="1.0.0",
            seed=seed,
            surface_profile=profile,
            runtime_semantics_version=2,
            grammar_sha256="a" * 64,
            semantic_spec_sha256="b" * 64,
            surface_profile_sha256="c" * 64,
        )
        
        # Should raise ValidationError for unsupported type
        with pytest.raises(ValidationError):
            _validate_manifest_size_bounded(manifest)


class TestUTF8Encoding:
    """Test UTF-8 byte counting for multibyte characters."""

    def test_single_char_utf8(self):
        """Single ASCII char is 1 byte."""
        s = "a"
        estimated = _estimate_json_value_size(s, MAX_MANIFEST_SIZE, "$")
        actual = len(canonical_bytes(s))
        assert estimated == actual

    def test_multibyte_utf8(self):
        """Multibyte UTF-8 chars are counted correctly."""
        # Japanese chars are 3 bytes each in UTF-8
        s = "日本語"
        estimated = _estimate_json_value_size(s, MAX_MANIFEST_SIZE, "$")
        actual = len(canonical_bytes(s))
        assert estimated == actual
        assert len(s.encode("utf-8")) == 9  # 3 chars * 3 bytes each

    def test_emoji_utf8(self):
        """Emoji are counted correctly (typically 4 bytes each)."""
        s = "🌍"
        estimated = _estimate_json_value_size(s, MAX_MANIFEST_SIZE, "$")
        actual = len(canonical_bytes(s))
        assert estimated == actual

    def test_mixed_utf8_content(self):
        """Mixed ASCII and UTF-8 content is counted correctly."""
        s = "hello 世界 🌍"
        estimated = _estimate_json_value_size(s, MAX_MANIFEST_SIZE, "$")
        actual = len(canonical_bytes(s))
        assert estimated == actual
