"""Wave 2.2 conformance corpus tests for runtime, surface, and derivation."""
import json
import pathlib

import pytest

from src.benchmark.manager import DerivationManifest, EnvironmentManager, reconstruct_environment_from_manifest
from src.execution.engine import ExecutionEngine
from src.language.seed import LanguageSeed, ValidationError
from src.language.surface import SurfaceProfile, to_canonical
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
