"""Contract verification and regression hardening for IterativeEvaluator (Wave 1C.13.2).

Covers, independently of the evaluator's own frame loop:
  * AST depth: explicit per-node traces for the seven approved examples, checked
    against a recursive oracle written here (the evaluator's validator is iterative).
  * Step charging: a spy proves WHICH frames are charged; IF / condition / selected
    branch are each charged exactly once; a failing node is charged; a rejected
    attempt is not.
  * Signed 64-bit arithmetic boundaries in all three overflow modes.
  * Parse-error handling.
  * Reproducible differential parity against the independent ReferenceEvaluator (src/oracle), with the
    the canonical INT64_MIN / -1 program included (see TestReferenceMatchesTheCanonicalInt64Contract).

Decisions recorded by the user for this wave:
  1. IF expression, condition expression and selected branch are separate expression
     nodes, each charged exactly one step. Nothing is charged twice.
  2. The signed 64-bit language contract overrides any evaluator for INT64_MIN / -1
     (the reference evaluator had to be corrected to match it in Wave 1C.14).
  3. Semantic expression-node counting is canonical.
"""

import pytest
from lark import Tree

from src.oracle.reference_evaluator import ReferenceEvaluator
from src.execution.iterative_evaluator import IterativeEvaluator
from tests.test_iterative_evaluator_resource_limits import _lang, run_limited

INT64_MIN = -(2 ** 63)
INT64_MAX = 2 ** 63 - 1
MODES = ["wraparound", "saturating", "error-on-overflow"]


@pytest.fixture
def evaluator():
    return IterativeEvaluator()


@pytest.fixture
def sc_lang():
    return _lang(short_circuit=True)


@pytest.fixture
def eager_lang():
    return _lang(short_circuit=False)


# ============================================================================
# 1. AST DEPTH: explicit traces for the approved examples
# ============================================================================

SEMANTIC = {"literal", "call", "if_expr"}


def oracle_nodes(tree):
    """Independent oracle (recursive, test-only): [(rule, depth)] for every semantic
    expression node. Roots are depth 1; a child expression of a call/if_expr is one
    deeper; wrappers (program, program_element, expr) and declarations add nothing;
    each def body is a fresh root at depth 1."""
    out = []

    def walk(node, depth):
        if not isinstance(node, Tree):
            return
        if node.data in SEMANTIC:
            out.append((node.data, depth))
            if node.data != "literal":
                for c in node.children:
                    if isinstance(c, Tree) and c.data == "expr":
                        walk(c, depth + 1)
        elif node.data == "def_decl":
            for c in node.children:
                if isinstance(c, Tree) and c.data == "expr":
                    walk(c, 1)
        else:
            for c in node.children:
                walk(c, depth)

    walk(tree, 1)
    return out


# program -> hand-written (rule, depth) multiset, then the maximum.
# Written from the contract, not from any evaluator output.
APPROVED = [
    ("1", [("literal", 1)], 1),
    ("(add 1 2)",
     [("call", 1), ("literal", 2), ("literal", 2)], 2),
    ("(add (add 1 1) 2)",
     [("call", 1), ("call", 2), ("literal", 3), ("literal", 3), ("literal", 2)], 3),
    ("(if true 1 2)",
     [("if_expr", 1), ("literal", 2), ("literal", 2), ("literal", 2)], 2),
    ("(if true 1 (if false 2 3))",
     [("if_expr", 1), ("literal", 2), ("literal", 2),
      ("if_expr", 2), ("literal", 3), ("literal", 3), ("literal", 3)], 3),
    ("(add (if true 1 2) 3)",
     [("call", 1), ("if_expr", 2), ("literal", 3), ("literal", 3), ("literal", 3),
      ("literal", 2)], 3),
    ("(and true (and true false))",
     [("call", 1), ("literal", 2), ("call", 2), ("literal", 3), ("literal", 3)], 3),
]


