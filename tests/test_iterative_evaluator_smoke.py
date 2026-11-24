"""Smoke test for IterativeEvaluator.

This test verifies that the standalone iterative evaluator can execute
a simple expression without hanging.

DO NOT use python -c or multiline shell commands to execute this.
Run only with: ./venv/bin/python -m pytest tests/test_iterative_evaluator_smoke.py -q
"""

import pytest

from src.execution.iterative_evaluator import IterativeEvaluator
from src.language.generator import LanguageGenerator
from src.language.seed import LanguageSeed


def test_simple_addition():
    """Test that the evaluator can execute a simple addition expression."""
    # Generate a language spec
    generator = LanguageGenerator()
    seed = LanguageSeed(
        name="TestLang",
        syntax_style="lisp",
        features=["arithmetic"],
        difficulty=1,
        arithmetic="wraparound",
        short_circuit=True,
    )
    spec = generator.generate(seed)
    
    # Create the evaluator
    evaluator = IterativeEvaluator()
    
    # Execute a simple addition
    result = evaluator.execute("(add 1 2)", spec)
    
    # Verify the result
    assert result.status == "success", f"Expected success, got {result.status}: {result.error_message}"
    assert result.value == 3, f"Expected 3, got {result.value}"


def test_simple_if_expression():
    """Test that the evaluator can execute a simple if expression."""
    generator = LanguageGenerator()
    seed = LanguageSeed(
        name="TestLang",
        syntax_style="lisp",
        features=["arithmetic"],
        difficulty=1,
        arithmetic="wraparound",
        short_circuit=True,
    )
    spec = generator.generate(seed)
    
    evaluator = IterativeEvaluator()
    result = evaluator.execute("(if true 42 99)", spec)
    
    assert result.status == "success"
    assert result.value == 42
