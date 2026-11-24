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
  - strict types, no coercion: arithmetic takes int operands; `and`, `or`, `not` and `if` take
    bool; `eq` returns false for values of different types. A type error has status `error`
    and is raised when the operation runs.
- **Execution.** `ExecutionEngine` (`src/execution/engine.py`) is the public entry point. It is a
  thin facade over `IterativeEvaluator` (`src/execution/iterative_evaluator.py`), which evaluates
  with an explicit frame stack, so user-function calls never use Python recursion. Functions use
  **lexical scoping**: a function body sees only its own parameters.
- **Independent reference evaluator.** `ReferenceEvaluator` (`src/oracle/reference_evaluator.py`) is a
  separate, deliberately simple recursive interpreter used as a test oracle. It shares only data
  types (`src/execution/types.py`) with the production path, and importing it loads no production
  execution module. It is for differential testing of small programs, not for production use.
- **Deterministic resource limits**, each enforced independently and configurable per engine
  (`ExecutionEngine(max_steps=..., max_ast_depth=..., max_call_depth=...)`):
  - *AST depth* (default 1,000): validated statically before execution, including uncalled
    function bodies and unselected `if` branches.
  - *Execution steps* (default 100,000): one step per expression node actually evaluated.
  - *Call depth* (default 100): active user-function invocations (100 allowed, 101 rejected).

## Known limitations

- **Not a security sandbox.** The interpreters bound steps, expression depth and call depth,
  but they run in the same Python process as the caller with no isolation of memory, CPU time,
  or the host. Do not use them to run untrusted code in a security-sensitive setting. The
  `sandbox/` directory is an empty placeholder.
- AST depth is checked after parsing, so a very large input still costs parse time before it is
  rejected (measured as roughly linear: an 8,000-level, 64 KB input took about 1.6 s).
- Parse errors are reported with status `error`, not `invalid_program`.
- The `ReferenceEvaluator` uses Python recursion: measured at 75 nested user-function calls under
  Python's default recursion limit (fewer when called from a deep stack such as a test runner).
- The command-line entry point (`src/cli.py`) is a placeholder: it prints a usage banner and
  does not run any command.

## Planned (not yet implemented)

These appear in the design documents under `.kiro/specs/unknownlang/` but have no code yet:
challenge generation, a challenge-level test oracle (the `ReferenceEvaluator` is only its
evaluation core), model adapters, benchmark scoring and metrics,
a FastAPI backend, a React + Vite frontend, and SQLite persistence. FastAPI, uvicorn and httpx
are declared in `pyproject.toml` but are not used by any current code.

A proposed benchmark architecture for these items is in `docs/architecture/` (start with
`wave2-overview.md`). It is a design only, **not yet approved**, and it differs from the list above in
places: it proposes plain files in place of SQLite and defers the API and frontend. It also reports
runtime findings that are not fixed (`runtime-findings.md`).

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
from src.execution import ExecutionEngine

seed = LanguageSeed(
    name="Demo", syntax_style="lisp", features=["arithmetic", "functions"],
    difficulty=1, arithmetic="wraparound", short_circuit=True,
)
spec = LanguageGenerator().generate(seed)
result = ExecutionEngine().execute("(add 1 (mul 2 3))", spec)
print(result.status, result.value)   # success 7

# Resource limits are optional keyword arguments (None = default):
strict = ExecutionEngine(max_steps=2)
print(strict.execute("(add 1 2)", spec).status)   # step_limit_exceeded
```

## Testing

```bash
python -m pytest
```

Run from the repository root. See [RELEASES.md](RELEASES.md) for the state of each milestone.

## License

[MIT](LICENSE) © 2026 Anurag Jaiswal