class TestApprovedDepthTraces:
    @pytest.mark.parametrize("program,nodes,depth", APPROVED, ids=[a[0] for a in APPROVED])
    def test_oracle_matches_hand_written_trace(self, evaluator, sc_lang, program, nodes, depth):
        tree = evaluator._get_parser(sc_lang.grammar).parse(program)
        assert sorted(oracle_nodes(tree)) == sorted(nodes)
        assert max(d for _, d in nodes) == depth

    @pytest.mark.parametrize("program,nodes,depth", APPROVED, ids=[a[0] for a in APPROVED])
    def test_validator_returns_approved_depth(self, evaluator, sc_lang, program, nodes, depth):
        tree = evaluator._get_parser(sc_lang.grammar).parse(program)
        assert evaluator._validate_ast_depth(tree, 1000) == depth

    @pytest.mark.parametrize("program,nodes,depth", APPROVED, ids=[a[0] for a in APPROVED])
    def test_boundary_and_no_steps_before_rejection(self, evaluator, sc_lang, program, nodes, depth):
        ok, _ = run_limited(evaluator, program, sc_lang, max_ast_depth=depth)
        assert ok.status == "success", ok.error_message
        bad, ctx = run_limited(evaluator, program, sc_lang, max_ast_depth=depth - 1)
        assert bad.status == "ast_depth_exceeded"
        assert ctx.steps == 0

    @pytest.mark.parametrize("program,nodes,depth", APPROVED, ids=[a[0] for a in APPROVED])
    def test_eager_mode_has_identical_depth(self, evaluator, eager_lang, program, nodes, depth):
        tree = evaluator._get_parser(eager_lang.grammar).parse(program)
        assert evaluator._validate_ast_depth(tree, 1000) == depth

    def test_wrappers_do_not_count(self, evaluator, sc_lang):
        """The tree has program > program_element > expr above every expression; none of
        those three levels is added: a bare literal is depth 1, not 4."""
        tree = evaluator._get_parser(sc_lang.grammar).parse("1")
        assert [n.data for n in tree.iter_subtrees_topdown()] == [
            "program", "program_element", "expr", "literal"]
        assert evaluator._validate_ast_depth(tree, 1000) == 1

    def test_oracle_agrees_with_validator_on_a_larger_corpus(self, evaluator, sc_lang):
        corpus = [
            "(def f (x) (add (add x 1) 1))\n(f 1)",
            "(if (eq 1 1) (add 1 (add 2 3)) (if true 4 5))",
            "(and (or true false) (and true (or false true)))",
            "(def a (x) x)\n(def b (y) (if (eq y 0) 1 (add y (b (sub y 1)))))\n(add (a 1) (b 2))",
            "(add 1 2)\n(if true (add 1 (add 1 1)) 0)\n7",
        ]
        for p in corpus:
            tree = evaluator._get_parser(sc_lang.grammar).parse(p)
            assert evaluator._validate_ast_depth(tree, 1000) == max(d for _, d in oracle_nodes(tree)), p


# ============================================================================
# 2. STEP CHARGING: which frames are charged, and exactly once
# ============================================================================

def charge_trace(evaluator, program, lang, max_steps=None):
    """Run through the production `_run`, spying on `_process_frame`.

    Returns (result, context, records) where each record is
    (frame_type_name, rule_or_None, steps_charged_by_that_frame)."""
    tree = evaluator._get_parser(lang.grammar).parse(program)
    ctx = evaluator._new_context(lang, max_steps=max_steps)
    records = []
    original = evaluator._process_frame

    def spy(frame_stack, frame, context, spec):
        before = context.steps
        try:
            original(frame_stack, frame, context, spec)
        finally:
            rule = frame.expr.data if isinstance(frame.expr, Tree) else None
            records.append((frame.frame_type.name, rule, context.steps - before))

    evaluator._process_frame = spy
    try:
        result = evaluator._run(tree, ctx, lang)
    finally:
        del evaluator._process_frame          # restore the class method
    return result, ctx, records


RICH = ("(def id (x) x)\n"
        "(def pick (n) (if (eq n 0) (id 10) (add n 1)))\n"
        "(and (eq (pick 0) 10) (or false (eq (pick 3) 4)))")


