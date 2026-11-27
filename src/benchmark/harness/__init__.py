"""M2.6 Benchmark Evaluation Harness.

Provides the deterministic evaluation harness that accepts a generated task,
its environment, and a model response, then produces a structured and reproducible
evaluation outcome.

The harness is a pure function: given the same inputs, it always produces identical outputs.
It does NOT call models, write storage, or have side effects.

M2.6 supports only EVAL, SYN, INF, CTRL (value-answer tasks).
Program tasks (REC, CONS, ERR) are explicitly unsupported.
"""

from src.benchmark.harness.types import AttemptOutcome
from src.benchmark.harness.evaluate import evaluate

__all__ = ["AttemptOutcome", "evaluate"]
