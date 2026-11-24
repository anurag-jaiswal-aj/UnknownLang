"""Recursion boundary tests for ExecutionEngine.

These tests verify that the frame-based evaluation engine correctly
enforces the call depth limit (default 100) for recursive functions.

IMPLEMENTATION NOTE:
ExecutionEngine is a facade over the iterative evaluator, which keeps user-function
calls on an explicit frame stack instead of the Python call stack. Python's recursion
limit therefore does not constrain the engine, and max_call_depth (default 100) is the
only call-depth ceiling, so the exact boundary below is testable.

EXPECTED BEHAVIOR:
- Recursion depth tracking via EvalContext.call_depth
- RecursionLimitExceeded raised when depth exceeds max_call_depth
- max_call_depth default: 100
- max_call_depth=100 allows 100 active invocations (depth 1-100)
- depth 101 triggers RecursionLimitExceeded

The evaluator increments call depth when it pushes a user-function frame and restores
it when the frame completes or the call fails, so state is clean after an error.
"""

import pytest

from src.execution.engine import MAX_INT64, MIN_INT64, ExecutionEngine, RecursionLimitExceeded
from src.language.generator import LanguageGenerator
from src.language.seed import LanguageSeed


@pytest.fixture
def recursion_lang():
    """Create language spec with recursion and functions features."""
    generator = LanguageGenerator()
    seed = LanguageSeed(
        name="RecursionLang",
        syntax_style="lisp",
        features=["recursion", "functions"],
        difficulty=2,
        arithmetic="wraparound",
        short_circuit=True,
    )
    return generator.generate(seed)


@pytest.fixture
def engine():
    """Create an ExecutionEngine instance."""
    return ExecutionEngine()


# =============================================================================
# EXACT RECURSION BOUNDARY TESTS
# =============================================================================

class TestExactRecursionBoundary:
    """Exact recursion boundary tests per the specification.

    The recur function definition:
        (def recur (n)
          (if (eq n 0)
              0
              (recur (sub n 1))))

    Expected results:
    - (recur 98)  → 99 active invocations → success (depth 99 <= 100)
    - (recur 99)  → 100 active invocations → success (depth 100 <= 100)
    - (recur 100) → 101 active invocations → recursion_limit_exceeded (depth 101 > 100)

    With frame-based evaluation, the depth check happens at the start of
    _eval_user_func, BEFORE the recursive call to _eval(body).
    """

    def test_recur_98_success(self, engine, recursion_lang):
        """Test recur(98) succeeds with 99 active invocations.

        Call chain: recur(98) → recur(97) → ... → recur(0) = 99 calls + base case
        Active invocations at peak: 99
        This is within the limit of 100.
        """
        program = """
(def recur (n)
  (if (eq n 0)
      0
      (recur (sub n 1))))
(recur 98)
"""
        result = engine.execute(program, recursion_lang)

        assert result.status == "success"
        assert result.value == 0

    def test_recur_99_success(self, engine, recursion_lang):
        """Test recur(99) succeeds with 100 active invocations.

        Call chain: recur(99) → recur(98) → ... → recur(0) = 100 calls + base case
        Active invocations at peak: 100
        This is exactly at the limit of 100, so it should succeed.
        """
        program = """
(def recur (n)
  (if (eq n 0)
      0
      (recur (sub n 1))))
(recur 99)
"""
        result = engine.execute(program, recursion_lang)

        assert result.status == "success"
        assert result.value == 0

    def test_recur_100_exceeds_limit(self, engine, recursion_lang):
        """Test recur(100) exceeds recursion limit with 101 invocations.

        Call chain: recur(100) → recur(99) → ... → recur(0) = 101 calls + base case
        Active invocations at peak: 101
        This exceeds the limit of 100, so it should fail with recursion_limit_exceeded.
        """
        program = """
(def recur (n)
  (if (eq n 0)
      0
      (recur (sub n 1))))
(recur 100)
"""
        result = engine.execute(program, recursion_lang)

        assert result.status == "recursion_limit_exceeded"
        assert "Call depth exceeded" in result.error_message


