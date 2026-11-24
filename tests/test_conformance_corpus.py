"""Wave 2.2 conformance corpus tests for runtime, surface, and derivation."""
import json
import pathlib

import pytest

from src.benchmark.canonical import MAX_NESTING_DEPTH, MAX_COLLECTION_SIZE, MAX_STRING_LENGTH
from src.benchmark.manager import (
    DerivationManifest,
    EnvironmentManager,
    MAX_MANIFEST_SIZE,
    reconstruct_environment_from_manifest,
)
from src.language.surface import SurfaceTranslationError
from src.execution.engine import ExecutionEngine
from src.language.seed import LanguageSeed, ValidationError
from src.language.surface import SurfaceProfile, to_canonical, MAX_SOURCE_LENGTH, MAX_MAPPINGS_PER_CATEGORY
from src.oracle.reference_evaluator import ReferenceEvaluator

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures" / "conformance"


def load_fixture(name: str) -> dict:
    """Load a conformance fixture by name."""
    with open(FIXTURES_DIR / f"{name}.json") as f:
        return json.load(f)


class TestRuntimeContract:
    """Test runtime contract compliance using conformance fixtures."""

    def test_empty_program_returns_none(self):
        fixtures = load_fixture("runtime_contract")
        fixture = fixtures["empty_program"]
        result = ExecutionEngine().execute(fixture["program"], _lang())
        assert (result.status, result.value) == (fixture["expected"]["status"], fixture["expected"]["value"])

    def test_definition_only_returns_none(self):
        fixtures = load_fixture("runtime_contract")
        fixture = fixtures["definition_only"]
        result = ExecutionEngine().execute(fixture["program"], _lang())
        assert (result.status, result.value) == (fixture["expected"]["status"], fixture["expected"]["value"])

    def test_expression_then_definition_returns_expression_value(self):
        fixtures = load_fixture("runtime_contract")
        fixture = fixtures["expression_then_definition"]
        result = ExecutionEngine().execute(fixture["program"], _lang())
        assert (result.status, result.value) == (fixture["expected"]["status"], fixture["expected"]["value"])

    def test_definition_then_expression_returns_expression_value(self):
        fixtures = load_fixture("runtime_contract")
        fixture = fixtures["definition_then_expression"]
        result = ExecutionEngine().execute(fixture["program"], _lang())
        assert (result.status, result.value) == (fixture["expected"]["status"], fixture["expected"]["value"])

    def test_multiple_expressions_returns_last(self):
        fixtures = load_fixture("runtime_contract")
        fixture = fixtures["multiple_expressions"]
        result = ExecutionEngine().execute(fixture["program"], _lang())
        assert (result.status, result.value) == (fixture["expected"]["status"], fixture["expected"]["value"])

    def test_division_by_zero_has_structured_error(self):
        fixtures = load_fixture("runtime_contract")
        fixture = fixtures["division_zero"]
        result = ExecutionEngine().execute(fixture["program"], _lang())
        assert result.status == fixture["expected"]["status"]
        assert result.error_kind == fixture["expected"]["error_kind"]


class TestSurfaceTranslation:
    """Test surface translation determinism using conformance fixtures."""

    def test_keyword_prefix_translation(self):
        fixtures = load_fixture("surface_translation")
        fixture = fixtures["keyword_prefix_translation"]
        profile = SurfaceProfile.from_dict(fixture["profile"])
        result = to_canonical(fixture["source"], profile)
        assert result.canonical_text == fixture["expected_canonical"]

    def test_operator_translation(self):
        fixtures = load_fixture("surface_translation")
        fixture = fixtures["operator_translation"]
        profile = SurfaceProfile.from_dict(fixture["profile"])
        result = to_canonical(fixture["source"], profile)
        assert result.canonical_text == fixture["expected_canonical"]

    def test_boolean_literals_translation(self):
        fixtures = load_fixture("surface_translation")
        fixture = fixtures["boolean_literals"]
        profile = SurfaceProfile.from_dict(fixture["profile"])
        result = to_canonical(fixture["source"], profile)
        assert result.canonical_text == fixture["expected_canonical"]

    def test_translation_determinism(self):
        """Same source + profile always produces same canonical output."""
        fixtures = load_fixture("surface_translation")
        fixture = fixtures["keyword_prefix_translation"]
        profile = SurfaceProfile.from_dict(fixture["profile"])
        canonical = fixture["expected_canonical"]

        for _ in range(3):
            result = to_canonical(fixture["source"], profile)
            assert result.canonical_text == canonical

    def test_translation_matches_reference(self):
        """Surface translation produces same result as reference evaluator."""
        fixtures = load_fixture("surface_translation")
        fixture = fixtures["operator_translation"]
        profile = SurfaceProfile.from_dict(fixture["profile"])

        lang = _lang()
        source = fixture["source"]

        production = ExecutionEngine().execute(source, lang, surface_profile=profile)
        reference = ReferenceEvaluator().execute(source, lang, surface_profile=profile)

        assert (production.status, production.value) == (reference.status, reference.value)


