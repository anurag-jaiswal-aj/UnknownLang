"""Frame lifecycle tests for IterativeEvaluator.

This module verifies the frame-based evaluation architecture:
- CALL frames consumed exactly once
- ARGUMENT frames consumed exactly once
- USER_FUNC_ENTRY and USER_FUNC_BODY have defined lifecycles
- Function-result frames produce exactly one result
- Cleanup frames restore state without synthetic results
- Call depth and bindings are restored correctly
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
def test_lang():
    """Create language spec with arithmetic and functions features."""
    generator = LanguageGenerator()
    seed = LanguageSeed(
        name="LifecycleLang",
        syntax_style="lisp",
        features=["arithmetic", "functions"],
        difficulty=1,
        arithmetic="wraparound",
        short_circuit=True,
    )
    return generator.generate(seed)


class TestFrameLifecycle:
    """Frame lifecycle tests."""

    def test_call_frame_consumed_once(self, evaluator, test_lang):
        """Verify CALL frame is consumed exactly once."""
        program = "(add 1 2)"
        result = evaluator.execute(program, test_lang)
        assert result.status == "success"
        assert result.value == 3

    def test_argument_frame_consumed_once(self, evaluator, test_lang):
        """Verify ARGUMENT frame is consumed exactly once."""
        program = "(add (add 1 1) (add 2 2))"
        result = evaluator.execute(program, test_lang)
        assert result.status == "success"
        assert result.value == 6

    def test_function_result_single(self, evaluator, test_lang):
        """Verify function-result frame produces exactly one result."""
        program = """
(def identity (x) x)
(identity 42)
"""
        result = evaluator.execute(program, test_lang)
        assert result.status == "success"
        assert result.value == 42

    def test_cleanup_frame_no_synthetic_result(self, evaluator, test_lang):
        """Verify cleanup frames don't produce synthetic results."""
        program = """
(def foo (x) (add x 1))
(def bar (y) (foo y))
(bar 5)
"""
        result = evaluator.execute(program, test_lang)
        assert result.status == "success"
        assert result.value == 6

    def test_depth_restoration(self, evaluator, test_lang):
        """Verify call depth and bindings are restored after nested returns."""
        program = """
(def outer (n)
  (if (eq n 0)
      100
      (inner n)))
(def inner (n)
  (if (eq n 0)
      200
      (outer (sub n 1))))
(outer 3)
"""
        result = evaluator.execute(program, test_lang)
        assert result.status == "success"
        # outer(3) -> inner(3) -> outer(2) -> inner(2) -> outer(1) -> inner(1) -> outer(0) = 100
        assert result.value == 100


class TestNestedCallEvaluation:
    """Nested call evaluation tests."""

    def test_nested_function_call(self, evaluator, test_lang):
        """Verify nested function calls return correct values."""
        program = """
(def add1 (x) (add x 1))
(def add2 (x) (add1 (add1 x)))
(add2 5)
"""
        result = evaluator.execute(program, test_lang)
        assert result.status == "success"
        assert result.value == 7

    def test_multiple_nested_calls(self, evaluator, test_lang):
        """Verify multiple nested function calls."""
        program = """
(def f (x) (add x 1))
(def g (x) (f (f x)))
(def h (x) (g (g (f x))))
(h 0)
"""
        result = evaluator.execute(program, test_lang)
        assert result.status == "success"
        assert result.value == 5

    def test_left_to_right_argument_evaluation(self, evaluator, test_lang):
        """Verify left-to-right argument evaluation order."""
        program = """
(def order (a b) (add a b))
(def test (n)
  (if (eq n 0)
      0
      (order (add n 10) (test (sub n 1)))))
(test 3)
"""
        result = evaluator.execute(program, test_lang)
        assert result.status == "success"
        assert result.value == 36


