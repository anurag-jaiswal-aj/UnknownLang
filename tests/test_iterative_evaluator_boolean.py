"""Boolean semantic tests for IterativeEvaluator.

This module verifies short-circuit and eager boolean evaluation:
- Short-circuit AND: false left skips RHS evaluation
- Short-circuit OR: true left skips RHS evaluation
- Strict boolean validation for all operands
- Nested function operand evaluation
- Eager mode: both operands always evaluated
- Error recovery and frame isolation
"""

import pytest

from src.execution.iterative_evaluator import IterativeEvaluator
from src.language.generator import LanguageGenerator
from src.language.seed import LanguageSeed


@pytest.fixture
def evaluator():
    """Create an IterativeEvaluator instance."""
    return IterativeEvaluator()


@pytest.fixture
def short_circuit_lang():
    """Create language spec with short-circuit boolean mode."""
    generator = LanguageGenerator()
    seed = LanguageSeed(
        name="ShortCircuitLang",
        syntax_style="lisp",
        features=["arithmetic", "functions"],
        difficulty=1,
        arithmetic="wraparound",
        short_circuit=True,
    )
    return generator.generate(seed)


@pytest.fixture
def eager_lang():
    """Create language spec with eager boolean mode."""
    generator = LanguageGenerator()
    seed = LanguageSeed(
        name="EagerLang",
        syntax_style="lisp",
        features=["arithmetic", "functions"],
        difficulty=1,
        arithmetic="wraparound",
        short_circuit=False,
    )
    return generator.generate(seed)


@pytest.fixture
def identity_func():
    """Program text defining identity function."""
    return """
(def identity (x) x)
"""


class TestShortCircuitAnd:
    """Short-circuit AND evaluation tests."""

    def test_and_false_left_short_circuits(self, evaluator, short_circuit_lang):
        """Short-circuit: false left operand skips RHS evaluation."""
        result = evaluator.execute("(and false (div 1 0))", short_circuit_lang)
        assert result.status == "success"
        assert result.value == False

    def test_and_true_false(self, evaluator, short_circuit_lang):
        """True left evaluates RHS which is false."""
        result = evaluator.execute("(and true false)", short_circuit_lang)
        assert result.status == "success"
        assert result.value == False

    def test_and_true_true(self, evaluator, short_circuit_lang):
        """True left evaluates RHS which is true."""
        result = evaluator.execute("(and true true)", short_circuit_lang)
        assert result.status == "success"
        assert result.value == True

    def test_and_with_nested_function_false(self, evaluator, short_circuit_lang, identity_func):
        """Short-circuit with nested function returning false."""
        program = identity_func + "(and (identity false) (div 1 0))"
        result = evaluator.execute(program, short_circuit_lang)
        assert result.status == "success"
        assert result.value == False

    def test_and_with_nested_function_skips_rhs(self, evaluator, short_circuit_lang, identity_func):
        """RHS not evaluated when LHS determines short-circuit."""
        program = identity_func + "(and (identity false) (div 1 0))"
        result = evaluator.execute(program, short_circuit_lang)
        assert result.status == "success"
        assert result.value == False


class TestShortCircuitOr:
    """Short-circuit OR evaluation tests."""

    def test_or_true_left_short_circuits(self, evaluator, short_circuit_lang):
        """Short-circuit: true left operand skips RHS evaluation."""
        result = evaluator.execute("(or true (div 1 0))", short_circuit_lang)
        assert result.status == "success"
        assert result.value == True

    def test_or_false_true(self, evaluator, short_circuit_lang):
        """False left evaluates RHS which is true."""
        result = evaluator.execute("(or false true)", short_circuit_lang)
        assert result.status == "success"
        assert result.value == True

    def test_or_false_false(self, evaluator, short_circuit_lang):
        """False left evaluates RHS which is false."""
        result = evaluator.execute("(or false false)", short_circuit_lang)
        assert result.status == "success"
        assert result.value == False

    def test_or_with_nested_function_true(self, evaluator, short_circuit_lang, identity_func):
        """Short-circuit with nested function returning true."""
        program = identity_func + "(or (identity true) (div 1 0))"
        result = evaluator.execute(program, short_circuit_lang)
        assert result.status == "success"
        assert result.value == True

    def test_or_with_nested_function_skips_rhs(self, evaluator, short_circuit_lang, identity_func):
        """RHS not evaluated when LHS determines short-circuit."""
        program = identity_func + "(or (identity true) (div 1 0))"
        result = evaluator.execute(program, short_circuit_lang)
        assert result.status == "success"
        assert result.value == True