class TestOnlySemanticNodesAreCharged:
    def test_charges_come_only_from_semantic_expr_frames(self, evaluator, sc_lang):
        result, ctx, records = charge_trace(evaluator, RICH, sc_lang)
        assert result.status == "success" and result.value is True
        for ftype, rule, charged in records:
            if ftype == "EXPR" and rule in SEMANTIC:
                assert charged == 1, (ftype, rule, charged)          # exactly once, never twice
            else:
                assert charged == 0, f"bookkeeping frame charged: {ftype}/{rule}"
        assert sum(c for _, _, c in records) == ctx.steps

    def test_every_bookkeeping_frame_type_was_exercised_and_free(self, evaluator, sc_lang):
        _, _, records = charge_trace(evaluator, RICH, sc_lang)
        seen = {t for t, _, _ in records}
        assert {"EXPR", "CALL", "ARGUMENT", "BUILTIN", "RETURN", "IF_CONDITION",
                "USER_FUNC_ENTRY", "USER_FUNC_BODY", "SC_AND", "SC_OR"} <= seen
        bookkeeping = [(t, c) for t, r, c in records if not (t == "EXPR" and r in SEMANTIC)]
        assert bookkeeping and all(c == 0 for _, c in bookkeeping)

    def test_wrappers_and_declarations_are_free(self, evaluator, sc_lang):
        _, _, records = charge_trace(evaluator, "(def f (x) x)\n3", sc_lang)
        wrappers = [(t, r, c) for t, r, c in records if r in {"program", "program_element", "expr", "def_decl"}]
        assert wrappers and all(c == 0 for _, _, c in wrappers)

    def test_step_count_equals_number_of_semantic_nodes_evaluated(self, evaluator, sc_lang):
        _, ctx, records = charge_trace(evaluator, RICH, sc_lang)
        evaluated = sum(1 for t, r, _ in records if t == "EXPR" and r in SEMANTIC)
        assert ctx.steps == evaluated


# Hand-derived: IF, its condition expression, and the selected branch are each one node.
#   (if true 1 2)               if, true, 1                               = 3
#   (if (eq 1 1) 1 2)           if, call(eq), 1, 1, branch 1              = 5
#   (if false 1 2)              if, false, branch 2                       = 3
#   (if true (add 1 2) 9)       if, true, call(add), 1, 2                 = 5
#   (if true 1 (if false 2 3))  if, true, 1  [inner if, false, 2, 3 skipped] = 3
#   (if false 1 (if true 2 3))  if, false, inner if, true, 2              = 5
IF_CASES = [
    ("(if true 1 2)", 3),
    ("(if (eq 1 1) 1 2)", 5),
    ("(if false 1 2)", 3),
    ("(if true (add 1 2) 9)", 5),
    ("(if true 1 (if false 2 3))", 3),
    ("(if false 1 (if true 2 3))", 5),
]


class TestIfIsChargedNodeByNode:
    @pytest.mark.parametrize("program,steps", IF_CASES, ids=[c[0] for c in IF_CASES])
    def test_exact_count_and_boundaries(self, evaluator, sc_lang, program, steps):
        ok, ctx = run_limited(evaluator, program, sc_lang)
        assert ok.status == "success" and ctx.steps == steps
        at, ctx_at = run_limited(evaluator, program, sc_lang, max_steps=steps)
        assert at.status == "success" and ctx_at.steps == steps
        below, ctx_below = run_limited(evaluator, program, sc_lang, max_steps=steps - 1)
        assert below.status == "step_limit_exceeded" and ctx_below.steps == steps - 1


