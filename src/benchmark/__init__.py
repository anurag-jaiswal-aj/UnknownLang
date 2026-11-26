"""Wave 2 Benchmark Platform.

This package provides the benchmark task generation, validation,
evaluation, and execution infrastructure for the UnknownLang project.

M2.5 Task Generation System:
- Task generators for EVAL, SYN, INF, CTRL categories
- Deterministic generation from derivation seeds
- Two-source verification (production + reference)
- Pair generation with validation gates T7/T8
- Identifiability (T13) and non-triviality (T9)
- Chance floor control (T10)

Submodules:
- canonical: Canonical JSON and SHA-256 hashing
- environments: Environment derivation and management
- generators: Task generators for value and program tasks
- harness: Task evaluation harness
- manager: Benchmark execution manager
- prompts: Prompt builder and template registry
- scoring: Scoring and metrics
- store: Content-addressed storage
"""

from .canonical import canonical_json, sha256_hex, sha256_text

__all__ = [
    # Canonical
    "canonical_json",
    "sha256_hex",
    "sha256_text",
]
