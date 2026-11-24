"""Wave 2 generator validation tests."""
import pytest

from src.language.generator import LanguageGenerator, LanguageSpec
from src.language.seed import LanguageSeed, ValidationError


def seed(features=("arithmetic", "functions")):
    return LanguageSeed(
        name="GeneratorValidation", syntax_style="lisp", features=list(features),
        difficulty=1, arithmetic="wraparound", short_circuit=True)


def test_generator_rejects_unknown_features():
    with pytest.raises(ValidationError, match="Unsupported features"):
        LanguageGenerator().generate(seed(("functions", "not-implemented")))


def test_generated_spec_has_no_registry_conflicts():
    generator = LanguageGenerator()
    spec = generator.generate(seed())
    assert generator.detect_conflicts(spec, generator._semantic_registry) == []


def test_conflict_detection_reports_builtin_metadata_change():
    generator = LanguageGenerator()
    spec = generator.generate(seed())
    original = spec.builtins["add"]
    from src.language.semantics import OperationInfo
    mutated = dict(spec.builtins)
    mutated["add"] = OperationInfo(
        name=original.name,
        arity=1,
        arg_types=original.arg_types,
        return_type=original.return_type,
        semantic_mode=original.semantic_mode,
    )
    mutated_spec = LanguageSpec(
        version=spec.version,
        spec_version=spec.spec_version,
        algorithm_version=spec.algorithm_version,
        language_id=spec.language_id,
        seed=spec.seed,
        grammar=spec.grammar,
        semantics=spec.semantics,
        builtins=mutated,
    )
    conflicts = generator.detect_conflicts(mutated_spec, generator._semantic_registry)
    assert conflicts == ["builtin add.arity differs from registry"]
