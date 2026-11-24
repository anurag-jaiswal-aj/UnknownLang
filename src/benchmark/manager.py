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

    This function performs exact incremental byte accounting that matches
    the canonical JSON serialization contract in canonical.py.

    It uses a bounded serializer that:
    1. Validates all string lengths before encoding
    2. Calculates exact UTF-8 byte count for each element
    3. Stops immediately when budget exceeded
    4. Does not build complete serialized output
    """
    from src.language.surface import MAX_STRING_LENGTH as MAX_STRING

    budget = MAX_MANIFEST_SIZE

    # Track cumulative size
    size = 0

    # Top-level structure: {"field1": value1, "field2": value2, ...}
    fixed_keys = [
        "schema_version", "environment_id", "env_schema_version",
        "generator_family_version", "generator_algorithm_version",
        "seed", "surface_profile", "runtime_semantics_version",
        "grammar_sha256", "semantic_spec_sha256", "surface_profile_sha256"
    ]

    # Opening brace: 1 byte
    size += 1

    # Process each key-value pair incrementally
    for i, key in enumerate(fixed_keys):
        # Key with quotes
        size += len(key.encode("utf-8")) + 2  # +2 for quotes

        # Colon separator
        size += 1

        # Add value size based on type and field
        if key == "schema_version":
            size += len(str(manifest.schema_version).encode("utf-8"))
        elif key == "environment_id":
            size += len(manifest.environment_id.encode("utf-8")) + 2  # +2 for quotes
        elif key == "env_schema_version":
            size += len(str(manifest.env_schema_version).encode("utf-8"))
        elif key == "generator_family_version":
            size += len(manifest.generator_family_version.encode("utf-8")) + 2
        elif key == "generator_algorithm_version":
            size += len(manifest.generator_algorithm_version.encode("utf-8")) + 2
        elif key == "seed":
            # Validate and account for seed dict
            seed_size = _estimate_dict_size_bounded(manifest.seed, budget - size, "seed")
            size += seed_size
        elif key == "surface_profile":
            # Validate and account for surface_profile dict
            profile_size = _estimate_dict_size_bounded(manifest.surface_profile, budget - size, "surface_profile")
            size += profile_size
        elif key == "runtime_semantics_version":
            size += len(str(manifest.runtime_semantics_version).encode("utf-8"))
        elif key in ("grammar_sha256", "semantic_spec_sha256", "surface_profile_sha256"):
            size += 64 + 2  # 64 hex chars + 2 quotes
        else:
            raise ValidationError(f"Unexpected manifest field: {key}")

        # Comma separator (except for last field)
        if i < len(fixed_keys) - 1:
            size += 1

        # Check budget after each field
        if size > budget:
            raise ValidationError(
                f"Manifest exceeds maximum size of {MAX_MANIFEST_SIZE} bytes "
                f"({size} bytes estimated)"
            )

    # Closing brace: 1 byte
    size += 1

    # Final budget check
    if size > budget:
        raise ValidationError(
            f"Manifest exceeds maximum size of {MAX_MANIFEST_SIZE} bytes "
            f"({size} bytes estimated)"
        )


def _estimate_dict_size_bounded(d: dict, budget: int, path: str) -> int:
    """Estimate dict size with bounded checking, matching canonical JSON encoding.

    This function performs exact incremental byte accounting that matches
    the canonical JSON serialization behavior in canonical.py:
    - JSON with sort_keys=True
    - separators=(',', ':')
    - ensure_ascii=True
    - UTF-8 encoding

    Returns exact encoded size or raises ValidationError if budget exceeded.
    Stops processing immediately when budget exceeded.
    """
    from src.language.surface import MAX_STRING_LENGTH as MAX_STRING

    size = 0

    # Opening brace: 1 byte
    size += 1

    # Get items in sorted order (matching canonical_json's sort_keys=True)
    items = sorted(d.items(), key=lambda x: x[0])
    num_items = len(items)

    for i, (key, value) in enumerate(items):
        # Key with quotes
        if type(key) is not str:
            raise ValidationError(f"Dictionary keys must be strings at {path}")
        
        key_bytes = key.encode("utf-8")
        size += len(key_bytes) + 2  # +2 for quotes

        if size > budget:
            raise ValidationError(
                f"Manifest exceeds maximum size of {MAX_MANIFEST_SIZE} bytes "
                f"({size} bytes estimated)"
            )

        # Colon separator: 1 byte
        size += 1

        # Value size based on type (exact canonical JSON encoding)
        value_bytes = _estimate_json_value_size(value, budget - size, f"{path}.{key}")
        size += value_bytes

        # Comma separator (except for last item): 1 byte
        if i < num_items - 1:
            size += 1

        if size > budget:
            raise ValidationError(
                f"Manifest exceeds maximum size of {MAX_MANIFEST_SIZE} bytes "
                f"({size} bytes estimated)"
            )

    # Closing brace: 1 byte
    size += 1

    return size


def _estimate_json_value_size(value: Any, budget: int, path: str) -> int:
    """Estimate exact UTF-8 byte size for a JSON value.

    This matches canonical_json's exact serialization rules:
    - sort_keys=True for dicts
    - separators=(',', ':')
    - ensure_ascii=True
    - UTF-8 encoding

    Returns exact byte count or raises ValidationError if budget exceeded.
    """
    from src.language.surface import MAX_STRING_LENGTH as MAX_STRING

    if value is None:
        return len(b"null")

    if type(value) is bool:
        return len(b"true") if value else len(b"false")

    if type(value) is int:
        # Exact byte count for integer string representation
        return len(str(value).encode("utf-8"))

    if type(value) is str:
        # Validate string length
        if len(value) > MAX_STRING:
            raise ValidationError(
                f"String at {path} exceeds maximum length of {MAX_STRING} "
                f"({len(value)} characters)"
            )
        # canonical_json uses ensure_ascii=True which escapes non-ASCII to \uXXXX
        # Calculate escaped size:
        # - Quotes: 2 bytes
        # - ASCII chars (0-127): 1 byte each (except special chars)
        # - Non-ASCII chars in BMP (128-65535): 6 bytes (\uXXXX format)
        # - Non-BMP chars (>65535): 12 bytes (surrogate pair: \uD83C\uDF0D)
        
        size = 2  # Quotes
        
        for char in value:
            code_point = ord(char)
            
            # Handle special chars that need backslash escaping
            if char in ('"', '\\', '\b', '\f', '\n', '\r', '\t'):
                # Backslash + char = 2 bytes
                size += 2
            elif code_point < 128:
                # ASCII (no escaping needed): 1 byte
                size += 1
            elif code_point < 65536:
                # BMP char: 6 bytes (\uXXXX format)
                size += 6
            else:
                # Non-BMP char (emoji etc): 12 bytes (surrogate pair)
                # Python's ensure_ascii uses UTF-16 surrogate pairs
                # e.g., 🌍 (U+1F30D) becomes \uD83C\uDF0D
                size += 12
        
        if size > budget:
            raise ValidationError(
                f"Manifest exceeds maximum size of {MAX_MANIFEST_SIZE} bytes "
                f"({size} bytes estimated)"
            )
        return size

    if isinstance(value, (list, tuple)):
        if isinstance(value, tuple):
            raise ValidationError(f"Tuples are not permitted at {path}")
        
        # Check collection size
        if len(value) > 1000:
            raise ValidationError(
                f"List at {path} exceeds maximum size of 1000"
            )

        size = 1  # Opening bracket

        for index, item in enumerate(value):
            # Validate string length for items
            if isinstance(item, str) and len(item) > MAX_STRING:
                raise ValidationError(
                    f"String at {path}[{index}] exceeds maximum length of {MAX_STRING}"
                )
            
            item_size = _estimate_json_value_size(item, budget - size, f"{path}[{index}]")
            size += item_size

            # Comma separator (except for last item)
            if index < len(value) - 1:
                size += 1

            if size > budget:
                raise ValidationError(
                    f"Manifest exceeds maximum size of {MAX_MANIFEST_SIZE} bytes "
                    f"({size} bytes estimated)"
                )

        size += 1  # Closing bracket
        return size

    if isinstance(value, dict):
        # Check collection size
        if len(value) > 1000:
            raise ValidationError(
                f"Object at {path} exceeds maximum size of 1000"
            )

        # Use the dict estimator which handles nested structures
        return _estimate_dict_size_bounded(value, budget, path)

    raise ValidationError(f"Unsupported type at {path}: {type(value).__name__}")


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