class TestFailedVersusRejected:
    def test_failed_node_is_charged(self, evaluator, sc_lang):
        # (div 1 0): call(div), 1, 0 are charged, then the division itself fails.
        result, ctx = run_limited(evaluator, "(div 1 0)", sc_lang)
        assert result.status == "error" and ctx.steps == 3

    def test_failure_lands_exactly_on_the_budget(self, evaluator, sc_lang):
        result, ctx = run_limited(evaluator, "(div 1 0)", sc_lang, max_steps=3)
        assert result.status == "error" and "Division by zero" in result.error_message
        assert ctx.steps == 3

    def test_rejected_attempt_is_not_charged_and_not_evaluated(self, evaluator, sc_lang):
        # Budget 2 admits call(add) and literal 1; literal 2 is attempted and rejected.
        result, ctx, records = charge_trace(evaluator, "(add 1 2)", sc_lang, max_steps=2)
        assert result.status == "step_limit_exceeded"
        assert ctx.steps == 2
        last = records[-1]
        assert last[0] == "EXPR" and last[1] == "literal" and last[2] == 0


    def test_exhausted_budget_never_reaches_the_failing_operation(self, evaluator, sc_lang):
        # Budget 2 for (div 1 0): the division would fail, but is never reached.
        result, _ = run_limited(evaluator, "(div 1 0)", sc_lang, max_steps=2)
        assert result.status == "step_limit_exceeded"


# ============================================================================
# 3. SIGNED 64-BIT ARITHMETIC BOUNDARIES
# ============================================================================

def _run_arith(evaluator, mode, expr):
    return evaluator.execute(expr, _lang(arithmetic=mode))


class TestInt64MinDividedByMinusOne:
    """The canonical language result, now also produced by the reference evaluator."""

    def test_wraparound_yields_int64_min(self, evaluator):
        r = _run_arith(evaluator, "wraparound", f"(div {INT64_MIN} -1)")
        assert (r.status, r.value) == ("success", INT64_MIN)

    def test_saturating_yields_int64_max(self, evaluator):
        r = _run_arith(evaluator, "saturating", f"(div {INT64_MIN} -1)")
        assert (r.status, r.value) == ("success", INT64_MAX)

    def test_error_on_overflow_reports_overflow(self, evaluator):
        r = _run_arith(evaluator, "error-on-overflow", f"(div {INT64_MIN} -1)")
        assert r.status == "error"
        assert "overflow" in r.error_message.lower()

    @pytest.mark.parametrize("mode", MODES)
    def test_results_are_always_in_signed_64_bit_range(self, evaluator, mode):
        r = _run_arith(evaluator, mode, f"(div {INT64_MIN} -1)")
        if r.status == "success":
            assert INT64_MIN <= r.value <= INT64_MAX

    @pytest.mark.parametrize("mode", MODES)
    def test_remainder_of_int64_min_by_minus_one_is_zero(self, evaluator, mode):
        r = _run_arith(evaluator, mode, f"(mod {INT64_MIN} -1)")
        assert (r.status, r.value) == ("success", 0)

    @pytest.mark.parametrize("mode", MODES)
    def test_neighbouring_values_do_not_overflow(self, evaluator, mode):
        # MAX / -1 = -MAX (representable); MIN / 1 = MIN; (MIN+1) / -1 = MAX.
        for expr, want in [(f"(div {INT64_MAX} -1)", -INT64_MAX),
                           (f"(div {INT64_MIN} 1)", INT64_MIN),
                           (f"(div {INT64_MIN + 1} -1)", INT64_MAX),
                           (f"(div {INT64_MIN} 2)", -(2 ** 62))]:
            r = _run_arith(evaluator, mode, expr)
            assert (r.status, r.value) == ("success", want), (mode, expr)


# (a, b, trunc quotient, remainder = a - trunc(a/b)*b) -- derived by hand:
#   7/2  -> 3  r 1      -7/2 -> -3 r -1      7/-2 -> -3 r 1      -7/-2 -> 3 r -1
DIV_MOD = [
    (7, 2, 3, 1), (-7, 2, -3, -1), (7, -2, -3, 1), (-7, -2, 3, -1),
    (6, 3, 2, 0), (-6, 3, -2, 0), (1, 3, 0, 1), (-1, 3, 0, -1), (0, 5, 0, 0), (0, -5, 0, 0),
]


