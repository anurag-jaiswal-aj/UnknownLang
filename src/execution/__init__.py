"""Execution package for UnknownLang.

Public API: ``ExecutionEngine`` and ``ExecutionResult``.

Exports are resolved lazily (PEP 562). Importing a submodule such as
``src.execution.types`` therefore does NOT import the engine or the iterative evaluator,
which keeps the independent reference evaluator (``src.oracle``) free of production
execution modules. ``from src.execution import ExecutionEngine, ExecutionResult`` works
exactly as before.
"""

from __future__ import annotations

from typing import Any

__all__ = ["ExecutionEngine", "ExecutionResult"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from . import engine

        return getattr(engine, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(list(globals()) + __all__)