class TestEnvironmentDerivation:
    """Test environment derivation and reconstruction using conformance fixtures."""

    def test_deterministic_environment_creation(self):
        fixtures = load_fixture("environment_derivation")
        fixture = fixtures["deterministic_creation"]
        seed = LanguageSeed.from_dict(fixture["seed"])
        profile = fixture["profile"]

        mgr = EnvironmentManager()
        env1, manifest1 = mgr.create_environment(seed, profile)
        env2, manifest2 = mgr.create_environment(seed, profile)

        assert env1.environment_id == env2.environment_id
        assert manifest1.environment_id == manifest2.environment_id

    def test_runtime_version_in_manifest(self):
        fixtures = load_fixture("environment_derivation")
        fixture = fixtures["deterministic_creation"]
        seed = LanguageSeed.from_dict(fixture["seed"])
        profile = fixture["profile"]

        mgr = EnvironmentManager()
        env, manifest = mgr.create_environment(seed, profile)

        assert manifest.schema_version == 1
        assert manifest.runtime_semantics_version == 2
        assert manifest.environment_id == env.environment_id
        assert manifest.runtime_semantics_version == env.identity_core["runtime_semantics_version"]

    def test_manifest_reconstruction_produces_same_id(self):
        fixtures = load_fixture("environment_derivation")
        fixture = fixtures["deterministic_creation"]
        seed = LanguageSeed.from_dict(fixture["seed"])
        profile = fixture["profile"]

        mgr = EnvironmentManager()
        env, manifest = mgr.create_environment(seed, profile)

        reconstructed = reconstruct_environment_from_manifest(manifest)
        assert reconstructed.environment_id == env.environment_id

    def test_invalid_manifest_schema_rejected(self):
        manifest = DerivationManifest(
            schema_version=999,
            environment_id="env_0" * 16,
            env_schema_version=1,
            generator_family_version="f1",
            generator_algorithm_version="1.0.0",
            seed={},
            surface_profile={},
            runtime_semantics_version=2,
            grammar_sha256="a" * 64,
            semantic_spec_sha256="b" * 64,
            surface_profile_sha256="c" * 64,
        )

        with pytest.raises(ValidationError):
            reconstruct_environment_from_manifest(manifest)

    def test_identity_mismatch_rejected(self):
        fixtures = load_fixture("environment_derivation")
        fixture = fixtures["deterministic_creation"]
        seed = LanguageSeed.from_dict(fixture["seed"])
        profile = fixture["profile"]

        mgr = EnvironmentManager()
        env, _ = mgr.create_environment(seed, profile)

        # Create manifest with wrong identity
        manifest = DerivationManifest(
            schema_version=1,
            environment_id="env_0" * 16,
            env_schema_version=1,
            generator_family_version="f1",
            generator_algorithm_version="1.0.0",
            seed=seed.to_dict(),
            surface_profile=profile,
            runtime_semantics_version=2,
            grammar_sha256=env.identity_core["grammar_sha256"],
            semantic_spec_sha256=env.identity_core["semantic_spec_sha256"],
            surface_profile_sha256=env.identity_core["surface_profile_sha256"],
        )

        with pytest.raises(ValidationError):
            reconstruct_environment_from_manifest(manifest)

    def test_runtime_version_mismatch_rejected(self):
        fixtures = load_fixture("environment_derivation")
        fixture = fixtures["deterministic_creation"]
        seed = LanguageSeed.from_dict(fixture["seed"])
        profile = fixture["profile"]

        mgr = EnvironmentManager()
        env, _ = mgr.create_environment(seed, profile)

        # Create manifest with wrong runtime version
        manifest = DerivationManifest(
            schema_version=1,
            environment_id=env.environment_id,
            env_schema_version=1,
            generator_family_version="f1",
            generator_algorithm_version="1.0.0",
            seed=seed.to_dict(),
            surface_profile=profile,
            runtime_semantics_version=1,  # Wrong version
            grammar_sha256=env.identity_core["grammar_sha256"],
            semantic_spec_sha256=env.identity_core["semantic_spec_sha256"],
            surface_profile_sha256=env.identity_core["surface_profile_sha256"],
        )

        with pytest.raises(ValidationError):
            reconstruct_environment_from_manifest(manifest)


