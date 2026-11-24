# UnknownLang

Adaptive AI reasoning benchmark platform that evaluates whether AI models can learn and reason within previously unseen, procedurally generated programming languages.

> **Status: early development / research prototype.** The language generator and two
> interpreters exist. The benchmark, scoring, API and UI described under
> [Planned](#planned-not-yet-implemented) do **not** exist yet.

## Overview

UnknownLang aims to generate controlled programming-language environments, give their
specifications to AI models, run the programs the models write on independent deterministic
interpreters, and measure how well the models generalize beyond the examples they were given.

## What works today

- **Procedural language generation.** A `LanguageSeed` (name, syntax style, features,
  difficulty, arithmetic mode, short-circuit mode) deterministically produces a
  `LanguageSpec`: a Lark grammar, semantics and a stable language identity. The same seed
  always produces the same artifacts.
  - Only the `lisp` syntax style generates a grammar. The seed validator accepts other
    style names, but the grammar builder rejects them.
- **Language semantics.** Built-in operations `add`, `sub`, `mul`, `div`, `mod`, `and`, `or`,
  `not`, `eq`, `if`, plus user-defined functions (`def`), with:
  - signed 64-bit integers and three overflow modes: wraparound, saturating, error-on-overflow
  - division truncating toward zero
  - strict boolean operands, with short-circuit or eager `and` / `or`
- **Two interpreters** (they share the language definitions but not evaluation code):
  - `ExecutionEngine` (`src/execution/engine.py`): the recursive interpreter.
  - `IterativeEvaluator` (`src/execution/iterative_evaluator.py`): a standalone evaluator that
    uses an explicit frame stack, so user-function calls do not use Python recursion. It is
    **not yet wired into** `ExecutionEngine` or the CLI.
- **Deterministic resource limits** in `IterativeEvaluator`, each enforced independently:
  - *AST depth*: validated statically before execution, including uncalled function bodies
    and unselected `if` branches.
  - *Execution steps*: one step per expression node actually evaluated.
  - *Call depth*: active user-function invocations (100 allowed, 101 rejected).

## Known limitations

- **Not a security sandbox.** The interpreters bound steps, expression depth and call depth,
  but they run in the same Python process as the caller with no isolation of memory, CPU time,
  or the host. Do not use them to run untrusted code in a security-sensitive setting. The
  `sandbox/` directory is an empty placeholder.
- `ExecutionEngine` uses Python recursion for user functions, so deep recursion can hit Python's
  recursion limit before the language's 100-call limit. `IterativeEvaluator` does not have this
  problem; integrating it into production is pending.
- `ExecutionEngine` returns `2**63` for `INT64_MIN / -1` in wraparound and saturating modes, which is
  outside signed 64-bit range. `IterativeEvaluator` returns the correct result for each mode.
- The two interpreters count execution steps differently, so step budgets are not interchangeable.
- The command-line entry point (`src/cli.py`) is a placeholder: it prints a usage banner and
  does not run any command.

## Planned (not yet implemented)

These appear in the design documents under `.kiro/specs/unknownlang/` but have no code yet:
challenge generation, an independent test oracle, model adapters, benchmark scoring and metrics,
a FastAPI backend, a React + Vite frontend, and SQLite persistence. FastAPI, uvicorn and httpx
are declared in `pyproject.toml` but are not used by any current code.

## Getting started

Requires Python 3.11 or newer (`pyproject.toml`). Development and tests have been run on Python 3.14.

```bash
git clone https://github.com/anurag-jaiswal-aj/UnknownLang.git
cd UnknownLang
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Generate a language and run a program:

```python
from src.language.generator import LanguageGenerator
from src.language.seed import LanguageSeed
from src.execution.iterative_evaluator import IterativeEvaluator

seed = LanguageSeed(
    name="Demo", syntax_style="lisp", features=["arithmetic", "functions"],
    difficulty=1, arithmetic="wraparound", short_circuit=True,
)
spec = LanguageGenerator().generate(seed)
result = IterativeEvaluator().execute("(add 1 (mul 2 3))", spec)
print(result.status, result.value)   # success 7
```

## Testing

```bash
python -m pytest
```

Run from the repository root. See [RELEASES.md](RELEASES.md) for the state of each milestone.

## License

[MIT](LICENSE) © 2026 Anurag Jaiswal
