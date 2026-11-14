"""Language identity calculation using SHA-256."""

import hashlib
from typing import Optional

from .seed import LanguageSeed, ValidationError


def compute_language_id(
    seed: LanguageSeed,
    spec_version: str = "1.0.0",
    algorithm_version: str = "1.0.0",
) -> str:
    """
    Compute deterministic language identity from seed and versions.
    
    The identity is computed as SHA256(canonical_seed + spec_version + algorithm_version)
    where canonical_seed is the JSON serialization with sorted keys.
    
    The same seed and versions always produce the same identity.
    Changing spec_version or algorithm_version changes the identity.
    The generated_at timestamp is never included in the identity.
    
    Args:
        seed: Validated LanguageSeed instance
        spec_version: Specification version string (default: "1.0.0")
        algorithm_version: Generator algorithm version string (default: "1.0.0")
    
    Returns:
        69-character hexadecimal language identifier prefixed with "lang_"
        (lang_ + 64 hex chars = full SHA-256 digest for cryptographic certainty)
    
    Raises:
        ValidationError: If seed is not valid
    """
    canonical_bytes = seed.to_canonical_bytes(spec_version, algorithm_version)
    hash_digest = hashlib.sha256(canonical_bytes).hexdigest()
    return f"lang_{hash_digest}"


def compute_language_id_from_dict(
    seed_dict: dict,
    spec_version: str = "1.0.0",
    algorithm_version: str = "1.0.0",
) -> str:
    """
    Compute language identity from raw dictionary seed.
    
    Convenience function that validates and creates a LanguageSeed internally.
    
    Args:
        seed_dict: Raw dictionary containing seed data
        spec_version: Specification version string (default: "1.0.0")
        algorithm_version: Generator algorithm version string (default: "1.0.0")
    
    Returns:
        69-character hexadecimal language identifier prefixed with "lang_"
    
    Raises:
        ValidationError: If seed_dict is invalid
    """
    seed = LanguageSeed.from_dict(seed_dict)
    return compute_language_id(seed, spec_version, algorithm_version)


def verify_identity_determinism(
    seed: LanguageSeed,
    spec_version: str = "1.0.0",
    algorithm_version: str = "1.0.0",
    iterations: int = 10,
) -> bool:
    """
    Verify that the same seed produces identical identities across multiple calls.
    
    Used for testing and validation purposes.
    
    Args:
        seed: Validated LanguageSeed instance
        spec_version: Specification version string
        algorithm_version: Generator algorithm version string
        iterations: Number of times to verify (default: 10)
    
    Returns:
        True if all iterations produce identical identity
    """
    identity = compute_language_id(seed, spec_version, algorithm_version)
    for _ in range(iterations - 1):
        if compute_language_id(seed, spec_version, algorithm_version) != identity:
            return False
    return True
