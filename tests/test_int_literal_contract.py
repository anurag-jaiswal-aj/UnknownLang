"""Signed 64-bit integer literal contract (Wave 1C.15).

Contract: an integer literal is valid iff MIN_INT64 <= value <= MAX_INT64. An invalid
literal is rejected statically, after parsing and before any evaluation, with result status
"error" and a message beginning "Integer literal out of range". The rule is independent of
the arithmetic mode (modes govern arithmetic results, never literal validity) and applies
wherever the literal appears, including function bodies that are never called and untaken
``if`` branches. Both evaluators implement it separately and must agree.

Bounds are written out as literal digits (not imported) so the tests do not trust the
constants they check.
"""
import pytest

from src.execution.engine import ExecutionEngine
from src.execution.iterative_evaluator import IterativeEvaluator
from src.language.generator import LanguageGenerator
from src.language.seed import LanguageSeed
from src.oracle.reference_evaluator import ReferenceEvaluator

MIN_S = "-9223372036854775808"
MAX_S = "9223372036854775807"
BELOW_MIN_S = "-9223372036854775809"
ABOVE_MAX_S = "9223372036854775808"
MIN_V = -(2**63)
MAX_V = 2**63 - 1

EVALUATORS = {"iterative": IterativeEvaluator, "facade": ExecutionEngine, "reference": ReferenceEvaluator}
MODES = ["wraparound", "saturating", "error-on-overflow"]


def _lang(mode: str):
    return LanguageGenerator().generate(LanguageSeed(
        name="IntLang", syntax_style="lisp", features=["recursion", "functions"],
        difficulty=2, arithmetic=mode, short_circuit=True))


@pytest.fixture(params=sorted(EVALUATORS))
def evaluator(request):
    return EVALUATORS[request.param]()


@pytest.fixture(params=MODES)
def mode(request):
    return request.param


class TestBoundaries:
    def test_int64_max_accepted(self, evaluator, mode):
        r = evaluator.execute(MAX_S, _lang(mode))
        assert (r.status, r.value) == ("success", MAX_V)

    def test_int64_min_accepted(self, evaluator, mode):
        r = evaluator.execute(MIN_S, _lang(mode))
        assert (r.status, r.value) == ("success", MIN_V)

    @pytest.mark.parametrize("lit", [ABOVE_MAX_S, BELOW_MIN_S, "99999999999999999999999999", "-99999999999999999999999999"])
    def test_out_of_range_rejected(self, evaluator, mode, lit):
        r = evaluator.execute(lit, _lang(mode))
        assert r.status == "error"
        assert r.error_message.startswith("Integer literal out of range: " + lit)

    def test_leading_zeros_do_not_change_value(self, evaluator):
        lang = _lang("wraparound")
        assert evaluator.execute("000" + MAX_S, lang).value == MAX_V
        assert evaluator.execute("0" + ABOVE_MAX_S, lang).status == "error"

    def test_negative_zero_and_small_negatives_unchanged(self, evaluator):
        lang = _lang("wraparound")
        assert evaluator.execute("-0", lang).value == 0
        assert evaluator.execute("(add -5 -7)", lang).value == -12


class TestPositions:
    """Rejection must not depend on where the literal sits or whether it would run."""

    @pytest.mark.parametrize("program", [
        f"(add 1 {ABOVE_MAX_S})",
        f"(add {BELOW_MIN_S} 1)",
        f"(add 1 (mul 2 (sub 3 {ABOVE_MAX_S})))",
        f"(if true 1 {ABOVE_MAX_S})",                       # untaken branch
        f"(if false {BELOW_MIN_S} 1)",                       # untaken branch
        f"(and false (eq {ABOVE_MAX_S} 1))",                 # short-circuited operand
        f"(def f (x) (add x {ABOVE_MAX_S}))\n(f 1)",         # function body, called
        f"(def f (x) (add x {ABOVE_MAX_S}))\n1",             # function body, never called
        f"1\n{ABOVE_MAX_S}",                                 # later top-level expression
        f"(def g (x) x)\n(g {BELOW_MIN_S})",                 # call argument
    ])
    def test_rejected_everywhere(self, evaluator, mode, program):
        r = evaluator.execute(program, _lang(mode))
        assert r.status == "error", program
        assert "Integer literal out of range" in r.error_message

    def test_nothing_evaluated_before_rejection(self, evaluator):
        """Rejection happens before evaluation: an earlier failing expression must not run first.

        (div 1 0) fails with a division error if it is evaluated, so the literal message proves
        the literal check ran before any expression was evaluated.
        """
        r = evaluator.execute(f"(div 1 0)\n{ABOVE_MAX_S}", _lang("wraparound"))
        assert r.status == "error"
        assert r.error_message.startswith("Integer literal out of range")
        assert r.output == ""

    def test_boundary_literals_accepted_in_function_bodies(self, evaluator):
        r = evaluator.execute(f"(def hi () {MAX_S})\n(def lo () {MIN_S})\n(sub (hi) (lo))", _lang("saturating"))
        assert (r.status, r.value) == ("success", MAX_V)  # 2**64 - 1 saturates to MAX


class TestDeepPrograms:
    def test_literal_check_does_not_recurse_on_deep_programs(self):
        """The production check must not use Python recursion (regression: Tree.scan_values)."""
        depth = 1500
        lang = _lang("wraparound")
        ev = IterativeEvaluator(max_ast_depth=2000)
        ok = ev.execute("(add 1 " * depth + "1" + ")" * depth, lang)
        assert (ok.status, ok.value) == ("success", depth + 1)
        bad = ev.execute("(add 1 " * depth + ABOVE_MAX_S + ")" * depth, lang)
        assert bad.status == "error" and "Integer literal out of range" in bad.error_message


class TestParityAndModes:
    @pytest.mark.parametrize("program", [ABOVE_MAX_S, BELOW_MIN_S, f"(add 1 {ABOVE_MAX_S})",
                                         f"(def f (x) {ABOVE_MAX_S})\n1", MAX_S, MIN_S])
    def test_production_and_reference_agree_exactly(self, mode, program):
        lang = _lang(mode)
        prod = IterativeEvaluator().execute(program, lang)
        ref = ReferenceEvaluator().execute(program, lang)
        assert (prod.status, prod.value, prod.error_message) == (ref.status, ref.value, ref.error_message)

    def test_error_message_is_documented_form(self, evaluator):
        r = evaluator.execute(ABOVE_MAX_S, _lang("wraparound"))
        assert r.error_message == (
            f"Integer literal out of range: {ABOVE_MAX_S} "
            f"(must be between {MIN_S} and {MAX_S})"
        )

    def test_arithmetic_modes_still_govern_arithmetic(self, evaluator):
        """Valid literals, overflowing arithmetic: each mode keeps its own behavior."""
        add = f"(add {MAX_S} 1)"
        assert evaluator.execute(add, _lang("wraparound")).value == MIN_V
        assert evaluator.execute(add, _lang("saturating")).value == MAX_V
        r = evaluator.execute(add, _lang("error-on-overflow"))
        assert r.status == "error"
        assert "Integer literal out of range" not in r.error_message
        sub = f"(sub {MIN_S} 1)"
        assert evaluator.execute(sub, _lang("wraparound")).value == MAX_V
        assert evaluator.execute(sub, _lang("saturating")).value == MIN_V
        assert evaluator.execute(sub, _lang("error-on-overflow")).status == "error"