class TestRecursionWithNonzeroBaseCase:
    """Tests with base case at non-zero values."""

    def test_recur_base_case_at_5(self, engine, recursion_lang):
        """Test recursive function with base case at n=5.

        recur_base5(10) → recur_base5(9) → ... → recur_base5(5) = 6 invocations
        """
        program = """
(def recur_base5 (n)
  (if (eq n 5)
      5
      (recur_base5 (sub n 1))))
(recur_base5 10)
"""
        result = engine.execute(program, recursion_lang)

        assert result.status == "success"
        assert result.value == 5

    def test_recur_base_case_at_0_exact(self, engine, recursion_lang):
        """Test recursive function with base case at n=0.

        Base case is at depth 1 (immediately), so any input should work.
        """
        program = """
(def base_zero (n)
  (if (eq n 0)
      0
      (base_zero (sub n 1))))
(base_zero 50)
"""
        result = engine.execute(program, recursion_lang)

        assert result.status == "success"
        assert result.value == 0


# =============================================================================
# RECOVERY TESTS (DEPTH-101 FAILURE FOLLOWED BY SUCCESS)
# =============================================================================

class TestRecursionRecovery:
    """Tests for engine state recovery after recursion limit exceeded."""

    def test_after_recursion_limit_independent_function_works(self, engine, recursion_lang):
        """Test that independent function works after recursion limit exceeded.

        This verifies that the engine properly resets its state after
        a recursion limit error. Each execution creates a fresh EvalContext,
        so the call depth should start at 0 for the next program.
        """
        # First, try to exceed the limit
        program1 = """
(def recur (n)
  (if (eq n 0)
      0
      (recur (sub n 1))))
(recur 100)
"""
        result1 = engine.execute(program1, recursion_lang)
        assert result1.status == "recursion_limit_exceeded"

        # Then, execute an independent successful function
        program2 = """
(def foo (x) (add x 1))
(foo 41)
"""
        result2 = engine.execute(program2, recursion_lang)
        assert result2.status == "success"
        assert result2.value == 42


# =============================================================================
# RECURSION FUNCTION ARITIES
# =============================================================================

class TestRecursionFunctionArities:
    """Tests for recursive functions with different arities."""

    def test_recursive_function_multiple_params(self, engine, recursion_lang):
        """Test recursive function with multiple parameters.

        Tests that left-to-right evaluation order is preserved
        for multiple arguments. Each argument is evaluated before
        the function is invoked.
        """
        program = """
(def sum_with_acc (n acc)
  (if (eq n 0)
      acc
      (sum_with_acc (sub n 1) (add acc n))))
(sum_with_acc 10 0)
"""
        result = engine.execute(program, recursion_lang)

        assert result.status == "success"
        assert result.value == 55  # 1+2+3+...+10 = 55

    def test_recursive_function_with_conditionals(self, engine, recursion_lang):
        """Test recursive function with complex conditional logic.

        The conditional inside the recursive call should not affect
        the depth tracking.
        """
        program = """
(def sum_evens (n acc)
  (if (eq n 0)
      acc
      (if (eq (mod n 2) 0)
          (sum_evens (sub n 1) (add acc n))
          (sum_evens (sub n 1) acc))))
(sum_evens 10 0)
"""
        result = engine.execute(program, recursion_lang)

        assert result.status == "success"
        assert result.value == 30  # 2+4+6+8+10 = 30


# =============================================================================
# NESTED RECURSIVE CALLS
# =============================================================================

class TestRecursionNestedCalls:
    """Tests for nested recursive calls."""

    def test_mutual_recursion_simulation(self, engine, recursion_lang):
        """Test that nested calls work correctly.

        This tests that our evaluation properly handles nested
        function calls within recursion.
        """
        program = """
(def count_nested (n)
  (if (eq n 0)
      1
      (add 1 (count_nested (sub n 1)))))
(count_nested 20)
"""
        result = engine.execute(program, recursion_lang)

        assert result.status == "success"
        assert result.value == 21