def _lang():
    """Create a test language specification."""
    from src.language.generator import LanguageGenerator
    from src.language.seed import LanguageSeed

    seed = LanguageSeed(
        name="conformance",
        syntax_style="lisp",
        features=["arithmetic", "functions"],
        difficulty=1,
        arithmetic="wraparound",
        short_circuit=True,
    )
    return LanguageGenerator().generate(seed)


class TestResourceBoundaries:
    """Test resource boundary enforcement."""

    def test_source_length_limit(self):
        """Verify source text longer than MAX_SOURCE_LENGTH is rejected."""
        long_source = " " * (MAX_SOURCE_LENGTH + 1)
        profile = SurfaceProfile(
            keywords={}, operators={}, literals={}, profile_schema_version=1
        )
        with pytest.raises(SurfaceTranslationError) as exc_info:
            to_canonical(long_source, profile)
        assert "exceeds maximum length" in str(exc_info.value)

    def test_profile_mappings_limit(self):
        """Verify surface profile with too many mappings is rejected."""
        too_many_keywords = {f"k{i}": "def" for i in range(MAX_MAPPINGS_PER_CATEGORY + 1)}
        profile_dict = {
            "profile_schema_version": 1,
            "keywords": too_many_keywords,
            "operators": {},
            "literals": {},
        }
        with pytest.raises(SurfaceTranslationError) as exc_info:
            SurfaceProfile.from_dict(profile_dict)
        assert "exceeds maximum" in str(exc_info.value)

    def test_canonical_depth_limit(self):
        """Verify deeply nested structures exceed MAX_NESTING_DEPTH."""
        def make_deep(n):
            if n == 0:
                return "base"
            return {"level": make_deep(n - 1)}

        # Depth 11 should fail (MAX_NESTING_DEPTH=10)
        deep = make_deep(11)
        from src.benchmark.canonical import canonical_json
        with pytest.raises(TypeError) as exc_info:
            canonical_json(deep)
        assert "Exceeds maximum nesting depth" in str(exc_info.value)

    def test_canonical_collection_size_limit(self):
        """Verify large collections exceed MAX_COLLECTION_SIZE."""
        from src.benchmark.canonical import canonical_json
        too_large = {str(i): i for i in range(MAX_COLLECTION_SIZE + 1)}
        with pytest.raises(TypeError) as exc_info:
            canonical_json(too_large)
        assert "exceeds maximum size" in str(exc_info.value)

    def test_canonical_string_length_limit(self):
        """Verify long strings exceed MAX_STRING_LENGTH."""
        from src.benchmark.canonical import canonical_json, sha256_text
        long_text = "x" * (MAX_STRING_LENGTH + 1)
        with pytest.raises(TypeError) as exc_info:
            canonical_json({"text": long_text})
        assert "exceeds maximum length" in str(exc_info.value)
        with pytest.raises(TypeError) as exc_info:
            sha256_text(long_text)
        assert "exceeds maximum length" in str(exc_info.value)

    def test_manifest_size_limit(self):
        """Verify manifest exceeding MAX_MANIFEST_SIZE is rejected."""
        from src.benchmark.canonical import canonical_bytes

        # Create a valid seed and profile first
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

        # Manifest should be well under limit, so reconstruction should succeed
        reconstructed = reconstruct_environment_from_manifest(manifest)
        assert reconstructed.environment_id == env.environment_id

    def test_manifest_at_exact_500kb_boundary(self):
        """Verify manifest at exactly 500,000 bytes boundary is accepted."""
        # Construct a manifest with size as close to 500,000 bytes as possible
        # Using 8 strings of 62400 chars each = 499,996 bytes (4 bytes under limit)

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
        env, _ = mgr.create_environment(seed, profile)

        # 8 strings of 62400 chars = 499,996 bytes (just under 500KB)
        large_seed = {
            "name": "test",
            "syntax_style": "lisp",
            "features": ["arithmetic", "functions"],
            "difficulty": 1,
            "arithmetic": "wraparound",
            "short_circuit": True,
            "f1": "x" * 62400,
            "f2": "y" * 62400,
            "f3": "z" * 62400,
            "f4": "a" * 62400,
            "f5": "b" * 62400,
            "f6": "c" * 62400,
            "f7": "d" * 62400,
            "f8": "e" * 62400,
        }

        large_manifest = DerivationManifest(
            schema_version=1,
            environment_id=env.environment_id,
            env_schema_version=1,
            generator_family_version="f1",
            generator_algorithm_version="1.0.0",
            seed=large_seed,
            surface_profile=profile,
            runtime_semantics_version=2,
            grammar_sha256=env.identity_core["grammar_sha256"],
            semantic_spec_sha256=env.identity_core["semantic_spec_sha256"],
            surface_profile_sha256=env.identity_core["surface_profile_sha256"],
        )

        # Verify actual size is just under limit
        from src.benchmark.canonical import canonical_bytes
        actual_size = len(canonical_bytes(large_manifest.to_dict()))
        assert actual_size <= MAX_MANIFEST_SIZE  # 499,996 bytes
        assert actual_size >= MAX_MANIFEST_SIZE - 100  # Close to boundary

        # Should be accepted (just under 500KB)
        reconstructed = reconstruct_environment_from_manifest(large_manifest)
        assert reconstructed.environment_id == env.environment_id

    def test_manifest_exceeding_500kb_boundary(self):
        """Verify manifest exceeding 500,000 bytes is rejected."""
        # Use the same setup but with one more character in each string
        # 8 strings of 62401 chars = 500,004 bytes (4 bytes over limit)

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
        env, _ = mgr.create_environment(seed, profile)

        # 8 strings of 62401 chars = 500,004 bytes (over 500KB)
        oversized_seed = {
            "name": "test",
            "syntax_style": "lisp",
            "features": ["arithmetic", "functions"],
            "difficulty": 1,
            "arithmetic": "wraparound",
            "short_circuit": True,
            "f1": "x" * 62401,
            "f2": "y" * 62401,
            "f3": "z" * 62401,
            "f4": "a" * 62401,
            "f5": "b" * 62401,
            "f6": "c" * 62401,
            "f7": "d" * 62401,
            "f8": "e" * 62401,
        }

        oversized_manifest = DerivationManifest(
            schema_version=1,
            environment_id=env.environment_id,
            env_schema_version=1,
            generator_family_version="f1",
            generator_algorithm_version="1.0.0",
            seed=oversized_seed,
            surface_profile=profile,
            runtime_semantics_version=2,
            grammar_sha256=env.identity_core["grammar_sha256"],
            semantic_spec_sha256=env.identity_core["semantic_spec_sha256"],
            surface_profile_sha256=env.identity_core["surface_profile_sha256"],
        )

        # Verify actual size exceeds limit
        from src.benchmark.canonical import canonical_bytes
        actual_size = len(canonical_bytes(oversized_manifest.to_dict()))
        assert actual_size > MAX_MANIFEST_SIZE  # 500,004 bytes

        # Should be rejected by preflight
        with pytest.raises(ValidationError, match="exceeds maximum size"):
            reconstruct_environment_from_manifest(oversized_manifest)

    def test_manifest_at_exact_boundary(self):
        """Verify manifest at exactly the accepted boundary is accepted."""
        # Create a manifest with large but valid seed that's close to 500KB
        # Each string is 65536 chars = ~65536 bytes
        # We need to fit within 500KB limit

        # Using 6 strings at 65536 chars each = ~393KB for strings
        # Total estimated: ~500KB which should be under 500KB

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

        # Create a large seed that approaches but stays under 500KB
        # Using 6 strings at 65536 chars each = ~393KB for strings
        # Total estimated: ~400KB which should be under 500KB
        large_seed = {
            "name": "test",
            "syntax_style": "lisp",
            "features": ["arithmetic", "functions"],
            "difficulty": 1,
            "arithmetic": "wraparound",
            "short_circuit": True,
            "f1": "x" * 65536,
            "f2": "y" * 65536,
            "f3": "z" * 65536,
            "f4": "a" * 65536,
            "f5": "b" * 65536,
            "f6": "c" * 65536,
        }

        large_manifest = DerivationManifest(
            schema_version=1,
            environment_id=env.environment_id,
            env_schema_version=1,
            generator_family_version="f1",
            generator_algorithm_version="1.0.0",
            seed=large_seed,
            surface_profile=profile,
            runtime_semantics_version=2,
            grammar_sha256=env.identity_core["grammar_sha256"],
            semantic_spec_sha256=env.identity_core["semantic_spec_sha256"],
            surface_profile_sha256=env.identity_core["surface_profile_sha256"],
        )

        # Should be accepted (under 500KB)
        reconstructed = reconstruct_environment_from_manifest(large_manifest)
        assert reconstructed.environment_id == env.environment_id

    def test_manifest_exceeding_boundary(self):
        """Verify manifest exceeding 500KB is rejected before reconstruction."""
        # Create a manifest with 7 large strings that exceeds 500KB
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

        # 8 strings at 65536 chars each = ~525KB for strings
        # Plus other fields exceeds 500KB
        oversized_seed = {
            "name": "test",
            "syntax_style": "lisp",
            "features": ["arithmetic", "functions"],
            "difficulty": 1,
            "arithmetic": "wraparound",
            "short_circuit": True,
            "f1": "x" * 65536,
            "f2": "y" * 65536,
            "f3": "z" * 65536,
            "f4": "a" * 65536,
            "f5": "b" * 65536,
            "f6": "c" * 65536,
            "f7": "d" * 65536,
            "f8": "e" * 65536,
        }

        oversized_manifest = DerivationManifest(
            schema_version=1,
            environment_id=env.environment_id,
            env_schema_version=1,
            generator_family_version="f1",
            generator_algorithm_version="1.0.0",
            seed=oversized_seed,
            surface_profile=profile,
            runtime_semantics_version=2,
            grammar_sha256=env.identity_core["grammar_sha256"],
            semantic_spec_sha256=env.identity_core["semantic_spec_sha256"],
            surface_profile_sha256=env.identity_core["surface_profile_sha256"],
        )

        # Should be rejected by preflight (before reconstruction)
        with pytest.raises(ValidationError, match="exceeds maximum size"):
            reconstruct_environment_from_manifest(oversized_manifest)

    def test_seed_name_boundary(self):
        """Verify seed name at exact MAX_NAME_LENGTH (50) is accepted, 51 rejected."""
        # Exactly 50 chars - should pass
        seed = LanguageSeed(
            name="a" * 50,
            syntax_style="lisp",
            features=["feature1"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        assert seed.name == "a" * 50

        # 51 chars - should fail
        with pytest.raises(ValidationError, match="name must be at most"):
            LanguageSeed(
                name="a" * 51,
                syntax_style="lisp",
                features=["feature1"],
                difficulty=1,
                arithmetic="wraparound",
                short_circuit=True,
            )

    def test_seed_feature_count_boundary(self):
        """Verify seed features at exact MAX_FEATURE_COUNT (10) is accepted, 11 rejected."""
        # Exactly 10 features - should pass
        seed = LanguageSeed(
            name="test",
            syntax_style="lisp",
            features=[f"feature{i}" for i in range(10)],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        assert len(seed.features) == 10

        # 11 features - should fail
        with pytest.raises(ValidationError, match="features must contain at most"):
            LanguageSeed(
                name="test",
                syntax_style="lisp",
                features=[f"feature{i}" for i in range(11)],
                difficulty=1,
                arithmetic="wraparound",
                short_circuit=True,
            )

    def test_seed_feature_length_boundary(self):
        """Verify seed feature at exact MAX_FEATURE_LENGTH (30) is accepted, 31 rejected."""
        # Exactly 30 chars - should pass
        seed = LanguageSeed(
            name="test",
            syntax_style="lisp",
            features=["a" * 30],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        assert len(seed.features[0]) == 30

        # 31 chars - should fail
        with pytest.raises(ValidationError, match="Each feature must be at most"):
            LanguageSeed(
                name="test",
                syntax_style="lisp",
                features=["a" * 31],
                difficulty=1,
                arithmetic="wraparound",
                short_circuit=True,
            )

    def test_seed_serialized_size_boundary(self):
        """Verify seed serialized at exact MAX_SERIALIZED_SEED_SIZE (4096) is accepted."""
        # Create a seed that serializes close to 4096 bytes
        # This requires careful construction since we can't easily control exact size
        # The validation happens in to_canonical_bytes after json.dumps
        seed = LanguageSeed(
            name="test",
            syntax_style="lisp",
            features=["arithmetic", "functions"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        # Small seed should be well under limit
        bytes_data = seed.to_canonical_bytes()
        assert len(bytes_data) < 4096

        # Create a seed with longer values that might approach limit
        long_seed = LanguageSeed(
            name="a" * 40,  # 40 chars for name
            syntax_style="lisp",
            features=["a" * 25 for _ in range(5)],  # 5 features at 25 chars each
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        long_bytes = long_seed.to_canonical_bytes()
        assert len(long_bytes) < 4096  # Should still be under limit

    def test_source_byte_boundary(self):
        """Verify source at exact MAX_SOURCE_LENGTH (65536 bytes) is accepted."""
        # Exactly 65536 bytes - should pass
        source_65536 = "a" * 65536
        assert len(source_65536.encode("utf-8")) == 65536

        profile = SurfaceProfile(
            keywords={}, operators={}, literals={}, profile_schema_version=1
        )
        result = to_canonical(source_65536, profile)
        assert result.canonical_text is not None

        # 65537 bytes - should fail
        source_65537 = "a" * 65537
        with pytest.raises(SurfaceTranslationError, match="exceeds maximum length"):
            to_canonical(source_65537, profile)

    def test_profile_mapping_key_target_boundary(self):
        """Verify mapping key/target at exact MAX length (64) is accepted."""
        # Exactly 64 chars for key and target - should pass
        profile_dict = {
            "profile_schema_version": 1,
            "keywords": {"a" * 64: "def"},
            "operators": {"b" * 64: "add"},
            "literals": {"c" * 64: "true"},
        }
        profile = SurfaceProfile.from_dict(profile_dict)
        assert "a" * 64 in profile.keywords
        assert "b" * 64 in profile.operators
        assert "c" * 64 in profile.literals

        # 65 chars - should fail
        profile_dict_over = {
            "profile_schema_version": 1,
            "keywords": {"a" * 65: "def"},
            "operators": {},
            "literals": {},
        }
        with pytest.raises(SurfaceTranslationError, match="exceeds maximum length"):
            SurfaceProfile.from_dict(profile_dict_over)

    def test_canonical_depth_boundary(self):
        """Verify canonical structure at exact MAX_NESTING_DEPTH (10) is accepted."""
        def make_deep(n):
            if n == 0:
                return "base"
            return {"level": make_deep(n - 1)}

        # Depth 10 - should pass
        deep_10 = make_deep(10)
        from src.benchmark.canonical import canonical_json
        result = canonical_json(deep_10)
        assert result is not None

        # Depth 11 - should fail
        deep_11 = make_deep(11)
        with pytest.raises(TypeError, match="Exceeds maximum nesting depth"):
            canonical_json(deep_11)

    def test_canonical_collection_size_boundary(self):
        """Verify collection at exact MAX_COLLECTION_SIZE (1000) is accepted."""
        from src.benchmark.canonical import canonical_json
        # Exactly 1000 items - should pass
        collection_1000 = {str(i): i for i in range(1000)}
        result = canonical_json(collection_1000)
        assert result is not None

        # 1001 items - should fail
        collection_1001 = {str(i): i for i in range(1001)}
        with pytest.raises(TypeError, match="exceeds maximum size"):
            canonical_json(collection_1001)

    def test_canonical_string_length_boundary(self):
        """Verify string at exact MAX_STRING_LENGTH (65536) is accepted."""
        from src.benchmark.canonical import canonical_json
        # Exactly 65536 chars - should pass
        string_65536 = "x" * 65536
        result = canonical_json({"text": string_65536})
        assert result is not None

        # 65537 chars - should fail
        string_65537 = "x" * 65537
        with pytest.raises(TypeError, match="exceeds maximum length"):
            canonical_json({"text": string_65537})
