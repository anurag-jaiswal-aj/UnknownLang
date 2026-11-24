"""Resource-limit tests for IterativeEvaluator (Wave 1C.13.1 contract).

Contract under test
-------------------
AST depth (static, before execution; consumes no steps)
  * Expression nodes are ``literal``, ``call`` and ``if_expr``. Every independent
    root (each top-level expression and each ``def`` body, called or not) is at
    depth 1; each child expression is one deeper. Grammar wrappers add nothing.
  * ``max_ast_depth`` is accepted, ``max_ast_depth + 1`` is rejected with
    ``ast_depth_exceeded``. Unselected IF branches and short-circuit operands count.

Execution steps (runtime)
  * Exactly one step is charged per expression node (literal, call, if_expr)
    actually evaluated, before it is evaluated. A node that then fails still cost
    its step. Unselected IF branches and short-circuited operands cost nothing.
  * Function entry/return, argument passing, builtin dispatch, wrappers and
    ``def`` declarations cost nothing.
  * ``max_steps`` charged nodes succeed; the next attempted node raises
    ``step_limit_exceeded``.

Call depth (runtime): active user-function invocations; 100 allowed, 101 rejected.

Every expected step count below is derived by hand from this contract and written
next to the program as the list of nodes evaluated. None is a frame count.
"""

import inspect
import sys

import pytest

from src.execution.iterative_evaluator import IterativeEvaluator
from src.language.generator import LanguageGenerator
from src.language.seed import LanguageSeed


# ============================================================================
# HELPER: run the PRODUCTION path with explicit limits
# ============================================================================

def run_limited(evaluator, program_text, language_spec, max_steps=None, max_ast_depth=None,
                max_call_depth=None):
    """Parse, then run through ``IterativeEvaluator._run`` with explicit limits.

    ``_run`` is exactly what ``execute()`` calls (static validation, frame loop,
    error translation). Nothing is re-implemented here. Returns
    ``(result, context)`` so tests can inspect ``context.steps`` and cleanup state.
    """
    tree = evaluator._get_parser(language_spec.grammar).parse(program_text)
    context = evaluator._new_context(
        language_spec,
        max_steps=max_steps,
        max_ast_depth=max_ast_depth,
        max_call_depth=max_call_depth,
    )
    return evaluator._run(tree, context, language_spec), context


def _lang(short_circuit=True, arithmetic="wraparound"):
    return LanguageGenerator().generate(LanguageSeed(
        name="ResourceLimitLang",
        syntax_style="lisp",
        features=["arithmetic", "functions"],
        difficulty=1,
        arithmetic=arithmetic,
        short_circuit=short_circuit,
    ))


@pytest.fixture
def evaluator():
    """Create an IterativeEvaluator instance."""
    return IterativeEvaluator()


@pytest.fixture
def test_lang():
    """Short-circuit language with arithmetic and functions."""
    return _lang(short_circuit=True)


@pytest.fixture
def eager_lang():
    """Eager-boolean language with arithmetic and functions."""
    return _lang(short_circuit=False)


# ============================================================================
# STEP LIMIT TESTS
# ============================================================================

# (id, program, lang fixture name, nodes evaluated, expected steps, expected final status)
# "nodes evaluated" is the independent derivation: one entry per literal/call/if_expr
# node that actually runs. Skipped nodes are listed so the exclusion is explicit.
STEP_CASES = [
    ("literal", "1", "test_lang",
     "literal(1)", 1, "success"),
    ("variable_lookup_via_body", "(def id (x) x)\n(id 42)", "test_lang",
     "call(id), literal(42), body literal(x)", 3, "success"),
    ("builtin_call", "(add 1 2)", "test_lang",
     "call(add), literal(1), literal(2)", 3, "success"),
    ("nested_builtin", "(add (add 1 1) 2)", "test_lang",
     "call(add), call(add), 1, 1, 2", 5, "success"),
    ("nested_builtin_both_sides", "(add (add 1 1) (add 2 2))", "test_lang",
     "3 calls + 4 literals", 7, "success"),
    ("if_selected_then_skips_else", "(if true 1 (add 2 3))", "test_lang",
     "if, true, 1. SKIPPED: call(add), 2, 3", 3, "success"),
    ("if_selected_else", "(if false 1 (add 2 3))", "test_lang",
     "if, false, call(add), 2, 3. SKIPPED: 1", 5, "success"),
    ("user_function_with_body_call", "(def inc (x) (add x 1))\n(inc 5)", "test_lang",
     "call(inc), 5, body call(add), x, 1", 5, "success"),
    ("short_circuit_and_skips_rhs", "(and false (div 1 0))", "test_lang",
     "call(and), false. SKIPPED: call(div), 1, 0", 2, "success"),
    ("short_circuit_and_evaluates_rhs", "(and true false)", "test_lang",
     "call(and), true, false", 3, "success"),
    ("short_circuit_or_skips_rhs", "(or true (div 1 0))", "test_lang",
     "call(or), true. SKIPPED: call(div), 1, 0", 2, "success"),
    ("short_circuit_or_evaluates_rhs", "(or false true)", "test_lang",
     "call(or), false, true", 3, "success"),
    ("eager_and_evaluates_both_then_fails", "(and false (div 1 0))", "eager_lang",
     "call(and), false, call(div), 1, 0 then div raises", 5, "error"),
    ("eager_or_evaluates_both_then_fails", "(or true (div 1 0))", "eager_lang",
     "call(or), true, call(div), 1, 0 then div raises", 5, "error"),
    ("eager_and_no_error", "(and false true)", "eager_lang",
     "call(and), false, true", 3, "success"),
    ("failed_builtin_still_charged", "(div 1 0)", "test_lang",
     "call(div), 1, 0 then raises", 3, "error"),
    ("undefined_variable_charged", "x", "test_lang",
     "literal(x) then lookup raises", 1, "error"),
]


