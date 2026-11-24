"""Lexical scoping contract (Wave 1C.14, stage 6).

Contract (design.md semantics.scoping = "lexical", requirements.md interpreter requirement):
a function body can see ONLY its own parameters (and, by name, declared functions). A
variable bound in a caller is never visible to a callee. The language has no globals, no
nested definitions and no variable-binding form, so lexical scope is exactly the parameter
list.

The old recursive engine copied the caller's variables into the callee (an accidental
dynamic scope: it captured a definition-time environment and never read it). That was a
production behavior change in Wave 1C.14; these tests pin the intended behavior on ALL
THREE evaluators so neither the production path nor the oracle can drift back.

Every expected value below is derived by hand from the contract, not from evaluator output.
"""

import pytest

from src.execution.engine import ExecutionEngine
from src.execution.iterative_evaluator import IterativeEvaluator
from src.language.generator import LanguageGenerator
from src.language.seed import LanguageSeed
from src.oracle.reference_evaluator import ReferenceEvaluator

EVALUATORS = {
    "iterative": IterativeEvaluator,
    "facade": ExecutionEngine,
    "reference": ReferenceEvaluator,
}


@pytest.fixture(scope="module")
def lang():
    return LanguageGenerator().generate(LanguageSeed(
        name="ScopeLang", syntax_style="lisp", features=["recursion", "functions"],
        difficulty=2, arithmetic="wraparound", short_circuit=True))


@pytest.fixture(params=sorted(EVALUATORS))
def run(request, lang):
    evaluator = EVALUATORS[request.param]()
    return lambda program: evaluator.execute(program, lang)


# (id, program, expected value) -- derivations in the comments.
VALUE_CASES = [
    # g binds x=1; f(10) runs with its OWN x=10; afterwards g's x is still 1.  10 + 1 = 11
    ("callee_parameter_shadows_without_clobbering_caller",
     "(def f (x) x)\n(def g (x) (add (f 10) x))\n(g 1)", 11),
    # the call is the SECOND operand: g's y must still be 5 afterwards.  5 + f(1) = 5 + 1 = 6
    ("caller_variable_intact_after_call_as_second_operand",
     "(def f (x) x)\n(def g (y) (add y (f 1)))\n(g 5)", 6),
    # the call is the FIRST operand: f(1) + y = 1 + 5 = 6
    ("caller_variable_intact_after_call_as_first_operand",
     "(def f (x) x)\n(def g (y) (add (f 1) y))\n(g 5)", 6),
    # c(z)=2z ; b(y)=y+c(y)=3y ; a(x)=b(x+1)+x.  a(1) = b(2) + 1 = 6 + 1 = 7
    ("three_levels_each_restore_their_own_environment",
     "(def c (z) (mul z 2))\n(def b (y) (add y (c y)))\n(def a (x) (add (b (add x 1)) x))\n(a 1)", 7),
    # same parameter name x in f and g: f(1)=1+100=101, then + g's own x (1) = 102
    ("same_parameter_name_in_two_functions",
     "(def f (x) (add x 100))\n(def g (x) (add (f x) x))\n(g 1)", 102),
    # every recursive invocation has its own n: 4+3+2+1+0 = 10
    ("each_recursive_invocation_has_its_own_binding",
     "(def sum (n) (if (eq n 0) 0 (add n (sum (sub n 1)))))\n(sum 4)", 10),
    # a parameter may share a function's name: variables and functions are separate
    # namespaces, so (g 5) = 5 + 1 = 6
    ("parameter_named_like_a_function",
     "(def f (x) x)\n(def g (f) (add f 1))\n(g 5)", 6),
    # g refers to h, declared after g but before the call: g(4) = h(4) = 5
    ("function_declared_later_is_visible_at_call_time",
     "(def g (x) (h x))\n(def h (x) (add x 1))\n(g 4)", 5),
    # 7 is odd: even(7) -> odd(6) -> ... -> odd(0) = false
    ("mutual_recursion_keeps_bindings_separate",
     "(def ev (n) (if (eq n 0) true (od (sub n 1))))\n(def od (n) (if (eq n 0) false (ev (sub n 1))))\n(ev 7)",
     False),
]

# Programs whose ONLY problem is a variable that exists in a caller but not in the callee.
FREE_VARIABLE_CASES = [
    # f reads x; x is bound only in g (the caller). Dynamic scope would give 1 + 5 = 6.
    ("callee_cannot_read_caller_variable",
     "(def f (y) (add x y))\n(def g (x) (f 1))\n(g 5)", "x"),
    # two hops: h reads x bound only in g, with f in between
    ("callee_cannot_read_variable_two_frames_up",
     "(def h (y) (add x y))\n(def f (y) (h y))\n(def g (x) (f 1))\n(g 5)", "x"),
    # the caller's PARAMETER of the same name does not leak into a no-parameter callee
    ("nullary_callee_cannot_read_caller_parameter",
     "(def f () n)\n(def g (n) (f))\n(g 5)", "n"),
    # a free variable at top level has nothing to resolve to
    ("top_level_free_variable", "x", "x"),
]


class TestLexicalScoping:
    @pytest.mark.parametrize("name,program,expected", VALUE_CASES, ids=[c[0] for c in VALUE_CASES])
    def test_values(self, run, name, program, expected):
        result = run(program)
        assert result.status == "success", result.error_message
        assert result.value == expected
        assert type(result.value) is type(expected)

    @pytest.mark.parametrize("name,program,var", FREE_VARIABLE_CASES, ids=[c[0] for c in FREE_VARIABLE_CASES])
    def test_a_callee_cannot_see_its_callers_variables(self, run, name, program, var):
        result = run(program)
        assert result.status == "error"
        assert result.value is None
        assert f"Unknown identifier: {var}" in result.error_message

    def test_error_leaves_the_evaluator_usable(self, run):
        assert run("(def f (y) (add x y))\n(def g (x) (f 1))\n(g 5)").status == "error"
        good = run("(add 1 2)")
        assert (good.status, good.value) == ("success", 3)


class TestAllEvaluatorsAgree:
    """Not just 'each is right': the three implementations give the same answer."""

    @pytest.mark.parametrize("name,program,expected",
                             [(c[0], c[1], c[2]) for c in VALUE_CASES] +
                             [(c[0], c[1], None) for c in FREE_VARIABLE_CASES],
                             ids=[c[0] for c in VALUE_CASES] + [c[0] for c in FREE_VARIABLE_CASES])
    def test_identical_status_and_value(self, lang, name, program, expected):
        outcomes = {}
        for label, cls in EVALUATORS.items():
            r = cls().execute(program, lang)
            outcomes[label] = (r.status, r.value)
        assert len(set(outcomes.values())) == 1, outcomes
