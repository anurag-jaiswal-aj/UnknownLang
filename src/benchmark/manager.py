"""Wave 2 environment lifecycle manager with deterministic derivation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from src.execution.types import RUNTIME_SEMANTICS_VERSION
from src.language.generator import LanguageGenerator
from src.language.seed import LanguageSeed, ValidationError
from src.language.surface import SurfaceProfile

from .canonical import canonical_bytes, canonical_json, sha256_hex, sha256_text
from .environments import (
    ENV_SCHEMA_VERSION,
    GENERATOR_ALGORITHM_VERSION,
    GENERATOR_FAMILY_VERSION,
    EnvironmentRecord,
    build_environment,
    identity_core as build_identity_core,
    semantic_projection,
)


# Derivation manifest version for reproducible reconstruction
DERIVATION_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class DerivationManifest:
    """Versioned record of how an environment was derived.

    This manifest contains all inputs needed to reconstruct an environment
    and verify its identity. It does NOT affect environment identity itself.
    """

    schema_version: int
    environment_id: str
    env_schema_version: int
    generator_family_version: str
    generator_algorithm_version: str
    seed: dict[str, Any]
    surface_profile: dict[str, Any]
    runtime_semantics_version: int
    grammar_sha256: str
    semantic_spec_sha256: str
    surface_profile_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "environment_id": self.environment_id,
            "env_schema_version": self.env_schema_version,
            "generator_family_version": self.generator_family_version,
            "generator_algorithm_version": self.generator_algorithm_version,
            "seed": self.seed,
            "surface_profile": self.surface_profile,
            "runtime_semantics_version": self.runtime_semantics_version,
            "grammar_sha256": self.grammar_sha256,
            "semantic_spec_sha256": self.semantic_spec_sha256,
            "surface_profile_sha256": self.surface_profile_sha256,
        }

    def to_canonical_bytes(self) -> bytes:
        """Return deterministic canonical bytes for the manifest."""
        return canonical_bytes(self.to_dict())


def create_derivation_manifest(
    record: EnvironmentRecord,
    seed: LanguageSeed,
    surface_profile: Mapping[str, Any],
) -> DerivationManifest:
    """Create a derivation manifest for an existing environment record."""
    return DerivationManifest(
        schema_version=DERIVATION_SCHEMA_VERSION,
        environment_id=record.environment_id,
        env_schema_version=record.identity_core["env_schema_version"],
        generator_family_version=record.identity_core["generator_family_version"],
        generator_algorithm_version=record.identity_core["generator_algorithm_version"],
        seed=seed.to_dict(),
        surface_profile=dict(surface_profile),
        runtime_semantics_version=record.identity_core["runtime_semantics_version"],
        grammar_sha256=record.identity_core["grammar_sha256"],
        semantic_spec_sha256=record.identity_core["semantic_spec_sha256"],
        surface_profile_sha256=record.identity_core["surface_profile_sha256"],
    )


def reconstruct_environment_from_manifest(
    manifest: DerivationManifest,
) -> EnvironmentRecord:
    """Reconstruct an environment from its derivation manifest.

    This function verifies that the reconstructed identity matches the
    manifest's stored identity, ensuring reproducibility.

    Raises:
        ValidationError: If manifest is invalid or identity doesn't match
    """
    if manifest.schema_version != DERIVATION_SCHEMA_VERSION:
        raise ValidationError(
            f"Unsupported derivation schema version: {manifest.schema_version}. "
            f"Supported: {DERIVATION_SCHEMA_VERSION}"
        )

    # Validate version fields
    if manifest.env_schema_version != ENV_SCHEMA_VERSION:
        raise ValidationError(
            f"Unsupported env schema version: {manifest.env_schema_version}. "
            f"Supported: {ENV_SCHEMA_VERSION}"
        )

    if manifest.generator_family_version != GENERATOR_FAMILY_VERSION:
        raise ValidationError(
            f"Unsupported generator family: {manifest.generator_family_version}. "
            f"Supported: {GENERATOR_FAMILY_VERSION}"
        )

    if manifest.generator_algorithm_version != GENERATOR_ALGORITHM_VERSION:
        raise ValidationError(
            f"Unsupported generator algorithm: {manifest.generator_algorithm_version}. "
            f"Supported: {GENERATOR_ALGORITHM_VERSION}"
        )

    if manifest.runtime_semantics_version != RUNTIME_SEMANTICS_VERSION:
        raise ValidationError(
            f"Runtime semantics version mismatch: {manifest.runtime_semantics_version}. "
            f"Expected: {RUNTIME_SEMANTICS_VERSION}"
        )

    # Reconstruct seed and surface profile
    try:
        seed = LanguageSeed.from_dict(manifest.seed)
        surface_profile = SurfaceProfile.from_dict(manifest.surface_profile)
    except (ValidationError, KeyError) as e:
        raise ValidationError(f"Failed to reconstruct seed/profile from manifest: {e}")

    # Rebuild the environment using the same inputs
    try:
        env = build_environment(
            seed.arithmetic,
            seed.short_circuit,
            manifest.surface_profile,
        )
    except Exception as e:
        raise ValidationError(f"Failed to rebuild environment: {e}")

    # Verify identity matches
    if env.environment_id != manifest.environment_id:
        raise ValidationError(
            f"Reconstructed identity mismatch. Expected: {manifest.environment_id}, "
            f"Got: {env.environment_id}"
        )

    return env


def _verify_manifest_with_hash_checks(manifest: DerivationManifest) -> EnvironmentRecord:
    """Verify manifest reconstruction with explicit hash verification.

    This function:
    1. Reconstructs seed and surface profile from manifest
    2. Rebuilds the environment using authoritative generation
    3. Verifies the computed environment_id matches manifest
    4. Recomputes and verifies individual hashes for integrity

    Raises:
        ValidationError: If any verification fails
    """
    # Reconstruct seed and surface profile
    seed = LanguageSeed.from_dict(manifest.seed)
    surface_profile = SurfaceProfile.from_dict(manifest.surface_profile)

    # Rebuild the environment using the same inputs
    env = build_environment(
        seed.arithmetic,
        seed.short_circuit,
        manifest.surface_profile,
    )

    # Verify environment_id matches (computed identity verification)
    if env.environment_id != manifest.environment_id:
        raise ValidationError(
            f"Reconstructed identity mismatch. Expected: {manifest.environment_id}, "
            f"Got: {env.environment_id}"
        )

    # Reconstruct the spec to verify individual hashes
    spec = LanguageGenerator().generate(
        seed,
        spec_version="1.0.0",
        algorithm_version=GENERATOR_ALGORITHM_VERSION,
    )

    # Verify grammar hash
    computed_grammar_sha256 = sha256_text(spec.grammar)
    if computed_grammar_sha256 != manifest.grammar_sha256:
        raise ValidationError(
            f"Grammar hash mismatch. Expected: {manifest.grammar_sha256}, "
            f"Got: {computed_grammar_sha256}"
        )

    # Verify semantic spec hash
    computed_semantic_sha256 = sha256_hex(semantic_projection(spec))
    if computed_semantic_sha256 != manifest.semantic_spec_sha256:
        raise ValidationError(
            f"Semantic spec hash mismatch. Expected: {manifest.semantic_spec_sha256}, "
            f"Got: {computed_semantic_sha256}"
        )

    # Verify surface profile hash
    computed_surface_sha256 = sha256_hex(dict(manifest.surface_profile))
    if computed_surface_sha256 != manifest.surface_profile_sha256:
        raise ValidationError(
            f"Surface profile hash mismatch. Expected: {manifest.surface_profile_sha256}, "
            f"Got: {computed_surface_sha256}"
        )

    return env


class EnvironmentManager:
    """Environment lifecycle manager with deterministic reconstruction."""

    def __init__(self) -> None:
        self._generator = LanguageGenerator()

    def create_environment(
        self,
        seed: LanguageSeed,
        surface_profile: Mapping[str, Any],
    ) -> tuple[EnvironmentRecord, DerivationManifest]:
        """Create a new validated environment and its derivation manifest.

        Args:
            seed: Language seed with feature configuration
            surface_profile: Surface profile mapping for translation

        Returns:
            Tuple of (environment_record, derivation_manifest)

        Raises:
            ValidationError: If seed is invalid or environment cannot be built
        """
        # Validate seed
        self._generator._semantic_registry.validate_seed(seed)

        # Validate surface profile
        SurfaceProfile.from_dict(surface_profile)

        # Build the environment
        env = build_environment(
            seed.arithmetic,
            seed.short_circuit,
            surface_profile,
        )

        # Create derivation manifest
        manifest = create_derivation_manifest(env, seed, surface_profile)

        return env, manifest

    def validate_environment(self, record: EnvironmentRecord) -> bool:
        """Validate an environment record.

        Checks:
        - Identity core has all required fields
        - SHA-256 hashes are valid format
        - Runtime version matches current runtime

        Args:
            record: Environment record to validate

        Returns:
            True if valid

        Raises:
            ValidationError: If validation fails
        """
        core = record.identity_core
        if not isinstance(core, dict):
            raise ValidationError("identity_core must be a dictionary")

        required = {
            "env_schema_version",
            "generator_family_version",
            "generator_algorithm_version",
            "grammar_sha256",
            "semantic_spec_sha256",
            "surface_profile_sha256",
            "runtime_semantics_version",
        }
        if set(core) != required:
            raise ValidationError(
                f"identity_core must have exactly these fields: {sorted(required)}"
            )

        for field in ("grammar_sha256", "semantic_spec_sha256", "surface_profile_sha256"):
            value = core[field]
            if type(value) is not str or len(value) != 64:
                raise ValidationError(
                    f"{field} must be 64-character lowercase hex string"
                )
            if any(c not in "0123456789abcdef" for c in value):
                raise ValidationError(
                    f"{field} must be lowercase hex, found: {value}"
                )

        if core["runtime_semantics_version"] != RUNTIME_SEMANTICS_VERSION:
            raise ValidationError(
                f"runtime_semantics_version mismatch: {core['runtime_semantics_version']} "
                f"!= {RUNTIME_SEMANTICS_VERSION}"
            )

        return True

    def verify_reconstruction(
        self,
        manifest: DerivationManifest,
    ) -> EnvironmentRecord:
        """Verify that a manifest can be reconstructed to the expected identity.

        This is useful for testing reproducibility and validating that
        the same inputs always produce the same environment.

        Args:
            manifest: Derivation manifest to verify

        Returns:
            The reconstructed environment record

        Raises:
            ValidationError: If reconstruction fails or identity doesn't match
        """
        # Perform full verification with hash checks
        return _verify_manifest_with_hash_checks(manifest)

    def resolve_environment(self, environment_id: str) -> EnvironmentRecord | None:
        """Attempt to resolve an environment by its canonical identity.

        This is a placeholder for future persistent storage. Currently
        always returns None.

        Args:
            environment_id: The canonical environment ID to resolve

        Returns:
            EnvironmentRecord if found, None otherwise
        """
        # TODO: Implement content-addressed storage lookup
        # For now, this is a placeholder for the future store implementation
        return None
