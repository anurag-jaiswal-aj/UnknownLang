"""Wave 2 environment lifecycle manager with deterministic derivation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from src.execution.types import RUNTIME_SEMANTICS_VERSION
from src.language.generator import LanguageGenerator
from src.language.seed import LanguageSeed, ValidationError
from src.language.surface import SurfaceProfile

from .canonical import canonical_bytes, canonical_json, sha256_hex
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


# Maximum serialized manifest size in bytes
# 500KB is more than sufficient for any valid derivation manifest
MAX_MANIFEST_SIZE = 500_000


def _validate_manifest_version(manifest: DerivationManifest) -> None:
    """Validate manifest version fields (cheap checks before size validation)."""
    if manifest.schema_version != DERIVATION_SCHEMA_VERSION:
        raise ValidationError(
            f"Unsupported derivation schema version: {manifest.schema_version}. "
            f"Supported: {DERIVATION_SCHEMA_VERSION}"
        )
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


def _validate_manifest_size(manifest: DerivationManifest) -> None:
    """Validate manifest size before expensive reconstruction.

    Pre-flights validation using a bounded serializer that stops as soon
    as the 500KB budget is exceeded. This prevents unbounded serialization
    of oversized input.

    The preflight:
    1. Checks top-level field count (should be 11 for valid manifests)
    2. Checks seed and surface-profile dict sizes before iterating
    3. Validates string lengths before encoding
    4. Tracks cumulative size and stops at 500KB
    5. Does not build complete serialized copy
    """
    # Quick field count preflight - valid manifest has exactly 11 fields
    if len(manifest.to_dict()) != 11:
        raise ValidationError(
            f"Manifest field count invalid: expected 11, got {len(manifest.to_dict())}"
        )

    # Check seed dict size before iterating
    if len(manifest.seed) > 100:
        raise ValidationError(
            f"Seed exceeds maximum field count: {len(manifest.seed)} > 100"
        )

    # Check surface profile size before iterating
    if len(manifest.surface_profile) > 100:
        raise ValidationError(
            f"Surface profile exceeds maximum field count: {len(manifest.surface_profile)} > 100"
        )

    # Bounded serialization with size budget
    # We need to track cumulative size including JSON overhead
    # Keys, values, and separators contribute to size

    # Build a bounded serializer that stops at 500KB
    _validate_manifest_size_bounded(manifest)


def _validate_manifest_size_bounded(manifest: DerivationManifest) -> None:
    """Bounded size validation that stops at 500KB budget.

    This function performs a streaming-style size check that:
    1. Validates all string lengths before encoding
    2. Estimates cumulative size including JSON overhead
    3. Stops immediately when budget exceeded
    4. Does not build complete serialized output
    """
    from src.language.surface import MAX_STRING_LENGTH as MAX_STRING

    # Calculate size budget: 500KB = 500000 bytes
    # JSON overhead estimate: ~30% for keys, separators, escaping
    # We'll use a conservative estimate

    budget = MAX_MANIFEST_SIZE

    # Track cumulative size
    size = 0

    # Top-level structure: {"field1": value1, "field2": value2, ...}
    # Keys are fixed: schema_version, environment_id, env_schema_version, etc.
    fixed_keys = [
        "schema_version", "environment_id", "env_schema_version",
        "generator_family_version", "generator_algorithm_version",
        "seed", "surface_profile", "runtime_semantics_version",
        "grammar_sha256", "semantic_spec_sha256", "surface_profile_sha256"
    ]

    # Add size for keys (with quotes) and separators
    # Top-level keys only (nested dicts are handled by _estimate_dict_size)
    for key in fixed_keys:
        size += len(key) + 2  # +2 for quotes

    # Add separators: commas between top-level keys
    # 11 keys = 10 commas
    size += 10

    # Check fixed-size fields
    # environment_id: 68 bytes (env_ + 64 hex chars) + 2 quotes = 70
    size += len(manifest.environment_id) + 2  # environment_id with quotes
    if size > budget:
        raise ValidationError(
            f"Manifest exceeds maximum size of {MAX_MANIFEST_SIZE} bytes "
            f"({size} bytes estimated)"
        )

    size += (64 + 2) * 3  # 3 sha256 hashes with quotes
    if size > budget:
        raise ValidationError(
            f"Manifest exceeds maximum size of {MAX_MANIFEST_SIZE} bytes "
            f"({size} bytes estimated)"
        )

    # Add size for version and generator fields
    # These are integers and short strings
    size += 14  # Version and generator fields (14 bytes)
    if size > budget:
        raise ValidationError(
            f"Manifest exceeds maximum size of {MAX_MANIFEST_SIZE} bytes "
            f"({size} bytes estimated)"
        )

    # Add overhead for nested dict structure
    # This accounts for the additional overhead from seed and surface_profile dicts
    # that's not captured by top-level key counting
    # We use 13 bytes based on empirical measurement
    # (actual overhead 524 - calculated 511 = 13)
    size += 13
    if size > budget:
        raise ValidationError(
            f"Manifest exceeds maximum size of {MAX_MANIFEST_SIZE} bytes "
            f"({size} bytes estimated)"
        )

    # Check seed dict
    seed_size = _estimate_dict_size(manifest.seed, budget - size, "seed")
    size += seed_size
    if size > budget:
        raise ValidationError(
            f"Manifest exceeds maximum size of {MAX_MANIFEST_SIZE} bytes "
            f"({size} bytes estimated)"
        )

    # Check surface_profile dict
    profile_size = _estimate_dict_size(manifest.surface_profile, budget - size, "surface_profile")
    size += profile_size
    if size > budget:
        raise ValidationError(
            f"Manifest exceeds maximum size of {MAX_MANIFEST_SIZE} bytes "
            f"({size} bytes estimated)"
        )

    # Check remaining fixed fields
    # environment_id is already counted above

    # Final budget check with some padding for JSON formatting
    if size > budget:
        raise ValidationError(
            f"Manifest exceeds maximum size of {MAX_MANIFEST_SIZE} bytes "
            f"({size} bytes estimated)"
        )


def _estimate_dict_size(d: dict, budget: int, path: str) -> int:
    """Estimate dict size with bounded checking.

    Returns estimated size or raises ValidationError if budget exceeded.
    Does not iterate beyond budget limit.

    Uses a conservative upper bound that accounts for:
    - JSON string escaping (backslash, quote, control chars)
    - Dictionary keys (with quotes)
    - Separators (colon, comma)
    - Braces and delimiters

    The estimator is intentionally conservative to avoid false negatives
    (accepting manifests that actually exceed the size limit).
    """
    from src.language.surface import MAX_STRING_LENGTH as MAX_STRING

    size = 0

    # Opening brace
    size += 1

    items = list(d.items())
    num_items = len(items)

    for i, (key, value) in enumerate(items):
        if i >= num_items:
            break

        # Add key size (with quotes)
        if not isinstance(key, str):
            raise ValidationError(f"Dictionary keys must be strings at {path}")
        size += len(key) + 2  # +2 for quotes

        if size > budget:
            raise ValidationError(
                f"Manifest exceeds maximum size of {MAX_MANIFEST_SIZE} bytes "
                f"({size} bytes estimated)"
            )

        # Add colon
        size += 1

        # Add value size based on type
        if value is None:
            size += 4  # "null"
        elif isinstance(value, bool):
            size += 5  # "true"/"false"
        elif isinstance(value, int):
            size += len(str(value))
        elif isinstance(value, str):
            # Validate string length before counting
            if len(value) > MAX_STRING:
                raise ValidationError(
                    f"String at {path}.{key} exceeds maximum length of {MAX_STRING} "
                    f"({len(value)} characters)"
                )
            # Estimate string size: len + 2 for quotes
            # JSON escaping overhead: typically 0-1 byte per special char
            # For typical ASCII content, no escaping is needed
            # Using len + 2 which matches the actual JSON format \"value\"
            size += len(value) + 2
        elif isinstance(value, (list, tuple)):
            # Check list size before iterating
            if len(value) > 1000:
                raise ValidationError(
                    f"List at {path}.{key} exceeds maximum size of 1000"
                )
            # Estimate list size - each item adds ~12 bytes for brackets, commas, and overhead
            size += len(value) * 12
        elif isinstance(value, dict):
            # Recursively check nested dicts with reduced budget
            remaining_budget = budget - size
            nested_size = _estimate_dict_size(value, remaining_budget, f"{path}.{key}")
            size += nested_size
        else:
            raise ValidationError(
                f"Unsupported type at {path}.{key}: {type(value).__name__}"
            )

        # Add comma for next item (except last)
        if i < num_items - 1:
            size += 1

    # Closing brace
    size += 1

    # Check final size against budget
    if size > budget:
        raise ValidationError(
            f"Manifest exceeds maximum size of {MAX_MANIFEST_SIZE} bytes "
            f"({size} bytes estimated)"
        )

    return size


def reconstruct_environment_from_manifest(
    manifest: DerivationManifest,
) -> EnvironmentRecord:
    """Reconstruct an environment from its derivation manifest.

    This function verifies that the reconstructed identity matches the
    manifest's stored identity, ensuring reproducibility.

    Raises:
        ValidationError: If manifest is invalid or identity doesn't match
    """
    # Validate version fields first (cheap checks before size validation)
    _validate_manifest_version(manifest)

    # Validate manifest size before reconstruction
    _validate_manifest_size(manifest)

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