def _case_ids():
    return [c[0] for c in STEP_CASES]


class TestSemanticStepCounts:
    """Exact semantic step counts, with the success/failure boundary for each."""

    @pytest.mark.parametrize("case", STEP_CASES, ids=_case_ids())
    def test_exact_count_with_ample_budget(self, evaluator, request, case):
        _id, program, lang_name, _nodes, steps, status = case
        lang = request.getfixturevalue(lang_name)
        result, ctx = run_limited(evaluator, program, lang)
        assert result.status == status, result.error_message
        assert ctx.steps == steps

    @pytest.mark.parametrize(
        "case", [c for c in STEP_CASES if c[5] == "success"],
        ids=[c[0] for c in STEP_CASES if c[5] == "success"],
    )
    def test_boundary_exactly_max_steps_succeeds_and_one_less_fails(self, evaluator, request, case):
        """max_steps == N succeeds; max_steps == N-1 rejects the Nth attempted node."""
        _id, program, lang_name, _nodes, steps, _status = case
        lang = request.getfixturevalue(lang_name)

        at, ctx_at = run_limited(evaluator, program, lang, max_steps=steps)
        assert at.status == "success"
        assert ctx_at.steps == steps

        below, ctx_below = run_limited(evaluator, program, lang, max_steps=steps - 1)
        assert below.status == "step_limit_exceeded"
        # The rejected attempt is not charged: exactly max_steps were charged.
        assert ctx_below.steps == steps - 1

    @pytest.mark.parametrize(
        "case", [c for c in STEP_CASES if c[5] == "error"],
        ids=[c[0] for c in STEP_CASES if c[5] == "error"],
    )
    def test_boundary_for_programs_that_fail(self, evaluator, request, case):
        """A failing program charged N steps: budget N reports the language error,
        budget N-1 reports step_limit_exceeded before the failing node is reached."""
        _id, program, lang_name, _nodes, steps, _status = case
        lang = request.getfixturevalue(lang_name)

        at, ctx_at = run_limited(evaluator, program, lang, max_steps=steps)
        assert at.status == "error"
        assert ctx_at.steps == steps

        below, _ = run_limited(evaluator, program, lang, max_steps=steps - 1)
        assert below.status == "step_limit_exceeded"

    def test_zero_budget_rejects_first_expression_before_evaluating(self, evaluator, test_lang):
        result, ctx = run_limited(evaluator, "(add 1 2)", test_lang, max_steps=0)
        assert result.status == "step_limit_exceeded"
        assert ctx.steps == 0

    def test_def_declarations_cost_nothing(self, evaluator, test_lang):
        """Declarations are not expressions: three defs + a literal = 1 step."""
        program = "(def a (x) x)\n(def b (y) (add y 1))\n(def c () 1)\n7"
        result, ctx = run_limited(evaluator, program, test_lang)
        assert result.status == "success"
        assert result.value == 7
        assert ctx.steps == 1

    def test_multiple_top_level_expressions_each_charged(self, evaluator, test_lang):
        """Two roots: (add 1 2) = 3 nodes, then literal 9 = 1 node; value of the last root."""
        result, ctx = run_limited(evaluator, "(add 1 2)\n9", test_lang)
        assert result.status == "success"
        assert result.value == 9
        assert ctx.steps == 4

    def test_recursive_function_step_cost(self, evaluator, test_lang):
        """(recur 2) with  (def recur (n) (if (eq n 0) 0 (recur (sub n 1)))).

        Hand derivation (one step per node evaluated):
          top-level call(recur) + arg literal(2)                          = 2
          body at n=2: if, call(eq), n, 0, call(recur), call(sub), n, 1   = 8
          body at n=1: same shape                                          = 8
          body at n=0: if, call(eq), n, 0, then-literal(0)                 = 5
          (the recursive call(recur) and its arg are counted inside the
           body that evaluates them)
          total                                                            = 23
        """
        program = "(def recur (n)\n  (if (eq n 0)\n      0\n      (recur (sub n 1))))\n(recur 2)"
        result, ctx = run_limited(evaluator, program, test_lang)
        assert result.status == "success"
        assert result.value == 0
        assert ctx.steps == 23

        at, _ = run_limited(evaluator, program, test_lang, max_steps=23)
        assert at.status == "success"
        below, ctx_below = run_limited(evaluator, program, test_lang, max_steps=22)
        assert below.status == "step_limit_exceeded"
        assert ctx_below.steps == 22

    def test_step_count_independent_of_frame_structure(self, evaluator, test_lang):
        """A user-function call costs call + args + body nodes, regardless of the
        extra frames (entry, restore marker, argument bookkeeping) used internally."""
        direct, c1 = run_limited(evaluator, "(add 5 1)", test_lang)
        via_fn, c2 = run_limited(evaluator, "(def inc (x) (add x 1))\n(inc 5)", test_lang)
        assert direct.value == via_fn.value == 6
        assert c1.steps == 3      # call, 5, 1
        assert c2.steps == 5      # call(inc), 5, call(add), x, 1

    def test_independent_execution_after_step_limit(self, evaluator, test_lang):
        """A step-limit failure leaves no state behind for the next run."""
        r1, _ = run_limited(evaluator, "(add 1 2)", test_lang, max_steps=2)
        assert r1.status == "step_limit_exceeded"
        r2, ctx = run_limited(evaluator, "(add 3 4)", test_lang, max_steps=3)
        assert r2.status == "success"
        assert r2.value == 7
        assert ctx.steps == 3

    def test_static_depth_rejection_consumes_no_steps(self, evaluator, test_lang):
        """Depth is validated before execution: a rejected program charges 0 steps."""
        result, ctx = run_limited(evaluator, "(add (add 1 1) 2)", test_lang, max_ast_depth=2)
        assert result.status == "ast_depth_exceeded"
        assert ctx.steps == 0
        assert ctx.result_stack == []