class TestDivisionAndRemainder:
    @pytest.mark.parametrize("mode", MODES)
    @pytest.mark.parametrize("a,b,q,r", DIV_MOD)
    def test_division_truncates_toward_zero(self, evaluator, mode, a, b, q, r):
        res = _run_arith(evaluator, mode, f"(div {a} {b})")
        assert (res.status, res.value) == ("success", q)

    @pytest.mark.parametrize("mode", MODES)
    @pytest.mark.parametrize("a,b,q,r", DIV_MOD)
    def test_remainder_is_a_minus_trunc_quotient_times_b(self, evaluator, mode, a, b, q, r):
        res = _run_arith(evaluator, mode, f"(mod {a} {b})")
        assert (res.status, res.value) == ("success", r)
        assert a == q * b + r                                   # identity the definition implies

    @pytest.mark.parametrize("mode", MODES)
    def test_division_by_zero_is_an_error(self, evaluator, mode):
        res = _run_arith(evaluator, mode, "(div 5 0)")
        assert res.status == "error" and "Division by zero" in res.error_message

    @pytest.mark.parametrize("mode", MODES)
    def test_modulo_by_zero_is_an_error(self, evaluator, mode):
        res = _run_arith(evaluator, mode, "(mod 5 0)")
        assert res.status == "error" and "Modulo by zero" in res.error_message

    @pytest.mark.parametrize("mode,add_expected,sub_expected,mul_expected", [
        ("wraparound", INT64_MIN, INT64_MAX, INT64_MIN),
        ("saturating", INT64_MAX, INT64_MIN, INT64_MIN),
    ])
    def test_add_sub_mul_overflow_modes(self, evaluator, mode, add_expected, sub_expected, mul_expected):
        # MAX+1 ; MIN-1 ; MIN*2  (MIN*2 wraps to 0 and saturates to MIN)
        assert _run_arith(evaluator, mode, f"(add {INT64_MAX} 1)").value == add_expected
        assert _run_arith(evaluator, mode, f"(sub {INT64_MIN} 1)").value == sub_expected
        want_mul = 0 if mode == "wraparound" else mul_expected
        assert _run_arith(evaluator, mode, f"(mul {INT64_MIN} 2)").value == want_mul

    @pytest.mark.parametrize("expr", [f"(add {INT64_MAX} 1)", f"(sub {INT64_MIN} 1)", f"(mul {INT64_MIN} 2)"])
    def test_error_on_overflow_rejects_each_operation(self, evaluator, expr):
        res = _run_arith(evaluator, "error-on-overflow", expr)
        assert res.status == "error" and "overflow" in res.error_message.lower()


# ============================================================================
# 4. PARSE ERRORS AND CLEANUP
# ============================================================================

class TestParseErrors:
    @pytest.mark.parametrize("program", ["(add 1", ")", "(((", "(add 1 2))"])
    def test_returns_error_result_and_does_not_raise(self, evaluator, sc_lang, program):
        result = evaluator.execute(program, sc_lang)          # must not raise
        assert result.status == "error"
        assert result.value is None
        assert result.error_message

    def test_evaluator_is_reusable_after_a_parse_error(self, evaluator, sc_lang):
        assert evaluator.execute("(add 1", sc_lang).status == "error"
        good = evaluator.execute("(add 1 2)", sc_lang)
        assert (good.status, good.value) == ("success", 3)


# ============================================================================
# 4b. FINAL SEMANTIC DECISIONS (Wave 1C.13.3, authoritative)
# ============================================================================