# =============================================================================
# LEFT-TO-RIGHT ARGUMENT EVALUATION
# =============================================================================

class TestRecursionLeftToRightEvaluation:
    """Tests for left-to-right argument evaluation order."""

    def test_left_to_right_with_side_effects_like_operations(self, engine, recursion_lang):
        """Test that left operand is evaluated before right.

        In our implementation, both arguments are pre-evaluated before
        the function is invoked. This tests that order is preserved.

        For eval_left_first(3):
        - First, evaluate (add 3 100) = 103 (left)
        - Then, evaluate (eval_left_first 2) recursively (right)
        - Result: 103 + (102 + (101 + 0)) = 306
        """
        program = """
(def test_order (a b)
  (add a b))
(def eval_left_first (n)
  (if (eq n 0)
      0
      (test_order (add n 100) (eval_left_first (sub n 1)))))
(eval_left_first 3)
"""
        result = engine.execute(program, recursion_lang)

        assert result.status == "success"
        assert result.value == 306


# =============================================================================
# IMPLEMENTATION CONSIDERATIONS FOR FRAME-BASED EVALUATION
# =============================================================================

class TestFrameBasedEvaluationConsiderations:
    """Tests documenting implementation considerations for frame-based evaluation."""

    def test_context_bindings_are_immutably_updated(self, engine, recursion_lang):
        """Verify that function parameter bindings don't leak between calls.

        In frame-based evaluation, each recursive call should have its
        own scope for parameter bindings. The with_bindings() method
        creates a new dictionary, so bindings don't leak.

        Test: identity_test(10) should compute 1+2+...+10 = 55
        """
        program = """
(def identity_test (x)
  (if (eq x 0)
      0
      (add x (identity_test (sub x 1)))))
(identity_test 10)
"""
        result = engine.execute(program, recursion_lang)

        assert result.status == "success"
        assert result.value == 55

    def test_function_environment_isolation(self, engine, recursion_lang):
        """Verify that function definitions are properly isolated.

        Each function should maintain its own environment, and
        different functions can call themselves recursively
        independently.

        Hand derivation: outer(x) = x + outer(x-1), outer(0) = 0, so outer(5) = 15.
        inner(y) = y + inner(y-1), inner(0) = 115, so inner(5) = 5+4+3+2+1+115 = 130.
        outer(5) + inner(5) = 15 + 130 = 145. (115 is inner's BASE value, not inner(5).)
        """
        program = """
(def outer (x)
  (if (eq x 0)
      0
      (add x (outer (sub x 1)))))

(def inner (y)
  (if (eq y 0)
      115
      (add y (inner (sub y 1)))))

(add (outer 5) (inner 5))
"""
        result = engine.execute(program, recursion_lang)

        assert result.status == "success"
        # outer(5) = 15, inner(5) = 130, total = 145
        assert result.value == 145


# =============================================================================
# EDGE CASES
# =============================================================================

class TestRecursionEdgeCases:
    """Edge case tests for recursion."""

    def test_base_case_at_zero(self, engine, recursion_lang):
        """Test recursive function with base case at 0."""
        program = """
(def fact (n)
  (if (eq n 0)
      1
      (mul n (fact (sub n 1)))))
(fact 0)
"""
        result = engine.execute(program, recursion_lang)

        assert result.status == "success"
        assert result.value == 1

    def test_immediate_recursion_exceeds_limit(self, engine, recursion_lang):
        """Test that infinite recursion is properly detected.

        A function that calls itself immediately without reaching
        a base case should exceed the limit quickly.
        """
        program = """
(def infinite (n)
  (infinite n))
(infinite 0)
"""
        result = engine.execute(program, recursion_lang)

        # Should hit the limit quickly (within 100 calls)
        assert result.status == "recursion_limit_exceeded"

    def test_deep_but_valid_recursion(self, engine, recursion_lang):
        """Test recursion at various valid depths.

        With Python recursion limit ~1000, we can test depths up to ~900.
        The engine's max_call_depth=100 is the limiting factor for deeper recursion.
        """
        program = """
(def sum (n)
  (if (eq n 0)
      0
      (add n (sum (sub n 1)))))
(sum 50)
"""
        result = engine.execute(program, recursion_lang)

        assert result.status == "success"
        assert result.value == 1275  # 50*51/2


