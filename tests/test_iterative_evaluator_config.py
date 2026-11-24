"""Constructor configuration of IterativeEvaluator (Wave 1C.14, stage 2).

    IterativeEvaluator(*, max_steps=None, max_ast_depth=None, max_call_depth=None)

Contract: ``None`` means the default (100_000 / 1_000 / 100); values are ``int >= 0``;
limits are resolved once, apply to every ``execute`` call, and never leak state between
calls. Every behavior below is checked through the PUBLIC ``execute`` method, using
program-level facts derived by hand from the semantic step / depth / call-depth contract:

  (add 1 2)           3 steps (call + two literals), depth 2, no user calls
  (add (add 1 1) 2)   depth 3
  recur(k)            k + 1 simultaneously active invocations
"""

import pytest

from src.execution.iterative_evaluator import IterativeEvaluator
from src.language.generator import LanguageGenerator
from src.language.seed import LanguageSeed

RECUR = "(def recur (n)\n  (if (eq n 0)\n      0\n      (recur (sub n 1))))\n"
LIMIT_NAMES = ["max_steps", "max_ast_depth", "max_call_depth"]


@pytest.fixture(scope="module")
def lang():
    return LanguageGenerator().generate(LanguageSeed(
        name="ConfigLang", syntax_style="lisp", features=["arithmetic", "functions"],
        difficulty=1, arithmetic="wraparound", short_circuit=True))


def nested(n: int) -> str:
    """n calls around one literal: depth n + 1."""
    return "(add 1 " * n + "1" + ")" * n


class TestDefaults:
    def test_no_arguments_still_works(self, lang):
        result = IterativeEvaluator().execute("(add 1 2)", lang)
        assert (result.status, result.value) == ("success", 3)

    def test_explicit_none_equals_default(self, lang):
        a = IterativeEvaluator()._new_context(lang)
        b = IterativeEvaluator(max_steps=None, max_ast_depth=None, max_call_depth=None)._new_context(lang)
        assert (a.max_steps, a.max_ast_depth, a.max_call_depth) == (100_000, 1_000, 100)
        assert (b.max_steps, b.max_ast_depth, b.max_call_depth) == (100_000, 1_000, 100)

    def test_default_ast_depth_boundary_through_execute(self, lang):
        ev = IterativeEvaluator()
        assert ev.execute(nested(999), lang).status == "success"                  # depth 1000
        assert ev.execute(nested(1000), lang).status == "ast_depth_exceeded"      # depth 1001

    def test_default_call_depth_boundary_through_execute(self, lang):
        ev = IterativeEvaluator()
        assert ev.execute(RECUR + "(recur 99)", lang).status == "success"                  # 100 active
        assert ev.execute(RECUR + "(recur 100)", lang).status == "recursion_limit_exceeded"  # 101 active

    def test_arguments_are_keyword_only(self):
        with pytest.raises(TypeError):
            IterativeEvaluator(5)  # type: ignore[misc]


class TestEachLimitIsAppliedThroughExecute:
    def test_max_steps(self, lang):
        assert IterativeEvaluator(max_steps=3).execute("(add 1 2)", lang).status == "success"
        below = IterativeEvaluator(max_steps=2).execute("(add 1 2)", lang)
        assert below.status == "step_limit_exceeded"

    def test_max_ast_depth(self, lang):
        ev = IterativeEvaluator(max_ast_depth=2)
        assert ev.execute("(add 1 2)", lang).status == "success"
        assert ev.execute("(add (add 1 1) 2)", lang).status == "ast_depth_exceeded"

    def test_max_call_depth(self, lang):
        ev = IterativeEvaluator(max_call_depth=5)
        assert ev.execute(RECUR + "(recur 4)", lang).status == "success"                   # 5 active
        assert ev.execute(RECUR + "(recur 5)", lang).status == "recursion_limit_exceeded"  # 6 active

    def test_a_limit_can_be_raised_above_its_default(self, lang):
        deep = IterativeEvaluator(max_ast_depth=2_000).execute(nested(1500), lang)
        assert (deep.status, deep.value) == ("success", 1501)
        assert IterativeEvaluator(max_call_depth=150).execute(RECUR + "(recur 120)", lang).status == "success"
        assert IterativeEvaluator(max_steps=10 ** 9).execute("(add 1 2)", lang).value == 3

    @pytest.mark.parametrize("kwargs,ok_prog,bad_prog,bad_status", [
        ({"max_steps": 3}, "(add 1 2)", "(add (add 1 1) 2)", "step_limit_exceeded"),
        ({"max_ast_depth": 2}, "(add 1 2)", "(add (add 1 1) 2)", "ast_depth_exceeded"),
    ])
    def test_configuring_one_limit_leaves_the_others_at_default(self, lang, kwargs, ok_prog, bad_prog, bad_status):
        ev = IterativeEvaluator(**kwargs)
        assert ev.execute(ok_prog, lang).status == "success"
        assert ev.execute(bad_prog, lang).status == bad_status
        ctx = ev._new_context(lang)
        defaults = {"max_steps": 100_000, "max_ast_depth": 1_000, "max_call_depth": 100}
        for name, default in defaults.items():
            assert getattr(ctx, name) == kwargs.get(name, default)

    def test_zero_is_a_real_limit(self, lang):
        assert IterativeEvaluator(max_steps=0).execute("1", lang).status == "step_limit_exceeded"
        assert IterativeEvaluator(max_ast_depth=0).execute("1", lang).status == "ast_depth_exceeded"
        assert IterativeEvaluator(max_call_depth=0).execute("(def f (x) x)\n(f 1)", lang).status == "recursion_limit_exceeded"
        # ... and an empty program needs none of them
        empty = IterativeEvaluator(max_steps=0, max_ast_depth=0, max_call_depth=0).execute("", lang)
        assert (empty.status, empty.value) == ("success", None)