# ============================================================================
# AST DEPTH TESTS (static)
# ============================================================================

# (id, program, depth) -- depth derived from the node tree, not from running the program.
#   1                          literal                                   -> 1
#   (add 1 2)                  call -> literals                          -> 2
#   (add (add 1 1) 2)          call -> call -> literal                   -> 3
#   (if true 1 2)              if -> literals                            -> 2
#   (if true 1 (if false 2 3)) if -> if -> literal                       -> 3
#   (add (if true 1 2) 3)      call -> if -> literal                     -> 3
#   (and true (and true false)) call -> call -> literal                  -> 3
DEPTH_CASES = [
    ("literal", "1", 1),
    ("single_call", "(add 1 2)", 2),
    ("nested_call", "(add (add 1 1) 2)", 3),
    ("simple_if", "(if true 1 2)", 2),
    ("nested_if_in_unselected_else", "(if true 1 (if false 2 3))", 3),
    ("nested_if_in_selected_branch", "(if false (if true 1 2) 3)", 3),
    ("if_inside_call_argument", "(add (if true 1 2) 3)", 3),
    ("call_inside_if_branch", "(if true (add 1 2) 3)", 3),
    ("nested_short_circuit", "(and true (and true false))", 3),
    ("deep_unselected_if_branch", "(if true 1 (if true 2 (if true 3 (add 4 5))))", 5),
    ("deep_skipped_short_circuit_operand", "(and false (and true (and true (or true false))))", 5),
    ("nullary_call", "(def f () 1)\n(f)", 1),
    ("multiple_top_level_takes_max", "(add 1 2)\n(add (add 1 1) 2)\n5", 3),
]