class TestEmptyProgram:
    """Decision 1: empty source is a valid program with no value."""

    @pytest.mark.parametrize("source", ["", "   ", "\n", " \n\t \n"], ids=["empty", "spaces", "newline", "mixed"])
    def test_empty_source_succeeds_with_no_value(self, evaluator, sc_lang, source):
        result = evaluator.execute(source, sc_lang)
        assert result.status == "success"
        assert result.value is None
        assert result.error_message == ""
        assert result.output == ""

    @pytest.mark.parametrize("arith", MODES)
    @pytest.mark.parametrize("sc", [True, False], ids=["sc", "eager"])
    def test_empty_source_in_every_language_configuration(self, evaluator, arith, sc):
        result = evaluator.execute("", _lang(short_circuit=sc, arithmetic=arith))
        assert (result.status, result.value) == ("success", None)

    def test_empty_program_consumes_no_steps_and_no_depth(self, evaluator, sc_lang):
        result, ctx = run_limited(evaluator, "", sc_lang, max_steps=0, max_ast_depth=0, max_call_depth=0)
        assert (result.status, result.value) == ("success", None)
        assert ctx.steps == 0 and ctx.call_depth == 0

    def test_empty_source_matches_reference_engine(self, evaluator, sc_lang):
        ref = ReferenceEvaluator().execute("", sc_lang)
        ours = evaluator.execute("", sc_lang)
        assert (ours.status, ours.value) == (ref.status, ref.value) == ("success", None)

    def test_program_of_only_declarations_returns_no_value(self, evaluator, sc_lang):
        """Definitions are declarations, not expression values."""
        result = evaluator.execute("(def f (x) x)", sc_lang)
        assert (result.status, result.value) == ("success", None)

    def test_definition_order_matches_reference(self, evaluator, sc_lang):
        cases = [
            ("(def f (x) x)\n(def g (x) x)", None),
            ("5\n(def f (x) x)", None),
            ("(def f (x) x)\n5", 5),
        ]
        for source, expected in cases:
            result = evaluator.execute(source, sc_lang)
            assert (result.status, result.value) == ("success", expected)

    def test_definition_only_matches_reference(self, evaluator, sc_lang):
        from src.oracle.reference_evaluator import ReferenceEvaluator
        source = "(def f (x) x)"
        ours = evaluator.execute(source, sc_lang)
        reference = ReferenceEvaluator().execute(source, sc_lang)
        assert (ours.status, ours.value, type(ours.value)) == (
            reference.status, reference.value, type(reference.value)
        )

        assert evaluator.execute("(add 1 2)", sc_lang).value == 3
        assert evaluator.execute("", sc_lang).value is None
        assert evaluator.execute("(add 3 4)", sc_lang).value == 7


class TestUndefinedFunctionStepCost:
    """Decision 2: (nope 1) costs exactly two semantic steps (the call expression and its
    evaluated argument literal). Function resolution then fails without another step."""

    PROGRAM = "(nope 1)"

    def test_exactly_two_steps_then_function_error(self, evaluator, sc_lang):
        result, ctx = run_limited(evaluator, self.PROGRAM, sc_lang)
        assert result.status == "error"
        assert "Unknown function: nope" in result.error_message
        assert ctx.steps == 2

    def test_budget_2_reaches_the_resolution_error(self, evaluator, sc_lang):
        result, ctx = run_limited(evaluator, self.PROGRAM, sc_lang, max_steps=2)
        assert result.status == "error"
        assert "Unknown function: nope" in result.error_message
        assert ctx.steps == 2

    def test_budget_1_rejects_the_argument_before_it_is_evaluated(self, evaluator, sc_lang):
        result, ctx = run_limited(evaluator, self.PROGRAM, sc_lang, max_steps=1)
        assert result.status == "step_limit_exceeded"
        assert ctx.steps == 1                       # only the call expression was charged

    def test_budget_0_rejects_the_call_expression_itself(self, evaluator, sc_lang):
        result, ctx = run_limited(evaluator, self.PROGRAM, sc_lang, max_steps=0)
        assert result.status == "step_limit_exceeded"
        assert ctx.steps == 0

    def test_charges_are_the_call_and_the_argument_literal_only(self, evaluator, sc_lang):
        result, ctx, records = charge_trace(evaluator, self.PROGRAM, sc_lang)
        charged = [(t, r) for t, r, c in records if c]
        assert charged == [("EXPR", "call"), ("EXPR", "literal")]
        assert ctx.steps == 2

    def test_cost_scales_with_arguments_evaluated_before_resolution(self, evaluator, sc_lang):
        """Arguments are evaluated first, so (nope 1 2) is call + two literals = 3."""
        _, ctx = run_limited(evaluator, "(nope 1 2)", sc_lang)
        assert ctx.steps == 3
        _, ctx0 = run_limited(evaluator, "(nope)", sc_lang)
        assert ctx0.steps == 1

    def test_failure_leaves_no_residual_state(self, evaluator, sc_lang):
        _, ctx = run_limited(evaluator, self.PROGRAM, sc_lang)
        assert ctx.call_depth == 0 and ctx.bindings == {}
        assert evaluator.execute("(add 1 2)", sc_lang).value == 3


