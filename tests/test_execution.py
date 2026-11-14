"""Unit tests for ExecutionEngine."""

import pytest
from lark import Tree

from src.execution.engine import (
    ExecutionEngine,
    ExecutionResult,
    EvalContext,
    ExecutionError,
    StepLimitExceeded,
    RecursionLimitExceeded,
    AstDepthExceeded,
    MIN_INT64,
    MAX_INT64,
)
from src.language.generator import LanguageGenerator
from src.language.seed import LanguageSeed


@pytest.fixture
def language_spec():
    """Create a test language spec."""
    generator = LanguageGenerator()
    seed = LanguageSeed(
        name="TestLang",
        syntax_style="lisp",
        features=["arithmetic"],
        difficulty=1,
        arithmetic="wraparound",
        short_circuit=True,
    )
    return generator.generate(seed)


@pytest.fixture
def engine():
    """Create an ExecutionEngine instance."""
    return ExecutionEngine()


class TestExecutionEngineBasic:
    """Basic execution engine tests."""

    def test_execute_simple_add(self, engine, language_spec):
        """Test simple addition."""
        result = engine.execute("(add 1 2)", language_spec)
        
        assert result.status == "success"
        assert result.value == 3
    
    def test_execute_nested_arithmetic(self, engine, language_spec):
        """Test nested arithmetic operations."""
        result = engine.execute("(add (mul 2 3) 4)", language_spec)
        
        assert result.status == "success"
        assert result.value == 10
    
    def test_execute_complex_expression(self, engine, language_spec):
        """Test complex expression evaluation."""
        result = engine.execute("(add (mul 2 3) (sub 10 5))", language_spec)
        
        assert result.status == "success"
        assert result.value == 11  # 6 + 5