class TestStaticAstDepth:
    """Depth is a static property of the parsed program and never depends on execution."""

    @pytest.mark.parametrize("case", DEPTH_CASES, ids=[c[0] for c in DEPTH_CASES])
    def test_depth_matches_derivation(self, evaluator, test_lang, case):
        _id, program, depth = case
        tree = evaluator._get_parser(test_lang.grammar).parse(program)
        assert evaluator._validate_ast_depth(tree, 1_000) == depth

    @pytest.mark.parametrize("case", DEPTH_CASES, ids=[c[0] for c in DEPTH_CASES])
    def test_at_limit_accepted_and_one_above_rejected(self, evaluator, test_lang, case):
        _id, program, depth = case
        ok, _ = run_limited(evaluator, program, test_lang, max_ast_depth=depth)
        assert ok.status == "success", ok.error_message
        bad, ctx = run_limited(evaluator, program, test_lang, max_ast_depth=depth - 1)
        assert bad.status == "ast_depth_exceeded"
        assert ctx.steps == 0, "static rejection must happen before any runtime step"

    def test_configured_limit_is_actually_used_not_a_default(self, evaluator, test_lang):
        """Regression: validation once ran against a hard-coded 1000. Prove that the
        caller's limit, whatever it is, decides the outcome."""
        program = "(add (add (add 1 1) 1) 1)"          # depth 4
        outcomes = {
            limit: run_limited(evaluator, program, test_lang, max_ast_depth=limit)[0].status
            for limit in (1, 2, 3, 4, 5, 50)
        }
        assert outcomes == {
            1: "ast_depth_exceeded", 2: "ast_depth_exceeded", 3: "ast_depth_exceeded",
            4: "success", 5: "success", 50: "success",
        }

    def test_two_evaluators_with_different_limits_do_not_share_state(self, evaluator, test_lang):
        program = "(add (add 1 1) 2)"                    # depth 3
        strict, _ = run_limited(evaluator, program, test_lang, max_ast_depth=2)
        lenient, _ = run_limited(evaluator, program, test_lang, max_ast_depth=3)
        strict_again, _ = run_limited(evaluator, program, test_lang, max_ast_depth=2)
        assert (strict.status, lenient.status, strict_again.status) == (
            "ast_depth_exceeded", "success", "ast_depth_exceeded")

    def test_default_limit_is_1000_through_public_execute(self, evaluator, test_lang):
        """The public execute() path uses DEFAULT_MAX_AST_DEPTH: 1000 runs, 1001 is rejected."""
        at_limit = "(add 1 " * 999 + "1" + ")" * 999          # 999 calls + literal = depth 1000
        over = "(add 1 " * 1000 + "1" + ")" * 1000            # depth 1001
        ok = evaluator.execute(at_limit, test_lang)
        assert ok.status == "success"
        assert ok.value == 1000
        assert evaluator.execute(over, test_lang).status == "ast_depth_exceeded"

    # ---- uncalled function bodies -------------------------------------------------

    def test_uncalled_function_with_over_limit_body_is_rejected(self, evaluator, test_lang):
        """The body is depth 3 and is never called; the program must still be rejected."""
        program = "(def deep (x) (add (add x 1) 1))\n1"
        tree = evaluator._get_parser(test_lang.grammar).parse(program)
        assert evaluator._validate_ast_depth(tree, 1_000) == 3

        bad, ctx = run_limited(evaluator, program, test_lang, max_ast_depth=2)
        assert bad.status == "ast_depth_exceeded"
        assert ctx.steps == 0
        assert ctx.functions.get("deep") is None, "rejected before the def was even registered"

        ok, _ = run_limited(evaluator, program, test_lang, max_ast_depth=3)
        assert ok.status == "success"
        assert ok.value == 1

    def test_function_bodies_are_independent_roots_starting_at_depth_one(self, evaluator, test_lang):
        """Body depth is not added to the call site: caller depth 2 + body depth 3 is NOT 5."""
        program = "(def f (x) (add (add x 1) 1))\n(add 1 (f 1))"
        tree = evaluator._get_parser(test_lang.grammar).parse(program)
        # body root depth 3; call site (add 1 (f 1)) is call -> call -> literal = 3
        assert evaluator._validate_ast_depth(tree, 1_000) == 3
        ok, _ = run_limited(evaluator, program, test_lang, max_ast_depth=3)
        assert ok.status == "success"
        assert ok.value == 4

    def test_multiple_function_bodies_each_validated_deepest_decides(self, evaluator, test_lang):
        program = ("(def shallow (x) x)\n"
                   "(def medium (x) (add x 1))\n"
                   "(def deepest (x) (add (add (add x 1) 1) 1))\n"
                   "(def another (x) (add x x))\n"
                   "1")
        tree = evaluator._get_parser(test_lang.grammar).parse(program)
        assert evaluator._validate_ast_depth(tree, 1_000) == 4
        assert run_limited(evaluator, program, test_lang, max_ast_depth=4)[0].status == "success"
        assert run_limited(evaluator, program, test_lang, max_ast_depth=3)[0].status == "ast_depth_exceeded"

    def test_deep_body_in_unselected_branch_of_uncalled_function(self, evaluator, test_lang):
        program = "(def g (n) (if (eq n 0) 0 (if true 1 (if true 2 (add 3 4)))))\n5"
        tree = evaluator._get_parser(test_lang.grammar).parse(program)
        assert evaluator._validate_ast_depth(tree, 1_000) == 5
        assert run_limited(evaluator, program, test_lang, max_ast_depth=4)[0].status == "ast_depth_exceeded"

    # ---- unselected / skipped code still counts -----------------------------------

    def test_unselected_if_branch_counts_but_is_never_evaluated(self, evaluator, test_lang):
        program = "(if true 1 (add (add (add 1 1) 1) 1))"      # else subtree is depth 5 from root
        tree = evaluator._get_parser(test_lang.grammar).parse(program)
        assert evaluator._validate_ast_depth(tree, 1_000) == 5
        bad, ctx = run_limited(evaluator, program, test_lang, max_ast_depth=4)
        assert bad.status == "ast_depth_exceeded"
        assert ctx.steps == 0
        # Within limit the branch is still never evaluated (3 steps: if, true, 1).
        ok, ctx_ok = run_limited(evaluator, program, test_lang, max_ast_depth=5)
        assert ok.status == "success"
        assert ok.value == 1
        assert ctx_ok.steps == 3

    def test_skipped_short_circuit_operand_counts_but_is_never_evaluated(self, evaluator, test_lang):
        program = "(and false (or true (and true (or true false))))"   # skipped operand: depth 5
        tree = evaluator._get_parser(test_lang.grammar).parse(program)
        assert evaluator._validate_ast_depth(tree, 1_000) == 5
        assert run_limited(evaluator, program, test_lang, max_ast_depth=4)[0].status == "ast_depth_exceeded"
        ok, ctx = run_limited(evaluator, program, test_lang, max_ast_depth=5)
        assert ok.status == "success"
        assert ok.value is False
        assert ctx.steps == 2                                   # call(and), false

    def test_eager_mode_depth_identical_to_short_circuit(self, evaluator, test_lang, eager_lang):
        program = "(and true (and true (and true false)))"
        for lang in (test_lang, eager_lang):
            tree = evaluator._get_parser(lang.grammar).parse(program)
            assert evaluator._validate_ast_depth(tree, 1_000) == 4

    def test_validator_does_not_execute_anything(self, evaluator, test_lang):
        """A program that would fail at runtime is still just measured, not run."""
        tree = evaluator._get_parser(test_lang.grammar).parse("(div 1 0)\nundefined_name")
        assert evaluator._validate_ast_depth(tree, 1_000) == 2

    def test_validator_is_iterative_not_recursive(self, evaluator, test_lang):
        """A 300-deep tree validates under a recursion limit only ~40 frames above us."""
        program = "(add 1 " * 300 + "1" + ")" * 300
        tree = evaluator._get_parser(test_lang.grammar).parse(program)
        base = len(inspect.stack())
        old = sys.getrecursionlimit()
        sys.setrecursionlimit(base + 40)
        try:
            depth = evaluator._validate_ast_depth(tree, 1_000)
        finally:
            sys.setrecursionlimit(old)
        assert depth == 301

    def test_ast_depth_error_preserves_context_for_next_run(self, evaluator, test_lang):
        r1, _ = run_limited(evaluator, "(add (add (add 1 1) 1) 1)", test_lang, max_ast_depth=2)
        assert r1.status == "ast_depth_exceeded"
        r2, _ = run_limited(evaluator, "(add 1 2)", test_lang, max_ast_depth=10)
        assert r2.status == "success"
        assert r2.value == 3


