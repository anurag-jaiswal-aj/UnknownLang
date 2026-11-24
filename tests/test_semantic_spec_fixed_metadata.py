"""Fixed semantic metadata on SemanticSpec (Wave 1C.15).

requirements.md Req. 6 criterion 3 requires the specification's semantics object to define
evaluation_order, scoping, arithmetic and type_coercion. Req. 5 criterion 6 and design.md
("Deferred Semantic Dimensions") defer the first, second and fourth as *configurable*
dimensions. The two are consistent: in the MVP they are recorded metadata with exactly one
supported value each, not options.
"""
import dataclasses

import pytest

from src.execution.iterative_evaluator import IterativeEvaluator
from src.language.generator import LanguageGenerator
from src.language.seed import LanguageSeed, ValidationError
from src.language.semantics import OperationInfo, SemanticRegistry, SemanticSpec
from src.oracle.reference_evaluator import ReferenceEvaluator

FIXED = {"evaluation_order": "left-to-right", "scoping": "lexical", "type_coercion": "strict"}


def _seed(mode="wraparound", sc=True):
    return LanguageSeed(name="MetaLang", syntax_style="lisp", features=["functions"],
                        difficulty=1, arithmetic=mode, short_circuit=sc)


def _spec(**kw):
    return SemanticSpec(arithmetic_mode="wraparound", short_circuit_mode=True, operations={}, **kw)


class TestFields:
    def test_fields_exist_as_str_with_fixed_defaults(self):
        fields = {f.name: f for f in dataclasses.fields(SemanticSpec)}
        for name, value in FIXED.items():
            assert name in fields
            assert fields[name].default == value
            assert getattr(_spec(), name) == value
            assert type(getattr(_spec(), name)) is str

    def test_legacy_positional_construction_still_works(self):
        spec = SemanticSpec("wraparound", True, {})
        assert spec.scoping == "lexical"

    def test_still_frozen(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            _spec().scoping = "dynamic"


class TestGeneratedSpecs:
    @pytest.mark.parametrize("mode", ["wraparound", "saturating", "error-on-overflow"])
    @pytest.mark.parametrize("sc", [True, False])
    def test_registry_populates_every_field(self, mode, sc):
        spec = SemanticRegistry().build_spec(_seed(mode, sc))
        for name, value in FIXED.items():
            assert getattr(spec, name) == value
        assert spec.arithmetic_mode == mode
        assert spec.short_circuit_mode is sc

    def test_generated_language_carries_fields(self):
        sem = LanguageGenerator().generate(_seed()).semantics
        assert {n: getattr(sem, n) for n in FIXED} == FIXED


class TestValidation:
    @pytest.mark.parametrize("name,bad", [
        ("evaluation_order", "right-to-left"),
        ("evaluation_order", ""),
        ("scoping", "dynamic"),
        ("scoping", "Lexical"),
        ("type_coercion", "loose"),
        ("type_coercion", None),
        ("scoping", 1),
    ])
    def test_unsupported_values_rejected(self, name, bad):
        with pytest.raises(ValidationError) as exc:
            _spec(**{name: bad})
        assert name in str(exc.value)

    def test_explicit_fixed_values_accepted(self):
        assert _spec(**FIXED).scoping == "lexical"

    def test_arithmetic_and_short_circuit_validation_unchanged(self):
        with pytest.raises(ValidationError):
            SemanticSpec(arithmetic_mode="bogus", short_circuit_mode=True, operations={})
        with pytest.raises(ValidationError):
            SemanticSpec(arithmetic_mode="wraparound", short_circuit_mode="yes", operations={})

    def test_seed_has_no_knob_for_fixed_dimensions(self):
        names = {f.name for f in dataclasses.fields(LanguageSeed)}
        assert not names & set(FIXED)


class TestBehaviorMatchesMetadata:
    """The recorded values describe what both evaluators actually do."""

    @pytest.mark.parametrize("cls", [IterativeEvaluator, ReferenceEvaluator])
    def test_left_to_right_evaluation(self, cls):
        lang = LanguageGenerator().generate(_seed())
        # Left operand fails with division by zero; right operand is an unknown identifier.
        left = cls().execute("(add (div 1 0) nope)", lang)
        right = cls().execute("(add nope (div 1 0))", lang)
        assert "Unknown identifier" not in left.error_message
        assert "Unknown identifier: nope" in right.error_message

    @pytest.mark.parametrize("cls", [IterativeEvaluator, ReferenceEvaluator])
    def test_lexical_scoping(self, cls):
        lang = LanguageGenerator().generate(_seed())
        r = cls().execute("(def f () x)\n(def g (x) (f))\n(g 1)", lang)
        assert r.status == "error" and "Unknown identifier: x" in r.error_message

    @pytest.mark.parametrize("cls", [IterativeEvaluator, ReferenceEvaluator])
    @pytest.mark.parametrize("program", ["(if 1 2 3)", "(and 1 true)", "(or false 0)", "(not 0)"])
    def test_no_truthiness_coercion(self, cls, program):
        """Ints are never coerced to booleans (design.md: strict boolean mode)."""
        lang = LanguageGenerator().generate(_seed())
        assert cls().execute(program, lang).status == "error"

    @pytest.mark.xfail(strict=True, reason=(
        "KNOWN GAP (Wave 1C.15 finding, awaiting approval): both evaluators treat Python bool "
        "as int, so booleans are coerced to integers in arithmetic and eq. type_coercion=strict "
        "(design.md) says this should be a type error. Fixing it is a behavior change outside "
        "this milestone. Remove this xfail when it is fixed."))
    @pytest.mark.parametrize("cls", [IterativeEvaluator, ReferenceEvaluator])
    @pytest.mark.parametrize("program", ["(add 1 true)", "(mul true true)", "(div 4 true)"])
    def test_no_bool_to_int_coercion_in_arithmetic(self, cls, program):
        lang = LanguageGenerator().generate(_seed())
        assert cls().execute(program, lang).status == "error"

    @pytest.mark.xfail(strict=True, reason="KNOWN GAP: eq compares bool and int by Python value; see above.")
    @pytest.mark.parametrize("cls", [IterativeEvaluator, ReferenceEvaluator])
    def test_eq_does_not_coerce_bool_to_int(self, cls):
        lang = LanguageGenerator().generate(_seed())
        r = cls().execute("(eq 1 true)", lang)
        assert not (r.status == "success" and r.value is True)
