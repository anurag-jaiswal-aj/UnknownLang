"""F2 surface translator and parser-boundary tests."""
import pytest

from src.execution.engine import ExecutionEngine
from src.language.generator import LanguageGenerator
from src.language.seed import LanguageSeed
from src.language.surface import SurfaceProfile, SurfaceTranslationError, to_canonical
from src.oracle.reference_evaluator import ReferenceEvaluator


@pytest.fixture
def language():
    return LanguageGenerator().generate(LanguageSeed(
        name="Surface", syntax_style="lisp", features=["functions"],
        difficulty=1, arithmetic="wraparound", short_circuit=True))


@pytest.fixture
def profile():
    return SurfaceProfile(
        keywords={"forge": "def", "fork": "if"},
        operators={"prax": "add", "zeph": "and", "rilo": "eq"},
        literals={"aye": "true", "nay": "false"},
    )


def test_keyword_prefix_is_one_user_identifier(profile):
    result = to_canonical("(forge ifx (a) a) (ifx 7)", profile)
    assert "ifx" not in result.canonical_text
    assert result.name_map["ifx"].startswith("_u")
    assert result.canonical_text.count(result.name_map["ifx"]) == 2


def test_generated_names_avoid_source_name_collisions(profile):
    result = to_canonical("(forge _u1 (x) (prax _u1 x))", profile)
    assert len(set(result.name_map.values())) == len(result.name_map)
    assert "_u1" in result.name_map
    assert result.name_map["_u1"] != "_u1"


@pytest.mark.parametrize("source", ["(prax 1 2)@", "(prax +1 2)", "(prax 1.0 2)", "(prax a-b 1)"])
def test_invalid_surface_lexemes_rejected(profile, source):
    with pytest.raises(SurfaceTranslationError):
        to_canonical(source, profile)


def test_surface_execution_uses_translator_on_production_and_reference(language, profile):
    source = "(forge ifx (a) a) (ifx 7)"
    production = ExecutionEngine().execute(source, language, surface_profile=profile)
    reference = ReferenceEvaluator().execute(source, language, surface_profile=profile)
    assert (production.status, production.value, type(production.value)) == ("success", 7, int)
    assert (reference.status, reference.value, type(reference.value)) == ("success", 7, int)


def test_surface_translation_is_deterministic(profile):
    source = "(forge f (x) (prax x 1)) (f 4)"
    a = to_canonical(source, profile)
    b = to_canonical(source, profile)
    assert a == b


def test_exact_surface_literals_and_operators_map(profile):
    result = to_canonical("(zeph aye nay)", profile)
    assert result.canonical_text == "(and true false)"


def test_whitespace_does_not_change_translation(profile):
    a = to_canonical("(prax 1 2)", profile)
    b = to_canonical(" ( prax\n 1\t2 ) ", profile)
    assert a == b