# ============================================================================
# CALL DEPTH TESTS (runtime)
# ============================================================================

RECUR = "(def recur (n)\n  (if (eq n 0)\n      0\n      (recur (sub n 1))))\n"


class TestCallDepth:
    """Active user-function invocations. Arguments evaluate before entry; built-ins
    never count. recur(k) has k+1 simultaneously active invocations at its deepest."""

    def test_single_invocation_counts_once(self, evaluator, test_lang):
        # (id 5): one user invocation.  Limit 1 passes, limit 0 rejects.
        program = "(def id (x) x)\n(id 5)"
        assert run_limited(evaluator, program, test_lang, max_call_depth=1)[0].status == "success"
        rejected, ctx = run_limited(evaluator, program, test_lang, max_call_depth=0)
        assert rejected.status == "recursion_limit_exceeded"
        assert ctx.call_depth == 0

    def test_builtins_do_not_count_toward_call_depth(self, evaluator, test_lang):
        deep_builtins = "(add (add (add (add 1 1) 1) 1) 1)"
        ok, ctx = run_limited(evaluator, deep_builtins, test_lang, max_call_depth=0)
        assert ok.status == "success"
        assert ok.value == 5
        assert ctx.call_depth == 0

    def test_base_case_invocation_counts(self, evaluator, test_lang):
        # recur(0) is a single invocation that immediately hits the base case.
        program = RECUR + "(recur 0)"
        assert run_limited(evaluator, program, test_lang, max_call_depth=1)[0].status == "success"
        assert run_limited(evaluator, program, test_lang, max_call_depth=0)[0].status == "recursion_limit_exceeded"

    def test_nested_calls_stack_their_depth(self, evaluator, test_lang):
        # outer -> middle -> inner, each one invocation, 3 active at the deepest point.
        program = ("(def inner (x) x)\n(def middle (x) (inner x))\n"
                   "(def outer (x) (middle x))\n(outer 1)")
        assert run_limited(evaluator, program, test_lang, max_call_depth=3)[0].status == "success"
        bad, ctx = run_limited(evaluator, program, test_lang, max_call_depth=2)
        assert bad.status == "recursion_limit_exceeded"
        assert ctx.call_depth == 0

    def test_sequential_calls_do_not_accumulate(self, evaluator, test_lang):
        # Each call returns before the next starts: peak depth is 1, not 3.
        program = "(def id (x) x)\n(add (id 1) (add (id 2) (id 3)))"
        ok, ctx = run_limited(evaluator, program, test_lang, max_call_depth=1)
        assert ok.status == "success"
        assert ok.value == 6
        assert ctx.call_depth == 0

    def test_arguments_evaluated_before_entry(self, evaluator, test_lang):
        # (id (id 1)): inner id returns before the outer id is entered => peak depth 1.
        program = "(def id (x) x)\n(id (id 1))"
        ok, _ = run_limited(evaluator, program, test_lang, max_call_depth=1)
        assert ok.status == "success"
        assert ok.value == 1
        # Compare: calling inside the BODY keeps the outer active => peak depth 2.
        body_call = "(def id (x) x)\n(def wrap (x) (id x))\n(wrap 1)"
        assert run_limited(evaluator, body_call, test_lang, max_call_depth=1)[0].status == "recursion_limit_exceeded"
        assert run_limited(evaluator, body_call, test_lang, max_call_depth=2)[0].status == "success"

    @pytest.mark.parametrize("k", [0, 1, 50, 98])
    def test_recursion_well_below_limit_succeeds(self, evaluator, test_lang, k):
        result, ctx = run_limited(evaluator, RECUR + f"(recur {k})", test_lang)
        assert result.status == "success"
        assert result.value == 0
        assert ctx.call_depth == 0

    def test_exactly_100_active_invocations_succeed(self, evaluator, test_lang):
        # recur(99): invocations for n = 99, 98, ..., 0 => exactly 100 active at the base case.
        result, ctx = run_limited(evaluator, RECUR + "(recur 99)", test_lang)
        assert result.status == "success", result.error_message
        assert result.value == 0
        assert ctx.call_depth == 0

    def test_101_active_invocations_are_rejected(self, evaluator, test_lang):
        # recur(100): invocations for n = 100, ..., 0 => 101 would be active.
        result, ctx = run_limited(evaluator, RECUR + "(recur 100)", test_lang)
        assert result.status == "recursion_limit_exceeded"
        assert "Call depth exceeded" in result.error_message
        assert ctx.call_depth == 0

    def test_limit_is_a_real_configured_parameter(self, evaluator, test_lang):
        program = RECUR + "(recur 4)"          # 5 active invocations
        assert run_limited(evaluator, program, test_lang, max_call_depth=5)[0].status == "success"
        assert run_limited(evaluator, program, test_lang, max_call_depth=4)[0].status == "recursion_limit_exceeded"

    def test_call_depth_limit_does_not_use_python_recursion(self, evaluator, test_lang):
        """100 nested user invocations succeed with Python's own recursion limit
        lowered to ~40 frames above this test, so the language limit is not Python's."""
        program = RECUR + "(recur 99)"
        tree = evaluator._get_parser(test_lang.grammar).parse(program)
        context = evaluator._new_context(test_lang)
        base = len(inspect.stack())
        old = sys.getrecursionlimit()
        sys.setrecursionlimit(base + 40)
        try:
            result = evaluator._run(tree, context, test_lang)
        finally:
            sys.setrecursionlimit(old)
        assert result.status == "success"
        assert result.value == 0

    def test_recursion_limit_is_independent_of_ast_depth(self, evaluator, test_lang):
        """100 invocations pass with a tiny static depth; deep syntax passes with 0 user calls."""
        program = RECUR + "(recur 99)"
        shallow, _ = run_limited(evaluator, program, test_lang, max_ast_depth=5)
        assert shallow.status == "success"
        deep = "(add 1 " * 200 + "1" + ")" * 200
        assert run_limited(evaluator, deep, test_lang, max_call_depth=0)[0].status == "success"


