"""Trusted-local Wave 2 environment identity and validation foundations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from src.execution.types import RUNTIME_SEMANTICS_VERSION
from src.language.generator import LanguageGenerator, LanguageSpec
from src.language.seed import LanguageSeed, ValidationError, VALID_FEATURES
from src.language.surface import SurfaceProfile

from .canonical import sha256_hex, sha256_text

ENV_SCHEMA_VERSION = 1
GENERATOR_FAMILY_VERSION = "f1"
GENERATOR_ALGORITHM_VERSION = "1.0.0"


@dataclass(frozen=True)
class EnvironmentRecord:
    """Content-addressed identity and descriptive metadata for one environment."""

    environment_id: str
    identity_core: dict[str, Any]
    observable_fingerprint: str
    surface_id: str
    semantic: dict[str, Any]
    surface_profile: dict[str, Any]
    runtime: dict[str, Any]
    derivation: dict[str, Any] | None = None
    status: str = "validated"

    def to_dict(self) -> dict[str, Any]:
        return {
            "environment_id": self.environment_id,
            "identity_core": self.identity_core,
            "observable_fingerprint": self.observable_fingerprint,
            "surface_id": self.surface_id,
            "semantic": self.semantic,
            "surface_profile": self.surface_profile,
            "runtime": self.runtime,
            "derivation": self.derivation,
            "status": self.status,
        }


def semantic_projection(spec: LanguageSpec) -> dict[str, Any]:
    sem = spec.semantics
    return {
        "arithmetic_mode": sem.arithmetic_mode,
        "short_circuit_mode": sem.short_circuit_mode,
        "evaluation_order": sem.evaluation_order,
        "scoping": sem.scoping,
        "type_coercion": sem.type_coercion,
        "operations": {
            name: {
                "arity": info.arity,
                "arg_types": list(info.arg_types),
                "return_type": info.return_type,
                "semantic_mode": info.semantic_mode,
            }
            for name, info in sorted(spec.builtins.items())
        },
    }


def pinned_seed(arithmetic: str, short_circuit: bool) -> LanguageSeed:
    return LanguageSeed(
        name="env",
        syntax_style="lisp",
        features=["arithmetic", "functions", "recursion", "short_circuit"],
        difficulty=1,
        arithmetic=arithmetic,
        short_circuit=short_circuit,
    )


def identity_core(spec: LanguageSpec, surface_profile: Mapping[str, Any]) -> dict[str, Any]:
    grammar_sha256 = sha256_text(spec.grammar)
    semantic_spec_sha256 = sha256_hex(semantic_projection(spec))
    surface_profile_sha256 = sha256_hex(dict(surface_profile))
    return {
        "env_schema_version": ENV_SCHEMA_VERSION,
        "generator_family_version": GENERATOR_FAMILY_VERSION,
        "generator_algorithm_version": GENERATOR_ALGORITHM_VERSION,
        "grammar_sha256": grammar_sha256,
        "semantic_spec_sha256": semantic_spec_sha256,
        "surface_profile_sha256": surface_profile_sha256,
        "runtime_semantics_version": RUNTIME_SEMANTICS_VERSION,
    }


def validate_identity_fields(record: Mapping[str, Any]) -> None:
    core = record.get("identity_core")
    if not isinstance(core, dict):
        raise ValidationError("identity_core must be an object")
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
        raise ValidationError(f"identity_core fields must equal {sorted(required)}")
    for field in ("grammar_sha256", "semantic_spec_sha256", "surface_profile_sha256"):
        value = core[field]
        if type(value) is not str or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValidationError(f"identity_core.{field} must be lowercase SHA-256 hex")
    if core["runtime_semantics_version"] != RUNTIME_SEMANTICS_VERSION:
        raise ValidationError("runtime_semantics_version does not match the running runtime")
    if record.get("surface_id") != core["surface_profile_sha256"]:
        raise ValidationError("surface_id must equal identity_core.surface_profile_sha256")


def build_environment(
    arithmetic: str,
    short_circuit: bool,
    surface_profile: Mapping[str, Any],
    derivation: dict[str, Any] | None = None,
) -> EnvironmentRecord:
    profile = SurfaceProfile.from_dict(surface_profile)
    seed = pinned_seed(arithmetic, short_circuit)
    spec = LanguageGenerator().generate(
        seed,
        spec_version="1.0.0",
        algorithm_version=GENERATOR_ALGORITHM_VERSION,
    )
    core = identity_core(spec, surface_profile)
    observable = sha256_hex({
        "grammar_sha256": core["grammar_sha256"],
        "semantic_spec_sha256": core["semantic_spec_sha256"],
        "surface_profile_sha256": core["surface_profile_sha256"],
    })
    environment_id = "env_" + sha256_hex(core)
    record = EnvironmentRecord(
        environment_id=environment_id,
        identity_core=core,
        observable_fingerprint=observable,
        surface_id=core["surface_profile_sha256"],
        semantic={"arithmetic": arithmetic, "short_circuit": short_circuit},
        surface_profile=dict(surface_profile),
        runtime={
            "language_id": spec.language_id,
            "spec_version": spec.spec_version,
            "algorithm_version": spec.algorithm_version,
            "grammar_sha256": core["grammar_sha256"],
        },
        derivation=derivation,
        status="validated",
    )
    validate_identity_fields(record.to_dict())
    return record


def get_language_spec(env: EnvironmentRecord) -> LanguageSpec:
    """Get the LanguageSpec for an environment record.
    
    This function reconstructs the LanguageSpec from the environment's
    semantic configuration and surface profile. It is used by the harness
    to execute programs through the production runtime.
    
    Args:
        env: EnvironmentRecord with valid identity
        
    Returns:
        LanguageSpec with grammar and semantics for the environment
    """
    semantic = env.semantic
    surface_profile = env.surface_profile
    
    profile = SurfaceProfile.from_dict(surface_profile)
    seed = pinned_seed(semantic["arithmetic"], semantic["short_circuit"])
    
    return LanguageGenerator().generate(
        seed,
        spec_version="1.0.0",
        algorithm_version=GENERATOR_ALGORITHM_VERSION,
    )