# =============================================================================
# COMPREHENSIVE REGRESSION TESTS
# =============================================================================

class TestRecursionRegressionSuite:
    """Comprehensive regression tests for recursion functionality."""

    def test_factorial_comprehensive(self, engine, recursion_lang):
        """Test factorial across multiple values.

        Regression test to ensure factorial works correctly at various depths.
        """
        program_template = """
(def factorial (n)
  (if (eq n 0)
      1
      (mul n (factorial (sub n 1)))))
(factorial {n})
"""

        test_cases = [
            (0, 1),
            (1, 1),
            (5, 120),
            (10, 3628800),
        ]

        for n, expected in test_cases:
            program = program_template.format(n=n)
            result = engine.execute(program, recursion_lang)
            assert result.status == "success", f"Factorial({n}) failed: {result.error_message}"
            assert result.value == expected, f"Factorial({n}) = {result.value}, expected {expected}"

    def test_fibonacci_basic(self, engine, recursion_lang):
        """Test basic fibonacci computation.

        Fibonacci(10) = 55
        This uses tree recursion, so the call count is exponential,
        but the depth is linear.
        """
        program = """
(def fibonacci (n)
  (if (eq n 0)
      0
      (if (eq n 1)
          1
          (add (fibonacci (sub n 1)) (fibonacci (sub n 2))))))
(fibonacci 10)
"""
        result = engine.execute(program, recursion_lang)

        assert result.status == "success"
        assert result.value == 55

    def test_nested_function_calls_no_recursion(self, engine, recursion_lang):
        """Test nested non-recursive function calls."""
        program = """
(def inc (x) (add x 1))
(def double (x) (add x x))
(def triple (x) (add (inc x) (double x)))
(triple 5)
"""
        result = engine.execute(program, recursion_lang)

        assert result.status == "success"
        assert result.value == 16

    def test_function_arity_errors(self, engine, recursion_lang):
        """Test that wrong argument counts produce errors."""
        program = """
(def two_args (a b) (add a b))
(two_args 1)
"""
        result = engine.execute(program, recursion_lang)

        assert result.status == "error"
        assert "arguments" in result.error_message.lower() or "arity" in result.error_message.lower()

    def test_function_arity_too_many(self, engine, recursion_lang):
        """Test that too many arguments produce errors."""
        program = """
(def one_arg (x) (add x 1))
(one_arg 1 2)
"""
        result = engine.execute(program, recursion_lang)

        assert result.status == "error"
        assert "arguments" in result.error_message.lower() or "arity" in result.error_message.lower()

    def test_self_recursion_exactly_at_limit(self, engine, recursion_lang):
        """Test self-recursion at exactly the depth limit.

        With frame-based evaluation, max_call_depth=100 means:
        - depth 1 (initial) to depth 100 (99th recursive call) → success
        - depth 101 (100th recursive call) → recursion_limit_exceeded

        at_limit(100) will try to call at_limit(99), ..., at_limit(0)
        At the point of calling at_limit(99), we're at depth 2
        At the point of calling at_limit(0), we're at depth 101

        So at_limit(100) should exceed the limit.
        """
        program = """
(def at_limit (n)
  (if (eq n 0)
      42
      (at_limit (sub n 1))))
(at_limit 100)
"""
        result = engine.execute(program, recursion_lang)

        # 100 recursive calls would hit depth 101
        # This should fail with recursion_limit_exceeded
        assert result.status == "recursion_limit_exceeded"

    def test_base_case_at_depth_100(self, engine, recursion_lang):
        """Test that base case at exactly depth 100 works.

        The limit is max_call_depth=100, meaning we can have
        up to 100 active invocations. A function that reaches
        depth 100 (99 recursive calls + 1 initial) should work.

        depth_100(99) → depth_100(98) → ... → depth_100(0)
        At peak: 100 active invocations (depth 1-100)
        """
        program = """
(def depth_100 (n)
  (if (eq n 0)
      999
      (depth_100 (sub n 1))))
(depth_100 99)
"""
        result = engine.execute(program, recursion_lang)

        # 99 recursive calls + 1 initial = 100, which equals the limit
        assert result.status == "success"
        assert result.value == 999

    def test_depth_101_failure_then_success(self, engine, recursion_lang):
        """Test depth-101 failure followed by independent success.

        This verifies that:
        1. A single deep recursion can trigger the limit
        2. The engine state is properly reset for subsequent executions
        """
        # First, trigger a depth-101 failure
        program_fail = """
(def fail_at_101 (n)
  (if (eq n 0)
      0
      (fail_at_101 (sub n 1))))
(fail_at_101 101)
"""
        result_fail = engine.execute(program_fail, recursion_lang)
        assert result_fail.status == "recursion_limit_exceeded"

        # Then, execute a successful independent function
        program_success = """
(def succeed (x) (add x 1))
(succeed 42)
"""
        result_success = engine.execute(program_success, recursion_lang)
        assert result_success.status == "success"
        assert result_success.value == 43