class TestCleanupAndIsolation:
    """Call depth and variable bindings are restored on return AND on every failure."""

    def test_depth_and_bindings_restored_after_normal_return(self, evaluator, test_lang):
        program = "(def f (x) x)\n(f 7)"
        result, ctx = run_limited(evaluator, program, test_lang)
        assert result.status == "success"
        assert ctx.call_depth == 0
        assert ctx.bindings == {}

    def test_caller_bindings_survive_a_nested_call(self, evaluator, test_lang):
        """Regression: after (f 1) returned, the caller's `y` was gone ('Unknown identifier')."""
        program = "(def f (x) x)\n(def g (y) (add (f 1) y))\n(g 5)"
        result, ctx = run_limited(evaluator, program, test_lang)
        assert result.status == "success", result.error_message
        assert result.value == 6                        # f(1)=1, y=5
        assert ctx.bindings == {}

    def test_caller_bindings_survive_when_call_is_second_operand(self, evaluator, test_lang):
        program = "(def f (x) x)\n(def g (y) (add y (f 1)))\n(g 5)"
        result, _ = run_limited(evaluator, program, test_lang)
        assert result.status == "success"
        assert result.value == 6

    @pytest.mark.parametrize("label,program,expected_status", [
        ("arithmetic_error", "(def f (x) (div x 0))\n(f 1)", "error"),
        ("undefined_variable", "(def f (x) (add x unknown))\n(f 1)", "error"),
        ("non_boolean_condition", "(def f (x) (if x 1 2))\n(f 5)", "error"),
        ("error_two_levels_deep", "(def f (x) (div x 0))\n(def g (y) (f y))\n(def h (z) (g z))\n(h 1)", "error"),
        ("error_inside_nested_arg", "(def f (x) x)\n(def g (y) (add (f y) (div y 0)))\n(g 1)", "error"),
        ("step_limit_inside_call", "(def f (x) (add (add x 1) 1))\n(f 1)", "step_limit_exceeded"),
    ])
    def test_depth_and_bindings_restored_after_failure(self, evaluator, test_lang, label, program, expected_status):
        max_steps = 4 if label == "step_limit_inside_call" else None
        result, ctx = run_limited(evaluator, program, test_lang, max_steps=max_steps)
        assert result.status == expected_status, (label, result.error_message)
        assert ctx.call_depth == 0, f"{label}: call_depth leaked"
        assert ctx.bindings == {}, f"{label}: callee bindings leaked into caller scope"

    def test_recursion_limit_rejection_restores_depth_and_bindings(self, evaluator, test_lang):
        result, ctx = run_limited(evaluator, RECUR + "(recur 150)", test_lang)
        assert result.status == "recursion_limit_exceeded"
        assert ctx.call_depth == 0
        assert ctx.bindings == {}

    def test_recovery_after_recursion_limit_rejection(self, evaluator, test_lang):
        bad, _ = run_limited(evaluator, RECUR + "(recur 100)", test_lang)
        assert bad.status == "recursion_limit_exceeded"
        good, ctx = run_limited(evaluator, RECUR + "(recur 99)", test_lang)
        assert good.status == "success"
        assert ctx.call_depth == 0
        # A fresh public execute() on the same evaluator instance is also unaffected.
        assert evaluator.execute(RECUR + "(recur 3)", test_lang).value == 0

    def test_unknown_function_and_arity_errors_leave_no_residue(self, evaluator, test_lang):
        for program in ("(nope 1)", "(def f (x) x)\n(f 1 2)", "(def f (x y) x)\n(f 1)"):
            result, ctx = run_limited(evaluator, program, test_lang)
            assert result.status == "error", program
            assert ctx.call_depth == 0
            assert ctx.bindings == {}

    def test_function_environment_isolation(self, evaluator, test_lang):
        """Hand derivation (the existing recursion test claims 130 and miscalculates it):
             outer(x) = x + outer(x-1), outer(0) = 0     => outer(5) = 5+4+3+2+1+0   = 15
             inner(y) = y + inner(y-1), inner(0) = 115   => inner(5) = 5+4+3+2+1+115 = 130
             outer(5) + inner(5) = 15 + 130 = 145
        The test's own comment says inner(5) = 115, which is inner's BASE value, not inner(5)."""
        program = ("(def outer (x) (if (eq x 0) 0 (add x (outer (sub x 1)))))\n"
                   "(def inner (y) (if (eq y 0) 115 (add y (inner (sub y 1)))))\n"
                   "(add (outer 5) (inner 5))")
        result, ctx = run_limited(evaluator, program, test_lang)
        assert result.status == "success"
        assert result.value == 145
        assert ctx.call_depth == 0

    def test_same_parameter_names_in_different_functions_do_not_collide(self, evaluator, test_lang):
        program = ("(def f (x) (add x 100))\n(def g (x) (add (f x) x))\n(g 1)")
        result, _ = run_limited(evaluator, program, test_lang)
        assert result.status == "success"
        assert result.value == 102                      # f(1)=101, then + g's own x=1

    def test_declaration_ordering_call_before_def_is_an_error(self, evaluator, test_lang):
        result, _ = run_limited(evaluator, "(f 1)\n(def f (x) x)", test_lang)
        assert result.status == "error"
        assert "Unknown function" in result.error_message

    def test_function_defined_later_is_visible_to_earlier_function_bodies(self, evaluator, test_lang):
        """g's body refers to h, which is declared after g but before the call."""
        program = "(def g (x) (h x))\n(def h (x) (add x 1))\n(g 4)"
        result, _ = run_limited(evaluator, program, test_lang)
        assert result.status == "success"
        assert result.value == 5

    def test_mutual_recursion_boundary(self, evaluator, test_lang):
        program = ("(def even (n) (if (eq n 0) true (odd (sub n 1))))\n"
                   "(def odd (n) (if (eq n 0) false (even (sub n 1))))\n")
        assert run_limited(evaluator, program + "(even 98)", test_lang)[0].value is True     # 99 active
        assert run_limited(evaluator, program + "(even 99)", test_lang)[0].value is False    # 100 active
        assert run_limited(evaluator, program + "(even 100)", test_lang)[0].status == "recursion_limit_exceeded"


