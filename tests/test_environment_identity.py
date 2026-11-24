"""Wave 2 environment identity and strict canonicalization tests."""
import pytest

from src.benchmark.canonical import canonical_bytes, canonical_json, sha256_hex
from src.benchmark.environments import build_environment
from src.execution.types import RUNTIME_SEMANTICS_VERSION
from src.language.seed import ValidationError

PROFILE = {
    "profile_schema_version": 1,
    "keywords": {"forge": "def", "fork": "if"},
    "operators": {"prax": "add", "zeph": "and", "rilo": "eq"},
    "literals": {"aye": "true", "nay": "false"},
}


def test_runtime_version_is_two():
    assert RUNTIME_SEMANTICS_VERSION == 2, "Runtime version 2 reflects F1 correction"


def test_runtime_version_change_changes_environment_id():
    """Verify that changing runtime_semantics_version produces a different environment ID.

    This test uses canonical_json to construct identity cores with different versions
    while keeping all other fields identical, then verifies the SHA256 hash changes.
    """
    core_v1 = {
        "env_schema_version": 1,
        "generator_family_version": "f1",
        "generator_algorithm_version": "1.0.0",
        "grammar_sha256": "a" * 64,
        "semantic_spec_sha256": "b" * 64,
        "surface_profile_sha256": "c" * 64,
        "runtime_semantics_version": 1,
    }
    core_v2 = {
        **core_v1,
        "runtime_semantics_version": 2,
    }
    hash_v1 = sha256_hex(core_v1)
    hash_v2 = sha256_hex(core_v2)
    assert hash_v1 != hash_v2, "SHA256 of identity_core must differ when runtime_semantics_version changes"


def test_identity_recomputes_from_one_core():
    record = build_environment("wraparound", True, PROFILE)
    assert record.environment_id == "env_" + sha256_hex(record.identity_core)
    assert record.surface_id == record.identity_core["surface_profile_sha256"]
    assert record.identity_core["runtime_semantics_version"] == RUNTIME_SEMANTICS_VERSION


def test_identity_changes_for_behavior_and_generator_inputs():
    base = build_environment("wraparound", True, PROFILE)
    eager = build_environment("wraparound", False, PROFILE)
    saturating = build_environment("saturating", True, PROFILE)
    altered_profile = {**PROFILE, "operators": {**PROFILE["operators"], "prax": "sub"}}
    remapped = build_environment("wraparound", True, altered_profile)
    assert len({base.environment_id, eager.environment_id, saturating.environment_id, remapped.environment_id}) == 4
    assert base.observable_fingerprint != eager.observable_fingerprint
    assert base.observable_fingerprint != remapped.observable_fingerprint


def test_identity_stable_across_mapping_order():
    reordered = {
        "literals": {"nay": "false", "aye": "true"},
        "operators": {"rilo": "eq", "zeph": "and", "prax": "add"},
        "keywords": {"fork": "if", "forge": "def"},
        "profile_schema_version": 1,
    }
    assert build_environment("wraparound", True, PROFILE).environment_id == \
        build_environment("wraparound", True, reordered).environment_id


def test_strict_canonicalization_rejects_ambiguous_values():
    assert canonical_json({"b": 2, "a": 1}) == '{"a":1,"b":2}'
    assert canonical_bytes([True, None, "é"]).startswith(b"[true,null,\"")
    with pytest.raises(TypeError):
        canonical_json({"value": 1.5})
    with pytest.raises(TypeError):
        canonical_json({1: "not-a-string-key"})
    with pytest.raises(TypeError):
        canonical_json({"value": object()})


def test_environment_record_rejects_identity_core_mismatch():
    record = build_environment("wraparound", True, PROFILE).to_dict()
    record["surface_id"] = "0" * 64
    from src.benchmark.environments import validate_identity_fields
    with pytest.raises(ValidationError):
        validate_identity_fields(record)