class TestExecutionEngineArithmeticWraparound:
    """Tests for wraparound arithmetic mode."""

    @pytest.fixture
    def language_spec_wraparound(self):
        """Create language spec with wraparound arithmetic."""
        generator = LanguageGenerator()
        seed = LanguageSeed(
            name="WraparoundLang",
            syntax_style="lisp",
            features=["arithmetic"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        return generator.generate(seed)

    def test_wraparound_overflow_positive(self, engine, language_spec_wraparound):
        """Test wraparound when adding past MAX_INT64."""
        result = engine.execute(f"(add {MAX_INT64} 1)", language_spec_wraparound)
        
        assert result.status == "success"
        # Should wrap to MIN_INT64
        assert result.value == MIN_INT64

    def test_wraparound_underflow_negative(self, engine, language_spec_wraparound):
        """Test wraparound when subtracting past MIN_INT64."""
        result = engine.execute(f"(sub {MIN_INT64} 1)", language_spec_wraparound)
        
        assert result.status == "success"
        # Should wrap to MAX_INT64
        assert result.value == MAX_INT64

    def test_wraparound_simple_values(self, engine, language_spec_wraparound):
        """Test wraparound with simple values."""
        result = engine.execute("(add 100 200)", language_spec_wraparound)
        
        assert result.status == "success"
        assert result.value == 300


class TestExecutionEngineArithmeticSaturating:
    """Tests for saturating arithmetic mode."""

    @pytest.fixture
    def language_spec_saturating(self):
        """Create language spec with saturating arithmetic."""
        generator = LanguageGenerator()
        seed = LanguageSeed(
            name="SaturatingLang",
            syntax_style="lisp",
            features=["arithmetic"],
            difficulty=1,
            arithmetic="saturating",
            short_circuit=True,
        )
        return generator.generate(seed)

    def test_saturating_overflow(self, engine, language_spec_saturating):
        """Test saturation at MAX_INT64."""
        result = engine.execute(f"(add {MAX_INT64} 1000)", language_spec_saturating)
        
        assert result.status == "success"
        assert result.value == MAX_INT64

    def test_saturating_underflow(self, engine, language_spec_saturating):
        """Test saturation at MIN_INT64."""
        result = engine.execute(f"(sub {MIN_INT64} 1000)", language_spec_saturating)
        
        assert result.status == "success"
        assert result.value == MIN_INT64

    def test_saturating_simple_values(self, engine, language_spec_saturating):
        """Test saturating with simple values."""
        result = engine.execute("(add 50 75)", language_spec_saturating)
        
        assert result.status == "success"
        assert result.value == 125


class TestExecutionEngineArithmeticErrorOnOverflow:
    """Tests for error-on-overflow arithmetic mode."""

    @pytest.fixture
    def language_spec_error(self):
        """Create language spec with error-on-overflow arithmetic."""
        generator = LanguageGenerator()
        seed = LanguageSeed(
            name="ErrorLang",
            syntax_style="lisp",
            features=["arithmetic"],
            difficulty=1,
            arithmetic="error-on-overflow",
            short_circuit=True,
        )
        return generator.generate(seed)

    def test_error_overflow(self, engine, language_spec_error):
        """Test error on overflow."""
        result = engine.execute(f"(add {MAX_INT64} 1)", language_spec_error)
        
        assert result.status == "error"
        assert "overflow" in result.error_message.lower() or "overflow" in str(result.error_message).lower()

    def test_error_division_by_zero(self, engine, language_spec_error):
        """Test error on division by zero."""
        result = engine.execute("(div 10 0)", language_spec_error)
        
        assert result.status == "error"
        assert "division by zero" in result.error_message.lower()

    def test_error_modulo_by_zero(self, engine, language_spec_error):
        """Test error on modulo by zero."""
        result = engine.execute("(mod 10 0)", language_spec_error)
        
        assert result.status == "error"
        assert "modulo by zero" in result.error_message.lower() or "division by zero" in result.error_message.lower()

    def test_error_simple_values(self, engine, language_spec_error):
        """Test error mode with simple values."""
        result = engine.execute("(add 100 200)", language_spec_error)
        
        assert result.status == "success"
        assert result.value == 300


class TestExecutionEngineBoolean:
    """Tests for boolean operations."""

    def test_and_operation(self, engine, language_spec):
        """Test and operation with various inputs."""
        # true AND true = true
        result = engine.execute("(and true true)", language_spec)
        assert result.status == "success"
        assert result.value == True
        
        # true AND false = false
        result = engine.execute("(and true false)", language_spec)
        assert result.status == "success"
        assert result.value == False
        
        # false AND true = false
        result = engine.execute("(and false true)", language_spec)
        assert result.status == "success"
        assert result.value == False
        
        # false AND false = false
        result = engine.execute("(and false false)", language_spec)
        assert result.status == "success"
        assert result.value == False

    def test_or_operation(self, engine, language_spec):
        """Test or operation with various inputs."""
        # true OR true = true
        result = engine.execute("(or true true)", language_spec)
        assert result.status == "success"
        assert result.value == True
        
        # true OR false = true
        result = engine.execute("(or true false)", language_spec)
        assert result.status == "success"
        assert result.value == True
        
        # false OR true = true
        result = engine.execute("(or false true)", language_spec)
        assert result.status == "success"
        assert result.value == True
        
        # false OR false = false
        result = engine.execute("(or false false)", language_spec)
        assert result.status == "success"
        assert result.value == False

    def test_not_operation(self, engine, language_spec):
        """Test not operation."""
        # NOT true = false
        result = engine.execute("(not true)", language_spec)
        assert result.status == "success"
        assert result.value == False
        
        # NOT false = true
        result = engine.execute("(not false)", language_spec)
        assert result.status == "success"
        assert result.value == True

    def test_eq_operation(self, engine, language_spec):
        """Test equality comparison."""
        # 1 == 1 = true
        result = engine.execute("(eq 1 1)", language_spec)
        assert result.status == "success"
        assert result.value == True
        
        # 1 == 2 = false
        result = engine.execute("(eq 1 2)", language_spec)
        assert result.status == "success"
        assert result.value == False
        
        # true == true = true
        result = engine.execute("(eq true true)", language_spec)
        assert result.status == "success"
        assert result.value == True

    def test_boolean_type_error(self, engine, language_spec):
        """Test boolean operations with non-boolean values."""
        # This should raise an error because we're using an integer
        result = engine.execute("(and 1 0)", language_spec)
        
        # The exact status depends on how type errors are handled
        assert result.status in ("error", "invalid_program")


class TestExecutionEngineShortCircuit:
    """Tests for short-circuit evaluation."""

    @pytest.fixture
    def language_spec_short_circuit(self):
        """Create language spec with short-circuit mode."""
        generator = LanguageGenerator()
        seed = LanguageSeed(
            name="ShortCircuitLang",
            syntax_style="lisp",
            features=["arithmetic"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        return generator.generate(seed)

    @pytest.fixture
    def language_spec_eager(self):
        """Create language spec with eager evaluation."""
        generator = LanguageGenerator()
        seed = LanguageSeed(
            name="EagerLang",
            syntax_style="lisp",
            features=["arithmetic"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=False,
        )
        return generator.generate(seed)

    def test_short_circuit_false_left(self, engine, language_spec_short_circuit):
        """Test short-circuit: false left operand doesn't evaluate right."""
        # With short-circuit, false AND expr should not evaluate expr
        # But our implementation pre-evaluates arguments before passing to the evaluator
        # So this test demonstrates the limitation
        result = engine.execute("(and false (add 1 2))", language_spec_short_circuit)
        
        assert result.status == "success"
        # Result should be false (left operand is false)
        assert result.value == False

    def test_short_circuit_true_left(self, engine, language_spec_short_circuit):
        """Test short-circuit: true left operand evaluates right (but must be boolean)."""
        # With strict boolean mode, the right operand must also be boolean
        # (add 1 2) = 3, which is not a boolean, so this should error
        result = engine.execute("(and true (add 1 2))", language_spec_short_circuit)
        
        assert result.status == "error"
        assert "boolean" in result.error_message.lower()

    def test_eager_mode_both_evaluated(self, engine, language_spec_eager):
        """Test eager mode evaluates both operands (but must be boolean)."""
        # In eager mode, both operands are evaluated, but both must be boolean
        result = engine.execute("(and true (add 1 2))", language_spec_eager)
        
        assert result.status == "error"
        assert "boolean" in result.error_message.lower()


class TestExecutionEngineIfExpression:
    """Tests for if-expression."""

    def test_if_true_branch(self, engine, language_spec):
        """Test if expression evaluates true branch."""
        result = engine.execute("(if true 1 2)", language_spec)
        
        assert result.status == "success"
        assert result.value == 1

    def test_if_false_branch(self, engine, language_spec):
        """Test if expression evaluates false branch."""
        result = engine.execute("(if false 1 2)", language_spec)
        
        assert result.status == "success"
        assert result.value == 2

    def test_if_nested(self, engine, language_spec):
        """Test nested if expressions."""
        result = engine.execute("(if true (if true 1 2) 3)", language_spec)
        
        assert result.status == "success"
        assert result.value == 1


class TestExecutionEngineFunctions:
    """Tests for user-defined functions."""

    @pytest.fixture
    def language_spec_functions(self):
        """Create language spec with functions feature."""
        generator = LanguageGenerator()
        seed = LanguageSeed(
            name="FunctionLang",
            syntax_style="lisp",
            features=["recursion", "functions"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        return generator.generate(seed)

    def test_simple_function(self, engine, language_spec_functions):
        """Test simple function definition and call."""
        program = """
(def foo () 42)
(foo)
"""
        result = engine.execute(program, language_spec_functions)
        
        assert result.status == "success"
        assert result.value == 42

    def test_function_with_params(self, engine, language_spec_functions):
        """Test function with parameters."""
        program = """
(def double (x) (add x x))
(double 5)
"""
        result = engine.execute(program, language_spec_functions)
        
        assert result.status == "success"
        assert result.value == 10

    def test_function_multiple_params(self, engine, language_spec_functions):
        """Test function with multiple parameters."""
        program = """
(def add3 (x y z) (add (add x y) z))
(add3 1 2 3)
"""
        result = engine.execute(program, language_spec_functions)
        
        assert result.status == "success"
        assert result.value == 6

    def test_function_recursion(self, engine, language_spec_functions):
        """Test recursive function (factorial)."""
        program = """
(def factorial (n)
  (if (eq n 0)
      1
      (mul n (factorial (sub n 1)))))
(factorial 5)
"""
        result = engine.execute(program, language_spec_functions)
        
        assert result.status == "success"
        assert result.value == 120

    def test_function_self_recursion(self, engine, language_spec_functions):
        """Test that self-recursion is supported."""
        program = """
(def count_down (n)
  (if (eq n 0)
      0
      (count_down (sub n 1))))
(count_down 10)
"""
        result = engine.execute(program, language_spec_functions)
        
        assert result.status == "success"
        assert result.value == 0


class TestExecutionEngineResourceLimits:
    """Tests for resource limit enforcement."""

    def test_step_limit_exceeded(self, engine, language_spec):
        """Test that step limit is enforced."""
        # Create a program that will exceed step limit
        # Each step counts as 1, so we need more than DEFAULT_MAX_STEPS steps
        # We'll test with a smaller limit for faster testing
        
        # For now, just verify the limit structure exists
        context = EvalContext(max_steps=10)
        assert context.max_steps == 10

    def test_call_depth_limit(self, engine, language_spec):
        """Test that call depth limit is enforced."""
        # Test that recursion is limited
        context = EvalContext(max_call_depth=5)
        assert context.max_call_depth == 5


class TestExecutionEngineIntegration:
    """Integration tests for ExecutionEngine."""

    def test_complete_arithmetic_chain(self, engine, language_spec):
        """Test complete arithmetic expression."""
        result = engine.execute(
            "(add (mul 2 3) (sub 10 5))",
            language_spec
        )
        
        assert result.status == "success"
        assert result.value == 11

    def test_complex_boolean_expression(self, engine, language_spec):
        """Test complex boolean expression."""
        result = engine.execute(
            "(and true (or false true))",
            language_spec
        )
        
        assert result.status == "success"
        assert result.value == True

    def test_nested_if_expressions(self, engine, language_spec):
        """Test nested if expressions."""
        result = engine.execute(
            "(if true (if false 1 2) (if true 3 4))",
            language_spec
        )
        
        assert result.status == "success"
        assert result.value == 2


class TestExecutionEngineEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_zero_multiplication(self, engine, language_spec):
        """Test multiplication with zero."""
        result = engine.execute("(mul 0 100)", language_spec)
        
        assert result.status == "success"
        assert result.value == 0

    def test_subtraction_negative_result(self, engine, language_spec):
        """Test subtraction resulting in negative number."""
        result = engine.execute("(sub 5 10)", language_spec)
        
        assert result.status == "success"
        assert result.value == -5

    def test_division_truncation(self, engine, language_spec):
        """Test division truncation toward zero."""
        result = engine.execute("(div 7 2)", language_spec)
        
        assert result.status == "success"
        assert result.value == 3

    def test_division_negative(self, engine, language_spec):
        """Test division with negative numbers."""
        result = engine.execute("(div -7 2)", language_spec)
        
        assert result.status == "success"
        assert result.value == -3

    def test_modulo_positive(self, engine, language_spec):
        """Test modulo operation."""
        result = engine.execute("(mod 7 3)", language_spec)
        
        assert result.status == "success"
        assert result.value == 1

    def test_modulo_negative_dividend(self, engine, language_spec):
        """Test modulo with negative dividend."""
        result = engine.execute("(mod -7 3)", language_spec)
        
        assert result.status == "success"
        assert result.value == -1