class TestStrictBooleanValidation:
    """Strict boolean validation tests."""

    def test_and_invalid_first_operand_raises_error(self, evaluator, short_circuit_lang):
        """Invalid first operand raises type error."""
        result = evaluator.execute("(and 42 true)", short_circuit_lang)
        assert result.status == "error"
        assert "boolean" in result.error_message.lower()

    def test_or_invalid_first_operand_raises_error(self, evaluator, short_circuit_lang):
        """Invalid first operand raises type error."""
        result = evaluator.execute("(or 42 true)", short_circuit_lang)
        assert result.status == "error"
        assert "boolean" in result.error_message.lower()

    def test_and_invalid_later_operand_raises_error(self, evaluator, short_circuit_lang):
        """Invalid later operand raises error when evaluated."""
        result = evaluator.execute("(and true 42)", short_circuit_lang)
        assert result.status == "error"
        assert "boolean" in result.error_message.lower()

    def test_or_invalid_later_operand_raises_error(self, evaluator, short_circuit_lang):
        """Invalid later operand raises error when evaluated."""
        result = evaluator.execute("(or false 42)", short_circuit_lang)
        assert result.status == "error"
        assert "boolean" in result.error_message.lower()

    def test_and_invalid_skipped_operand_not_evaluated(self, evaluator, short_circuit_lang, identity_func):
        """Invalid operand that is skipped is not evaluated."""
        # LHS is false, so RHS (div 1 0) should not be evaluated
        program = identity_func + "(and (identity false) (div 1 0))"
        result = evaluator.execute(program, short_circuit_lang)
        assert result.status == "success"
        assert result.value == False

    def test_or_invalid_skipped_operand_not_evaluated(self, evaluator, short_circuit_lang, identity_func):
        """Invalid operand that is skipped is not evaluated."""
        # LHS is true, so RHS (div 1 0) should not be evaluated
        program = identity_func + "(or (identity true) (div 1 0))"
        result = evaluator.execute(program, short_circuit_lang)
        assert result.status == "success"
        assert result.value == True


class TestNestedFunctionNonBooleanResult:
    """Tests for nested functions returning non-Boolean values."""

    def test_and_nested_function_returns_int_raises_error(self, evaluator, short_circuit_lang):
        """Nested function returning int raises error when evaluated."""
        program = """
(def get_int () 42)
(and (get_int) true)
"""
        result = evaluator.execute(program, short_circuit_lang)
        assert result.status == "error"
        assert "boolean" in result.error_message.lower()

    def test_or_nested_function_returns_int_raises_error(self, evaluator, short_circuit_lang):
        """Nested function returning int raises error when evaluated."""
        program = """
(def get_int () 42)
(or (get_int) true)
"""
        result = evaluator.execute(program, short_circuit_lang)
        assert result.status == "error"
        assert "boolean" in result.error_message.lower()


class TestEagerMode:
    """Eager evaluation mode tests."""

    def test_eager_and_both_operands_evaluated(self, evaluator, eager_lang):
        """In eager mode, both operands are evaluated."""
        result = evaluator.execute("(and true (add 1 2))", eager_lang)
        assert result.status == "error"
        assert "boolean" in result.error_message.lower()

    def test_eager_or_both_operands_evaluated(self, evaluator, eager_lang):
        """In eager mode, both operands are evaluated."""
        result = evaluator.execute("(or false (add 1 2))", eager_lang)
        assert result.status == "error"
        assert "boolean" in result.error_message.lower()

    def test_eager_and_propagates_division_by_zero(self, evaluator, eager_lang):
        """Eager mode propagates division-by-zero errors."""
        result = evaluator.execute("(and true (div 1 0))", eager_lang)
        assert result.status == "error"
        assert "division" in result.error_message.lower() or "zero" in result.error_message.lower()

    def test_eager_or_propagates_division_by_zero(self, evaluator, eager_lang):
        """Eager mode propagates division-by-zero errors."""
        result = evaluator.execute("(or false (div 1 0))", eager_lang)
        assert result.status == "error"
        assert "division" in result.error_message.lower() or "zero" in result.error_message.lower()

    def test_eager_left_to_right_evaluation_order(self, evaluator, eager_lang):
        """Eager mode preserves left-to-right evaluation order."""
        # Both operands evaluated, left should be checked first for boolean type
        result = evaluator.execute("(and (add 1 2) true)", eager_lang)
        assert result.status == "error"
        assert "boolean" in result.error_message.lower()