# ============================================================================
# 5. REPRODUCIBLE DIFFERENTIAL PARITY AGAINST THE REFERENCE ENGINE
# ============================================================================

IDENT = "(def identity (x) x)\n"
RECUR = "(def recur (n) (if (eq n 0) 0 (recur (sub n 1))))\n"

PARITY_CORPUS = [
    # literals
    "1", "-5", "0", "true", "false",
    # arithmetic, signs, nesting
    "(add 1 2)", "(sub 1 2)", "(mul -3 4)", "(add 1 (mul 2 3))", "(add (add 1 1) (add 2 2))",
    "(div 7 2)", "(div -7 2)", "(div 7 -2)", "(div -7 -2)",
    "(mod 7 2)", "(mod -7 2)", "(mod 7 -2)", "(mod -7 -2)",
    f"(add {INT64_MAX} 1)", f"(sub {INT64_MIN} 1)", f"(mul {INT64_MAX} 2)", f"(mul {INT64_MIN} -1)",
    f"(mod {INT64_MIN} -1)", f"(div {INT64_MAX} -1)",
    f"(div {INT64_MIN} -1)",
    "(div 1 0)", "(mod 1 0)", "(add true 1)", "(add 1 true)",
    # booleans, strict typing
    "(and true true)", "(and true false)", "(and false true)", "(and false false)",
    "(or true true)", "(or true false)", "(or false true)", "(or false false)",
    "(and (and true true) (or false true))", "(or (and false true) (and true true))",
    "(and 1 true)", "(and true 1)", "(or 1 true)", "(or false 1)",
    "(and false (div 1 0))", "(and true (div 1 0))", "(or true (div 1 0))", "(or false (div 1 0))",
    "(not true)", "(not false)", "(not 1)", "(eq 1 1)", "(eq 1 2)", "(eq true true)", "(eq (add 1 1) 2)",
    # if
    "(if true 1 2)", "(if false 1 2)", "(if true 1 (div 1 0))", "(if false (div 1 0) 2)",
    "(if 1 2 3)", "(if true 1 (if false 2 3))", "(if false 1 (if true 2 3))",
    "(add (if true 1 2) 3)",
    # functions
    IDENT + "(identity 42)",
    IDENT + "(and (identity true) true)", IDENT + "(and (identity true) false)",
    IDENT + "(or (identity false) true)", IDENT + "(or (identity true) (div 1 0))",
    IDENT + "(and (identity false) (div 1 0))", IDENT + "(and true (identity false))",
    IDENT + "(identity (identity 1))",
    "(def f (x) (add x 1))\n(def g (x) (f (f x)))\n(g 5)",
    "(def f (x) x)\n(def g (y) (add (f 1) y))\n(g 5)",
    "(def f (x) x)\n(def g (y) (add y (f 1)))\n(g 5)",
    "(def f (x) (add x 100))\n(def g (x) (add (f x) x))\n(g 1)",
    "(def g (x) (h x))\n(def h (x) (add x 1))\n(g 4)",
    RECUR + "(recur 0)", RECUR + "(recur 10)", RECUR + "(recur 40)",
    "(def fact (n) (if (eq n 0) 1 (mul n (fact (sub n 1)))))\n(fact 10)",
    ("(def outer (x) (if (eq x 0) 0 (add x (outer (sub x 1)))))\n"
     "(def inner (y) (if (eq y 0) 115 (add y (inner (sub y 1)))))\n(add (outer 5) (inner 5))"),
    ("(def even (n) (if (eq n 0) true (odd (sub n 1))))\n"
     "(def odd (n) (if (eq n 0) false (even (sub n 1))))\n(even 10)"),
    "(def f (x) (div x 0))\n(f 1)",
    "(def f (x) (add x unknown))\n(f 1)",
    "(def f (x) x)\n(f 1 2)", "(def f (x y) x)\n(f 1)",
    # lexical scoping: a callee must not see its caller's variables (both must error)
    "(def f (y) (add x y))\n(def g (x) (f 1))\n(g 5)",
    "(f 1)\n(def f (x) x)", "(nope 1)", "x",
    "(add 1 2)\n9",
    "(add 1",
]