# ============================================================================
# SHORT-CIRCUIT / FUNCTION INTERACTION (regression for operand mix-up)
# ============================================================================

class TestShortCircuitWithUserFunctions:
    """Regression: a user-function call inside an and/or operand used to have its
    argument and result values consumed as boolean operands of the enclosing
    short-circuit frame. Expected values are derived from the language semantics."""

    IDENT = "(def identity (x) x)\n"

    @pytest.mark.parametrize("expr,expected", [
        ("(and (identity true) true)", True),
        ("(and (identity true) false)", False),
        ("(and (identity false) true)", False),
        ("(or (identity false) true)", True),
        ("(or (identity false) false)", False),
        ("(or (identity true) false)", True),
        ("(and true (identity true))", True),
        ("(or false (identity true))", True),
        ("(and (identity true) (identity true))", True),
        ("(and (and (identity true) true) (or false (identity true)))", True),
    ])
    def test_values(self, evaluator, test_lang, expr, expected):
        result, _ = run_limited(evaluator, self.IDENT + expr, test_lang)
        assert result.status == "success", result.error_message
        assert result.value is expected

    def test_decisive_left_operand_skips_failing_right(self, evaluator, test_lang):
        for expr in ("(and (identity false) (div 1 0))", "(or (identity true) (div 1 0))"):
            result, _ = run_limited(evaluator, self.IDENT + expr, test_lang)
            assert result.status == "success"

    def test_non_decisive_left_operand_evaluates_failing_right(self, evaluator, test_lang):
        for expr in ("(and (identity true) (div 1 0))", "(or (identity false) (div 1 0))"):
            result, _ = run_limited(evaluator, self.IDENT + expr, test_lang)
            assert result.status == "error"

    def test_step_count_with_function_operand(self, evaluator, test_lang):
        """(and (identity true) false): call(and), call(identity), arg true, body x, false = 5."""
        result, ctx = run_limited(evaluator, self.IDENT + "(and (identity true) false)", test_lang)
        assert result.value is False
        assert ctx.steps == 5
        below, _ = run_limited(evaluator, self.IDENT + "(and (identity true) false)", test_lang, max_steps=4)
        assert below.status == "step_limit_exceeded"

    def test_non_boolean_operand_is_rejected(self, evaluator, test_lang):
        for expr in ("(and 1 true)", "(and true 1)", "(or 1 true)", "(or false 1)"):
            assert run_limited(evaluator, expr, test_lang)[0].status == "error", expr

    def test_eager_mode_still_evaluates_both_sides(self, evaluator, eager_lang):
        result, ctx = run_limited(evaluator, self.IDENT + "(and (identity true) true)", eager_lang)
        assert result.value is True
        # call(and), call(identity), true, body x, true = 5
        assert ctx.steps == 5


# ============================================================================
# OUTPUT LIMIT ASSESSMENT
# ============================================================================

class TestOutputLimitAssessment:
    """Assessment of output-limit implementation."""

    def test_no_output_produced(self, evaluator, test_lang):
        """Current language has no output-producing operations."""
        result, _ = run_limited(evaluator, "(add 1 2)", test_lang)
        assert result.output == ""

    def test_add_output_method_exists(self, evaluator, test_lang):
        """add_output() method exists in EvalContext."""
        from src.execution.iterative_evaluator import EvalContext
        assert hasattr(EvalContext, 'add_output')
        assert callable(getattr(EvalContext, 'add_output'))

    def test_output_limit_not_exercised(self, evaluator, test_lang):
        """add_output() exists but nothing in the language calls it. Documented, not a gap."""
        from src.execution.iterative_evaluator import EvalContext
        context = EvalContext(max_output_bytes=10)
        assert hasattr(context, 'output_buffer')
        assert context.output_buffer == ""
        assert hasattr(context, 'max_output_bytes')
