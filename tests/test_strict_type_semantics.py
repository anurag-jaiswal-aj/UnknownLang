"""Strict runtime type semantics (Wave 1C.16).

Contract (also recorded in RELEASES.md, Wave 1C.16):

* Arithmetic (add, sub, mul, div, mod) requires int operands. A bool operand is a type error.
* and, or and not require bool operands. An int operand is a type error. In short-circuit
  mode the right operand of and/or is evaluated only when the left one does not decide the
  result. In eager mode both operands are evaluated first, so an error raised while evaluating
  the right operand is reported before a type error in the left operand (design.md, Boolean
  Semantics, "Key distinction").
* if requires a bool condition (no truthiness) and evaluates only the selected branch.
* eq accepts any two values. Values of the same type compare by value. Values of different
  types are never equal, so (eq 1 true) is false (design.md declares eq as any x any -> bool).
* Type checks run after the operands are evaluated and before the operation itself, so a type
  error takes precedence over division by zero and over overflow.
* A type error has status "error" and one of the messages used below.

Expected results are hand-derived from that contract. Each expectation records the status, the
exact Python type of the value (so 1 and True are never confused), and the exact error text.
Short-circuit cases whose outcome depends on which error is raised first (a non-boolean left
operand with an erroring right operand) are not specified; they are only checked for agreement
between the two evaluators.
"""

import pytest

from src.execution.engine import ExecutionEngine
from src.execution.iterative_evaluator import IterativeEvaluator
from src.language.generator import LanguageGenerator
from src.language.seed import LanguageSeed
from src.oracle.reference_evaluator import ReferenceEvaluator

MODES = ["wraparound", "saturating", "error-on-overflow"]
SHORT_CIRCUIT = [True, False]
EVALUATORS = {
    "iterative": IterativeEvaluator,
    "facade": ExecutionEngine,
    "reference": ReferenceEvaluator,
}


def _lang(mode, short_circuit):
    return LanguageGenerator().generate(LanguageSeed(
        name="TypeLang", syntax_style="lisp", features=["recursion", "functions"],
        difficulty=2, arithmetic=mode, short_circuit=short_circuit))


SPECS = {(mode, sc): _lang(mode, sc) for mode in MODES for sc in SHORT_CIRCUIT}


def int_ok(value):
    return ("success", int, value, "")


def bool_ok(value):
    return ("success", bool, value, "")


def type_error(message):
    return ("error", type(None), None, message)


def arith(op, got):
    return type_error(f"Arithmetic operation '{op}' requires int arguments, got {got}")


BOOL_INT = type_error("Boolean operation requires boolean arguments, got int")
NOT_INT = type_error("not requires boolean argument, got int")
IF_INT = type_error("if condition must be boolean, got int")
DIV_ZERO = type_error("Runtime error: Division by zero")


def both(expected):
    """Same expectation in short-circuit and eager configurations."""
    return expected, expected


def _shape(result):
    return (result.status, type(result.value), result.value, result.error_message)