PARITY_LANGS = [(a, sc) for a in MODES for sc in (True, False)]


def _key(r):
    return (r.status, r.value, type(r.value))


class TestDifferentialParity:
    """Status, value and value type must match the reference engine across every
    overflow mode and both boolean modes. Messages and step counts are intentionally
    NOT compared: step accounting differs by design (decision 3)."""

    @pytest.mark.parametrize("arith,sc", PARITY_LANGS, ids=[f"{a}-{'sc' if s else 'eager'}" for a, s in PARITY_LANGS])
    def test_corpus_matches_reference(self, arith, sc):
        lang = _lang(short_circuit=sc, arithmetic=arith)
        mismatches = []
        for program in PARITY_CORPUS:
            ours = IterativeEvaluator().execute(program, lang)
            ref = ReferenceEvaluator().execute(program, lang)
            if _key(ours) != _key(ref):
                mismatches.append((program, _key(ours), _key(ref)))
        assert not mismatches, "\n".join(map(repr, mismatches))

    def test_corpus_is_not_trivially_all_errors(self):
        lang = _lang()
        statuses = [IterativeEvaluator().execute(p, lang).status for p in PARITY_CORPUS]
        assert statuses.count("success") > 50 and statuses.count("error") > 15


class TestReferenceMatchesTheCanonicalInt64Contract:
    """The reference evaluator's INT64_MIN / -1 defect (it returned +2**63 in wraparound and
    saturating modes) was fixed in Wave 1C.14, independently of the iterative evaluator
    (a modular shift rather than a bit mask). These tests replace the two strict xfails
    that documented it, and the program is now part of the differential corpus too."""

    CANONICAL = {"wraparound": ("success", INT64_MIN), "saturating": ("success", INT64_MAX),
                 "error-on-overflow": ("error", None)}

    @pytest.mark.parametrize("mode", MODES)
    def test_reference_result_is_the_canonical_one(self, mode):
        r = ReferenceEvaluator().execute(f"(div {INT64_MIN} -1)", _lang(arithmetic=mode))
        assert (r.status, r.value) == self.CANONICAL[mode]
        if r.status == "error":
            assert "overflow" in r.error_message.lower()

    @pytest.mark.parametrize("mode", MODES)
    def test_both_evaluators_agree_on_the_canonical_result(self, mode):
        lang = _lang(arithmetic=mode)
        program = f"(div {INT64_MIN} -1)"
        ref = ReferenceEvaluator().execute(program, lang)
        ours = IterativeEvaluator().execute(program, lang)
        assert (ref.status, ref.value) == (ours.status, ours.value) == self.CANONICAL[mode]

    @pytest.mark.parametrize("mode", MODES)
    def test_reference_division_stays_in_range_for_every_neighbour(self, mode):
        for a, b, want in [(INT64_MAX, -1, -INT64_MAX), (INT64_MIN, 1, INT64_MIN),
                           (INT64_MIN + 1, -1, INT64_MAX), (INT64_MIN, 2, -(2 ** 62))]:
            r = ReferenceEvaluator().execute(f"(div {a} {b})", _lang(arithmetic=mode))
            assert (r.status, r.value) == ("success", want), (mode, a, b)