# =============================================================================
# INTEGRATION WITH ARITHMETIC MODES
# =============================================================================

class TestRecursionIntegrationWithArithmetic:
    """Recursion combined with arithmetic modes.

    Every program here stays within the 100-invocation call-depth limit: ``(f 98 ...)``
    makes invocations for n = 98 .. 0, i.e. 99 active at the base case. Expected values are
    derived from first principles (plain Python, below), not from the evaluator.
    """

    N = 98                       # 99 simultaneous invocations
    STEP = 10 ** 17              # 98 * 10**17 = 9.8e18 > INT64_MAX (9.223e18)

    @staticmethod
    def _wrap(x):
        """Reduce to signed 64-bit two's complement."""
        x &= (1 << 64) - 1
        return x - (1 << 64) if x >= (1 << 63) else x

    @staticmethod
    def _clamp(x):
        return max(MIN_INT64, min(MAX_INT64, x))

    @classmethod
    def _fold(cls, n, delta, reduce):
        acc = 0
        for _ in range(n):
            acc = reduce(acc + delta)
        return acc

    @staticmethod
    def _lang(mode):
        return LanguageGenerator().generate(LanguageSeed(
            name=f"{mode}RecLang", syntax_style="lisp", features=["recursion", "functions"],
            difficulty=2, arithmetic=mode, short_circuit=True))

    @staticmethod
    def _accumulate(op, delta, n):
        return (f"(def acc_rec (n acc)\n"
                f"  (if (eq n 0)\n"
                f"      acc\n"
                f"      (acc_rec (sub n 1) ({op} acc {delta}))))\n"
                f"(acc_rec {n} 0)")

    # ---- wraparound ------------------------------------------------------------------

    def test_wraparound_in_recursive_function(self, engine, recursion_lang):
        """98 additions of INT64_MAX under wraparound.

        98 * MAX = 98 * 2**63 - 98 = 49 * 2**64 - 98, which is congruent to -98 (mod 2**64),
        so the result is exactly -98. Without wrapping the sum would be ~9.0e20; with
        saturation it would be INT64_MAX; with error-on-overflow it would be an error.
        """
        assert self._fold(self.N, MAX_INT64, self._wrap) == -98          # the oracle itself
        result = engine.execute(self._accumulate("add", MAX_INT64, self.N), recursion_lang)
        assert result.status == "success"
        assert result.value == -98

    def test_wraparound_program_gives_different_results_in_other_modes(self):
        program = self._accumulate("add", MAX_INT64, self.N)
        saturating = ExecutionEngine().execute(program, self._lang("saturating"))
        assert (saturating.status, saturating.value) == ("success", MAX_INT64)
        overflow = ExecutionEngine().execute(program, self._lang("error-on-overflow"))
        assert overflow.status == "error" and "overflow" in overflow.error_message.lower()

    # ---- saturating ------------------------------------------------------------------

    def test_saturating_in_recursive_function(self, recursion_lang):
        """98 additions of 10**17 under saturating arithmetic.

        The unclamped sum is 98 * 10**17 = 9_800_000_000_000_000_000, which exceeds
        INT64_MAX = 9_223_372_036_854_775_807 by 576_627_963_145_224_193. The accumulator
        first overflows at the 93rd addition (92 * 10**17 still fits) and must then stay at
        INT64_MAX for the remaining five additions.
        """
        total = self.N * self.STEP
        assert total > MAX_INT64 and 92 * self.STEP < MAX_INT64 < 93 * self.STEP
        assert self._fold(self.N, self.STEP, self._clamp) == MAX_INT64    # the oracle itself
        result = ExecutionEngine().execute(
            self._accumulate("add", self.STEP, self.N), self._lang("saturating"))
        assert result.status == "success"
        assert result.value == MAX_INT64

    def test_saturating_negative_direction_clamps_to_int64_min(self):
        """98 subtractions of 10**17 from 0 under saturating arithmetic clamp at INT64_MIN."""
        assert self._fold(self.N, -self.STEP, self._clamp) == MIN_INT64
        result = ExecutionEngine().execute(
            self._accumulate("sub", self.STEP, self.N), self._lang("saturating"))
        assert (result.status, result.value) == ("success", MIN_INT64)

    def test_saturating_program_gives_different_results_in_other_modes(self):
        """Wraparound reduces mod 2**64; error-on-overflow fails. Neither equals INT64_MAX."""
        program = self._accumulate("add", self.STEP, self.N)
        wrapped = ExecutionEngine().execute(program, self._lang("wraparound"))
        assert wrapped.status == "success"
        assert wrapped.value == self._fold(self.N, self.STEP, self._wrap)
        assert wrapped.value == self._wrap(self.N * self.STEP) == -8_646_744_073_709_551_616
        assert wrapped.value != MAX_INT64
        overflow = ExecutionEngine().execute(program, self._lang("error-on-overflow"))
        assert overflow.status == "error" and "overflow" in overflow.error_message.lower()