# (program, expected when short_circuit=True, expected when short_circuit=False)
TABLE = [
    # --- equality: any two values, same type compares by value, no coercion ----------
    ("(eq 1 1)", *both(bool_ok(True))),
    ("(eq 1 2)", *both(bool_ok(False))),
    ("(eq -1 -1)", *both(bool_ok(True))),
    ("(eq 0 0)", *both(bool_ok(True))),
    ("(eq true true)", *both(bool_ok(True))),
    ("(eq false false)", *both(bool_ok(True))),
    ("(eq true false)", *both(bool_ok(False))),
    ("(eq 1 true)", *both(bool_ok(False))),
    ("(eq true 1)", *both(bool_ok(False))),
    ("(eq 0 false)", *both(bool_ok(False))),
    ("(eq false 0)", *both(bool_ok(False))),
    ("(eq (eq 1 1) 1)", *both(bool_ok(False))),
    ("(eq (eq 1 1) true)", *both(bool_ok(True))),
    ("(not (eq 1 true))", *both(bool_ok(True))),
    ("(if (eq 1 true) 10 20)", *both(int_ok(20))),
    ("(and (eq 0 false) true)", *both(bool_ok(False))),
    ("(or (eq 0 false) (eq 1 1))", *both(bool_ok(True))),
    ("(def same (a b) (eq a b))\n(same 1 true)", *both(bool_ok(False))),
    ("(def same (a b) (eq a b))\n(same true true)", *both(bool_ok(True))),
    # --- arithmetic: operands must be int ----------------------------------------------
    ("(add 1 2)", *both(int_ok(3))),
    ("(sub 0 1)", *both(int_ok(-1))),
    ("(mul -3 4)", *both(int_ok(-12))),
    ("(div -7 2)", *both(int_ok(-3))),
    ("(mod -7 3)", *both(int_ok(-1))),
    ("(add 9223372036854775807 0)", *both(int_ok(9223372036854775807))),
    ("(add 1 true)", *both(arith("add", "bool"))),
    ("(add true 1)", *both(arith("add", "bool"))),
    ("(add true true)", *both(arith("add", "bool"))),
    ("(sub 1 false)", *both(arith("sub", "bool"))),
    ("(sub false 1)", *both(arith("sub", "bool"))),
    ("(mul true 3)", *both(arith("mul", "bool"))),
    ("(mul 3 false)", *both(arith("mul", "bool"))),
    ("(div 4 true)", *both(arith("div", "bool"))),
    ("(div true 2)", *both(arith("div", "bool"))),
    ("(mod 5 true)", *both(arith("mod", "bool"))),
    ("(mod true 2)", *both(arith("mod", "bool"))),
    # a type error takes precedence over division and modulo by zero (false == 0 in Python)
    ("(div 1 false)", *both(arith("div", "bool"))),
    ("(mod 5 false)", *both(arith("mod", "bool"))),
    ("(div false 0)", *both(arith("div", "bool"))),
    ("(mod false 0)", *both(arith("mod", "bool"))),
    # a type error takes precedence over overflow in every arithmetic mode
    ("(add 9223372036854775807 true)", *both(arith("add", "bool"))),
    ("(sub -9223372036854775808 true)", *both(arith("sub", "bool"))),
    ("(mul 9223372036854775807 true)", *both(arith("mul", "bool"))),
    # nested arithmetic and comparison results
    ("(add 1 (mul 2 true))", *both(arith("mul", "bool"))),
    ("(add (eq 1 true) 1)", *both(arith("add", "bool"))),
    ("(add 1 (add 2 (sub true 3)))", *both(arith("sub", "bool"))),
    ("(if (eq (add 1 true) 2) 1 2)", *both(arith("add", "bool"))),
    # --- and / or / not: operands must be bool ------------------------------------------
    ("(and true true)", *both(bool_ok(True))),
    ("(and true false)", *both(bool_ok(False))),
    ("(or false true)", *both(bool_ok(True))),
    ("(or false false)", *both(bool_ok(False))),
    ("(not true)", *both(bool_ok(False))),
    ("(not false)", *both(bool_ok(True))),
    ("(and 1 true)", *both(BOOL_INT)),
    ("(and true 1)", *both(BOOL_INT)),
    ("(and 0 true)", *both(BOOL_INT)),
    ("(or false 1)", *both(BOOL_INT)),
    ("(or 0 false)", *both(BOOL_INT)),
    ("(and (add 1 2) true)", *both(BOOL_INT)),
    ("(and false 1)", bool_ok(False), BOOL_INT),   # short-circuit: right operand never evaluated
    ("(or true 1)", bool_ok(True), BOOL_INT),      # short-circuit: right operand never evaluated
    ("(and false (div 1 0))", bool_ok(False), DIV_ZERO),
    ("(or true (div 1 0))", bool_ok(True), DIV_ZERO),
    ("(and true (div 1 0))", DIV_ZERO, DIV_ZERO),
    ("(not 1)", *both(NOT_INT)),
    ("(not 0)", *both(NOT_INT)),
    ("(or (eq 1 true) true)", *both(bool_ok(True))),
    # --- if: condition must be bool; only the selected branch is evaluated -------------
    ("(if 1 2 3)", *both(IF_INT)),
    ("(if 0 2 3)", *both(IF_INT)),
    ("(if true 1 2)", *both(int_ok(1))),
    ("(if false 1 2)", *both(int_ok(2))),
    ("(if true 1 (add true 1))", *both(int_ok(1))),
    ("(if false (add true 1) 2)", *both(int_ok(2))),
    ("(if (and 1 true) 1 2)", *both(BOOL_INT)),
    ("(if (not 0) 1 2)", *both(NOT_INT)),
    ("(if true true 1)", *both(bool_ok(True))),
    ("(add 1 (if (not 1) 2 3))", *both(NOT_INT)),
    # --- user function arguments are untyped; each operation checks what it receives ---
    ("(def f (x) (add x 1))\n(f true)", *both(arith("add", "bool"))),
    ("(def f (x) (add x 1))\n(f 41)", *both(int_ok(42))),
    ("(def g (x) (not x))\n(g 1)", *both(NOT_INT)),
    ("(def g (x) (not x))\n(g true)", *both(bool_ok(False))),
    ("(def id (x) x)\n(id true)", *both(bool_ok(True))),
    ("(def id (x) x)\n(id 1)", *both(int_ok(1))),
    ("(def f (x y) (add x y))\n(f 1 false)", *both(arith("add", "bool"))),
    ("(def f (x y) (eq x y))\n(f 1 true)", *both(bool_ok(False))),
    ("(def f (x) (if x 1 2))\n(f 1)", *both(IF_INT)),
    ("(def f (x) (if x 1 2))\n(f false)", *both(int_ok(2))),
]

