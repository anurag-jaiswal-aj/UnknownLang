"""if metadata consistency (Wave 1C.16.1).

The design declares `if` as a conditional expression that evaluates only the selected branch,
independently of the boolean evaluation mode (short_circuit vs eager). The metadata should
reflect this: `if` always uses short-circuit mode, never eager.

This test verifies:
- `if` metadata is identical regardless of the `short_circuit` seed setting.
- The production and reference evaluators both implement lazy `if`.
- The eager short-circuit table in design.md applies to `and`/`or` only, not `if`.
"""
import pytest

from src.execution.engine import ExecutionEngine
from src.execution.iterative_evaluator import IterativeEvaluator
from src.language.generator import LanguageGenerator
from src.language.seed import LanguageSeed
from src.oracle.reference_evaluator import ReferenceEvaluator
from src.language.semantics import SemanticRegistry

SEEDS = {
    "short-circuit": LanguageSeed(name="IfSC", syntax_style="lisp", features=["functions"],
                                  difficulty=2, arithmetic="wraparound", short_circuit=True),
    "eager": LanguageSeed(name="IfEager", syntax_style="lisp", features=["functions"],
                          difficulty=2, arithmetic="wraparound", short_circuit=False),
}


def _spec(short_circuit):
    return SemanticRegistry().build_spec(SEEDS["short-circuit" if short_circuit else "eager"])


def _lang(short_circuit):
    return LanguageGenerator().generate(SEEDS["short-circuit" if short_circuit else "eager"])


class TestIfMetadataConsistency:
    @pytest.mark.parametrize("short_circuit", [True, False])
    def test_if_always_has_short_circuit_mode(self, short_circuit):
        spec = _spec(short_circuit)
        assert spec.operations["if"].semantic_mode == "short-circuit"

    @pytest.mark.parametrize("short_circuit", [True, False])
    def test_if_is_different_from_and_or(self, short_circuit):
        spec = _spec(short_circuit)
        assert spec.operations["if"].semantic_mode == "short-circuit"
        # and/or follow short_circuit mode
        expected_and_or = "short-circuit" if short_circuit else "eager"
        assert spec.operations["and"].semantic_mode == expected_and_or
        assert spec.operations["or"].semantic_mode == expected_and_or
        # if is always short-circuit, so it differs only when short_circuit=False
        if short_circuit:
            # when short_circuit=True, all modes are "short-circuit"
            assert spec.operations["if"].semantic_mode == expected_and_or
        else:
            assert spec.operations["if"].semantic_mode != expected_and_or

    @pytest.mark.parametrize("cls", [IterativeEvaluator, ReferenceEvaluator])
    @pytest.mark.parametrize("short_circuit", [True, False])
    def test_if_is_lazy_both_modes(self, cls, short_circuit):
        """if evaluates only the selected branch, regardless of boolean evaluation mode."""
        lang = _lang(short_circuit)
        ev = cls()
        # The selected branch runs, the other branch is never evaluated.
        # If the untaken branch raised an error, it would fail if evaluated.
        # Both branches being valid proves nothing was evaluated.
        program = "(if true 1 (div 1 0))\n(if false (mul 2 true) 3)"
        r = ev.execute(program, lang)
        assert (r.status, r.value) == ("success", 3)
        # The false branch (div 1 0) and the else branch (mul 2 true) are never evaluated.
        # If they were, the first would raise division by zero and the second would raise
        # a type error (bool used as int).
        assert r.error_message == ""

    @pytest.mark.parametrize("short_circuit", [True, False])
    def test_production_and_reference_agree_on_if(self, short_circuit):
        """Production and reference both implement lazy if, regardless of short_circuit mode."""
        lang = _lang(short_circuit)
        prod = ExecutionEngine().execute("(if true 1 (div 1 0))\n(if false 2 3)", lang)
        ref = ReferenceEvaluator().execute("(if true 1 (div 1 0))\n(if false 2 3)", lang)
        assert (prod.status, prod.value, prod.error_message) == \
            (ref.status, ref.value, ref.error_message)


class TestGeneratedSpecs:
    @pytest.mark.parametrize("short_circuit", [True, False])
    def test_spec_operations_dict_is_same_for_both_modes(self, short_circuit):
        spec = _spec(short_circuit)
        # The operations dict should be identical regardless of short_circuit mode.
        # This is true for if, but not for and/or which follow short_circuit.
        other = _spec(not short_circuit)
        # if metadata should be identical
        assert spec.operations["if"].arity == other.operations["if"].arity
        assert spec.operations["if"].arg_types == other.operations["if"].arg_types
        assert spec.operations["if"].return_type == other.operations["if"].return_type
        assert spec.operations["if"].semantic_mode == other.operations["if"].semantic_mode
        # and/or differ in semantic_mode
        assert spec.operations["and"].semantic_mode != other.operations["and"].semantic_mode
        assert spec.operations["or"].semantic_mode != other.operations["or"].semantic_mode