# =============================================================================
# DEPTH-100 BOUNDARY VERIFICATION
# =============================================================================

class TestDepth100BoundaryVerification:
    """Tests to verify the depth-100 boundary behavior."""

    def test_98_at_100_depth_limit(self, engine, recursion_lang):
        """Test that 98 works within the 100 depth limit.

        recur(98) creates 98 recursive calls, so peak depth is 99
        (including the initial call). This should succeed.
        """
        program = """
(def recur (n)
  (if (eq n 0)
      0
      (recur (sub n 1))))
(recur 98)
"""
        result = engine.execute(program, recursion_lang)

        assert result.status == "success"
        assert result.value == 0

    def test_99_at_100_depth_limit(self, engine, recursion_lang):
        """Test that 99 works at the 100 depth limit.

        recur(99) creates 99 recursive calls, so peak depth is 100
        (including the initial call). This should succeed.
        """
        program = """
(def recur (n)
  (if (eq n 0)
      0
      (recur (sub n 1))))
(recur 99)
"""
        result = engine.execute(program, recursion_lang)

        assert result.status == "success"
        assert result.value == 0

    def test_100_exceeds_100_depth_limit(self, engine, recursion_lang):
        """Test that 100 exceeds the 100 depth limit.

        recur(100) creates 100 recursive calls, so peak depth is 101
        (including the initial call). This should fail.
        """
        program = """
(def recur (n)
  (if (eq n 0)
      0
      (recur (sub n 1))))
(recur 100)
"""
        result = engine.execute(program, recursion_lang)

        assert result.status == "recursion_limit_exceeded"
        assert "Call depth exceeded" in result.error_message
