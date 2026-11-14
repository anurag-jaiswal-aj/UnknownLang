"""Execution engine for UnknownLang.

This package provides the production ExecutionEngine for parsing and
evaluating programs in generated UnknownLang languages.
"""

from .engine import ExecutionEngine, ExecutionResult

__all__ = ["ExecutionEngine", "ExecutionResult"]