class TestValidation:
    @pytest.mark.parametrize("name", LIMIT_NAMES)
    @pytest.mark.parametrize("bad", [True, False, 1.0, 2.5, "5", [1], (1,), b"1"],
                             ids=["True", "False", "float1", "float2.5", "str", "list", "tuple", "bytes"])
    def test_non_int_is_a_type_error_naming_the_parameter(self, name, bad):
        with pytest.raises(TypeError, match=name):
            IterativeEvaluator(**{name: bad})

    @pytest.mark.parametrize("name", LIMIT_NAMES)
    @pytest.mark.parametrize("bad", [-1, -100])
    def test_negative_is_a_value_error_naming_the_parameter(self, name, bad):
        with pytest.raises(ValueError, match=name):
            IterativeEvaluator(**{name: bad})

    @pytest.mark.parametrize("name", LIMIT_NAMES)
    def test_boundary_values_are_accepted(self, name):
        IterativeEvaluator(**{name: 0})
        IterativeEvaluator(**{name: 1})
        IterativeEvaluator(**{name: 10 ** 12})

    def test_unknown_keyword_is_rejected(self):
        with pytest.raises(TypeError):
            IterativeEvaluator(max_output_bytes=10)  # type: ignore[call-arg]

    def test_one_invalid_value_among_valid_ones_still_raises(self):
        with pytest.raises(ValueError):
            IterativeEvaluator(max_steps=10, max_ast_depth=-1)


class TestPerCallIsolationAndPrecedence:
    def test_each_execute_gets_a_fresh_context(self, lang):
        ev = IterativeEvaluator(max_steps=3)
        assert ev.execute("(add 1 2)", lang).status == "success"
        assert ev.execute("(add 1 2)", lang).status == "success"          # steps did not accumulate
        assert ev._new_context(lang) is not ev._new_context(lang)
        assert ev._new_context(lang).steps == 0

    def test_a_failed_run_does_not_poison_the_next_one(self, lang):
        # Budget 30 steps. nested(n) costs 2n + 1 steps (n calls, n literals, 1 final literal):
        # nested(14) = 29 fits, nested(15) = 31 does not. recur(5) with call depth 2 is
        # rejected after ~18 steps, so the call-depth limit triggers before the step limit.
        ev = IterativeEvaluator(max_steps=30, max_call_depth=2)
        assert ev.execute(RECUR + "(recur 5)", lang).status == "recursion_limit_exceeded"
        assert ev.execute("(add 1 2)", lang).value == 3
        assert ev.execute(nested(15), lang).status == "step_limit_exceeded"
        fits = ev.execute(nested(14), lang)
        assert (fits.status, fits.value) == ("success", 15)
        assert ev.execute(RECUR + "(recur 5)", lang).status == "recursion_limit_exceeded"

    def test_limits_are_not_mutated_by_execution(self, lang):
        ev = IterativeEvaluator(max_steps=3, max_ast_depth=7, max_call_depth=9)
        ev.execute("(add 1 2)", lang)
        ev.execute(RECUR + "(recur 50)", lang)
        ctx = ev._new_context(lang)
        assert (ctx.max_steps, ctx.max_ast_depth, ctx.max_call_depth) == (3, 7, 9)

    def test_two_evaluators_do_not_share_limits(self, lang):
        strict, lenient = IterativeEvaluator(max_steps=2), IterativeEvaluator(max_steps=3)
        assert strict.execute("(add 1 2)", lang).status == "step_limit_exceeded"
        assert lenient.execute("(add 1 2)", lang).status == "success"
        assert strict.execute("(add 1 2)", lang).status == "step_limit_exceeded"

    def test_precedence_per_call_over_constructor_over_default(self, lang):
        ev = IterativeEvaluator(max_steps=3)
        assert ev._new_context(lang).max_steps == 3                       # constructor beats default
        assert ev._new_context(lang, max_steps=7).max_steps == 7          # per-call beats constructor
        assert ev._new_context(lang, max_steps=None).max_steps == 3       # None falls back to constructor
        assert IterativeEvaluator()._new_context(lang, max_steps=None).max_steps == 100_000

    def test_static_depth_check_uses_the_configured_limit_before_any_step(self, lang):
        ev = IterativeEvaluator(max_ast_depth=2, max_steps=0)
        # Depth is validated first, so the status is ast_depth_exceeded even though the
        # step budget (0) would also reject the first expression.
        assert ev.execute("(add (add 1 1) 2)", lang).status == "ast_depth_exceeded"