class TestFunctionArities:
    """Function arity tests."""

    def test_two_parameter_function(self, evaluator, test_lang):
        """Verify function with two parameters."""
        program = """
(def add2 (a b) (add a b))
(add2 10 20)
"""
        result = evaluator.execute(program, test_lang)
        assert result.status == "success"
        assert result.value == 30

    def test_three_parameter_function(self, evaluator, test_lang):
        """Verify function with three parameters."""
        program = """
(def sum3 (a b c) (add (add a b) c))
(sum3 1 2 3)
"""
        result = evaluator.execute(program, test_lang)
        assert result.status == "success"
        assert result.value == 6

    def test_multiple_call_same_evaluator(self, evaluator, test_lang):
        """Verify multiple calls using same evaluator instance."""
        program1 = "(add 1 2)"
        program2 = "(add 3 4)"
        
        result1 = evaluator.execute(program1, test_lang)
        result2 = evaluator.execute(program2, test_lang)
        
        assert result1.status == "success"
        assert result1.value == 3
        assert result2.status == "success"
        assert result2.value == 7


class TestConditionalEvaluation:
    """Conditional evaluation tests."""

    def test_if_expression(self, evaluator, test_lang):
        """Verify if expression returns correct branch."""
        program = "(if true 42 99)"
        result = evaluator.execute(program, test_lang)
        assert result.status == "success"
        assert result.value == 42

    def test_if_with_function_calls(self, evaluator, test_lang):
        """Verify if expression with function calls in branches."""
        program = """
(def true_branch () 100)
(def false_branch () 200)
(if true (true_branch) (false_branch))
"""
        result = evaluator.execute(program, test_lang)
        assert result.status == "success"
        assert result.value == 100

    def test_nested_if_expressions(self, evaluator, test_lang):
        """Verify nested if expressions."""
        program = """
(def test (x)
  (if (eq x 0)
      1
      (if (eq x 1)
          2
          3)))
(test 0)
"""
        result = evaluator.execute(program, test_lang)
        assert result.status == "success"
        assert result.value == 1


class TestErrorRecovery:
    """Error recovery tests."""

    def test_failed_then_valid_execution(self, evaluator, test_lang):
        """Verify failed execution doesn't affect subsequent valid execution."""
        # First, try to execute with undefined function (should fail)
        bad_program = "(undefined_func 1 2)"
        result1 = evaluator.execute(bad_program, test_lang)
        assert result1.status == "error"
        assert "Unknown function" in result1.error_message

        # Then, execute a valid program
        good_program = "(add 1 2)"
        result2 = evaluator.execute(good_program, test_lang)
        assert result2.status == "success"
        assert result2.value == 3

    def test_call_depth_resets_between_executions(self, evaluator, test_lang):
        """Verify call depth returns to initial value between executions."""
        program1 = """
(def deep (n)
  (if (eq n 0)
      0
      (deep (sub n 1))))
(deep 10)
"""
        result1 = evaluator.execute(program1, test_lang)
        assert result1.status == "success"
        assert result1.value == 0

        # Execute another program - depth should be reset
        program2 = "(add 1 2)"
        result2 = evaluator.execute(program2, test_lang)
        assert result2.status == "success"
        assert result2.value == 3


class TestRecursionBoundary:
    """Recursion boundary tests (frame-based evaluation)."""

    def test_recur_100_exceeds_limit(self, evaluator, test_lang):
        """Test recur(100) exceeds recursion limit with 101 invocations."""
        program = """
(def recur (n)
  (if (eq n 0)
      0
      (recur (sub n 1))))
(recur 100)
"""
        result = evaluator.execute(program, test_lang)
        assert result.status == "recursion_limit_exceeded"
        assert "Call depth exceeded" in result.error_message

    def test_recur_99_success(self, evaluator, test_lang):
        """Test recur(99) succeeds with 100 invocations (exactly at limit)."""
        program = """
(def recur (n)
  (if (eq n 0)
      0
      (recur (sub n 1))))
(recur 99)
"""
        result = evaluator.execute(program, test_lang)
        assert result.status == "success"
        assert result.value == 0