# Eager mode evaluates both operands before checking either, so the right operand's error wins.
# The short-circuit outcome for these programs is not specified (see module docstring).
EAGER_ORDER = [
    ("(and 1 (div 1 0))", DIV_ZERO),
    ("(or 0 (div 1 0))", DIV_ZERO),
    ("(and (add 1 2) (div 1 0))", DIV_ZERO),
    ("(and 1 (add true 1))", arith("add", "bool")),
    ("(or true (add true 1))", arith("add", "bool")),
]

# Programs with no hand-derived expectation: production and reference must agree exactly.
EXTRA_AGREEMENT = [
    "(and 1 (div 1 0))",
    "(or 0 (div 1 0))",
    "(and 1 (add true 1))",
    "(or true (add true 1))",
    "(def h (x) (add x 1))\n5",
    "(def f (x) (if x 1 2))\n(f 1)",
    "(if true 1 9223372036854775807)",
    "(add 9223372036854775807 1)",
    "(mul 9223372036854775807 2)",
    "(div -9223372036854775808 -1)",
    "1",
    "true",
    "false",
]


def _ids(rows):
    return [row[0].replace("\n", " ; ") for row in rows]


class TestHandDerivedContract:
    @pytest.mark.parametrize("program,expect_sc,expect_eager", TABLE, ids=_ids(TABLE))
    def test_every_evaluator_and_arithmetic_mode(self, program, expect_sc, expect_eager):
        for name, evaluator_cls in EVALUATORS.items():
            for mode in MODES:
                for sc in SHORT_CIRCUIT:
                    expected = expect_sc if sc else expect_eager
                    got = _shape(evaluator_cls().execute(program, SPECS[(mode, sc)]))
                    assert got == expected, f"{name} mode={mode} short_circuit={sc}: {program!r}"

    @pytest.mark.parametrize("program,expected", EAGER_ORDER, ids=_ids(EAGER_ORDER))
    def test_eager_mode_raises_the_right_operand_error_first(self, program, expected):
        for name, evaluator_cls in EVALUATORS.items():
            for mode in MODES:
                got = _shape(evaluator_cls().execute(program, SPECS[(mode, False)]))
                assert got == expected, f"{name} mode={mode}: {program!r}"


class TestProductionMatchesReference:
    @pytest.mark.parametrize("sc", SHORT_CIRCUIT)
    @pytest.mark.parametrize("mode", MODES)
    def test_identical_status_type_value_and_message(self, mode, sc):
        lang = SPECS[(mode, sc)]
        production, reference = IterativeEvaluator(), ReferenceEvaluator()
        programs = [row[0] for row in TABLE] + [row[0] for row in EAGER_ORDER] + EXTRA_AGREEMENT
        for program in programs:
            ours = _shape(production.execute(program, lang))
            theirs = _shape(reference.execute(program, lang))
            assert ours == theirs, f"mode={mode} short_circuit={sc}: {program!r}"

    @pytest.mark.parametrize("sc", SHORT_CIRCUIT)
    def test_facade_is_identical_to_the_iterative_evaluator(self, sc):
        lang = SPECS[("wraparound", sc)]
        for program in [row[0] for row in TABLE] + EXTRA_AGREEMENT:
            assert _shape(ExecutionEngine().execute(program, lang)) == \
                _shape(IterativeEvaluator().execute(program, lang)), program