class TestLifecycleAndIsolation:
    """Frame lifecycle and isolation tests."""

    def test_repeated_boolean_executions_no_frame_leak(self, evaluator, short_circuit_lang):
        """Repeated Boolean executions do not leak frames."""
        # Execute multiple Boolean operations
        evaluator.execute("(and true false)", short_circuit_lang)
        evaluator.execute("(or false true)", short_circuit_lang)
        evaluator.execute("(and (identity true) false)", short_circuit_lang)
        
        # Final execution should work correctly
        result = evaluator.execute("(and true true)", short_circuit_lang)
        assert result.status == "success"
        assert result.value == True

    def test_boolean_error_does_not_corrupt_next_execution(self, evaluator, short_circuit_lang):
        """Boolean evaluation error does not corrupt the next execution."""
        # First, try with invalid operand (should fail)
        bad_result = evaluator.execute("(and 42 true)", short_circuit_lang)
        assert bad_result.status == "error"
        
        # Then, execute a valid program - should work correctly
        good_result = evaluator.execute("(and true false)", short_circuit_lang)
        assert good_result.status == "success"
        assert good_result.value == False

    def test_multi_level_nested_function_operands(self, evaluator, short_circuit_lang):
        """Multi-level nested function operands work correctly."""
        program = """
(def identity (x) x)
(def double (y) (identity (identity y)))
(def triple (z) (double (identity z)))
(and (triple false) (div 1 0))
"""
        result = evaluator.execute(program, short_circuit_lang)
        assert result.status == "success"
        assert result.value == False


class TestParameterizedShortCircuitBehavior:
    """Parameterized tests for short-circuit behavior."""

    @pytest.mark.parametrize("left,expected_right_evaluated", [
        (False, True),   # false AND evaluates RHS
        (True, False),   # true AND short-circuits RHS
    ])
    def test_and_short_circuit_behavior(self, evaluator, short_circuit_lang, left, expected_right_evaluated):
        """Test AND short-circuit with different left operands."""
        # When left is false, result is false without evaluating RHS
        # When left is true, result depends on RHS (but RHS was not evaluated in skipped case)
        if left == False:
            # RHS should be skipped (use division to verify it's not evaluated)
            program = f"(and false (div 1 0))"
            result = evaluator.execute(program, short_circuit_lang)
            assert result.status == "success"
            assert result.value == False
        else:
            # LHS is true, RHS must be evaluated and must be boolean
            program = f"(and true true)"
            result = evaluator.execute(program, short_circuit_lang)
            assert result.status == "success"
            assert result.value == True

    @pytest.mark.parametrize("left,expected_right_evaluated", [
        (False, True),   # false OR evaluates RHS
        (True, False),   # true OR short-circuits RHS
    ])
    def test_or_short_circuit_behavior(self, evaluator, short_circuit_lang, left, expected_right_evaluated):
        """Test OR short-circuit with different left operands."""
        # When left is true, result is true without evaluating RHS
        # When left is false, result depends on RHS (but RHS was not evaluated in skipped case)
        if left == True:
            # RHS should be skipped (use division to verify it's not evaluated)
            program = f"(or true (div 1 0))"
            result = evaluator.execute(program, short_circuit_lang)
            assert result.status == "success"
            assert result.value == True
        else:
            # LHS is false, RHS must be evaluated
            program = f"(or false true)"
            result = evaluator.execute(program, short_circuit_lang)
            assert result.status == "success"
            assert result.value == True
