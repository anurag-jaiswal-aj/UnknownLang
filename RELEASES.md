# Release Ledger

Milestones in reverse chronological order. Each entry states what was verified and what was not.

## Wave 1C.14 — Production integration of the iterative evaluator

- **Branch:** `main` (published; `fix/wave1c-correction` is kept as history)
- **Status:** `ExecutionEngine` now runs on the iterative evaluator. The previous recursive
  interpreter is preserved as an independent reference evaluator. The full repository suite
  passes.

### Commits (in order)

| Commit | Change |
|---|---|
| `338f307` | `src/execution/types.py` (shared types), lazy `src/execution/__init__.py` |
| `9bf199d` | validated `max_steps` / `max_ast_depth` / `max_call_depth` constructor arguments |
| `e9d224d` | extract the recursive interpreter to `src/oracle/reference_evaluator.py` (behavior-neutral) |
| `d3306c7` | reference evaluator: canonical `INT64_MIN / -1` and lexical scoping |
| `c5573c1` | `ExecutionEngine` becomes a facade over `IterativeEvaluator` |
| `c658eaa` | recursion-boundary tests committed, with three corrected expectations |
| `e6f6625` | facade, lexical-scoping and reference-independence tests |
| `16f0114` | docs: lexical scoping added as Requirement 7, criterion 8 |
| `1f58b50` | structural proof that the production path has no method recursion |

This ledger entry and the README update are committed after the commits above.

### Architecture

- `src/execution/types.py`: `ExecutionResult`, the exception hierarchy, signed 64-bit bounds and
  default limits. It imports **no project modules**.
- `src/execution/iterative_evaluator.py`: the evaluator and its `EvalContext` (step charging
  stays here). Imports `types.py`.
- `src/execution/engine.py`: compatibility facade; imports the evaluator and `types.py`.
  `ExecutionEngine()` and every previously importable name still work and are the **same objects**
  as in `types.py`.
- `src/oracle/reference_evaluator.py`: independent recursive oracle. It may import
  `src.execution.types`, `src.language.*`, Lark and the standard library, and must **not** import
  `engine.py`, `iterative_evaluator.py` or any production execution helper. It shares data types
  only. Importing it loads no production execution module (enforced by tests).
- `src/execution/__init__.py` resolves its exports lazily, so importing a submodule does not load
  the engine.

### Behavior changes

1. **Lexical scoping.** A function body sees only its own parameters. The old engine let a callee
   read its caller's variables (an accidental dynamic scope: it captured a definition-time
   environment and never read it). Programs relying on that now fail with `Unknown identifier`.
2. **Recursion works to the limit.** 100 simultaneous user-function invocations succeed and the
   101st returns `recursion_limit_exceeded`. Previously most such programs failed with a Python
   `RecursionError` (`status="error"`).
3. **AST depth is enforced** (default 1,000) and reported as `ast_depth_exceeded`, validated
   statically before execution, including uncalled function bodies. It was previously not enforced.
4. **Semantic step counting.** One step per expression node actually evaluated. The previous
   engine made about 4x as many increments per node (measured 3.7x to 4.2x on six programs), so a
   given `max_steps` now buys roughly four times as much evaluation. The old counter was also
   unreliable as a cumulative budget: it lived on contexts that are copied by value, and the
   top-level context's `steps` stayed 0 after a run.
5. **Call depth counts after arguments are evaluated**, so `(id (id (id 1)))` peaks at depth 1.
   The old engine counted depth before arguments (peak 3).
6. **Error text:** the call-depth message is now `Call depth exceeded: N >= M` (was `N > M`).
7. **`INT64_MIN / -1`** in the reference evaluator now returns `INT64_MIN` (wraparound) or
   `INT64_MAX` (saturating), or reports overflow; it previously returned `2**63`.
8. **Constructor limits:** `ExecutionEngine(*, max_steps=None, max_ast_depth=None,
   max_call_depth=None)`; `None` means the default; values must be `int >= 0` (`bool` and non-int
   raise `TypeError`, negatives `ValueError`). Defaults live in one place.
9. The module's script-mode self-test in `engine.py` was removed with the old implementation.

### Test corrections

Of the 14 tests that failed on the old engine, 11 pass unchanged. Three were wrong and were
corrected: the environment-isolation test expected 130 but the value is **145** (15 + 130; 115 is
`inner`'s base value); the wraparound and saturating recursion tests needed 1,001 and 101
invocations (limit 100), and the saturating one never reached INT64_MAX. They now use 99
invocations and expect exactly `-98`, `INT64_MAX` and `INT64_MIN`, each derived by hand.

### Verification (real exit codes, `.venv`, Python 3.14)

| Command | Result | Exit |
|---|---|---|
| Standalone evaluator suites (6 files) | 402 passed | 0 |
| Production test files (`test_execution`, `test_execution_integration`, `test_recursion_boundary`) | 97 passed | 0 |
| Full suite (`python -m pytest`) | **809 passed** | 0 |

Mutation checks (defects injected in memory, never written to disk): constructor tests 9/9
caught; reference corrections 5/5; arithmetic mutations against the recursion tests 4/4
(3 distinct arithmetic mutations were used in an earlier check against 5 scenarios, so that
earlier "five mutations" wording was a miscount); production arithmetic defects against the
differential tests 5/5; facade defects 7/7. Differential tests compare `ExecutionEngine` with the
oracle on a hand corpus and 900 seeded random programs (764 success, 136 error) in all six
arithmetic/boolean configurations, with no mismatches. The lazy-package and import-hygiene
tests run in fresh subprocesses, so they were verified by passing, not by in-memory mutation.

### Known limitations and deferred work

- **Not a security sandbox**; process-level isolation is required for untrusted code.
- AST depth is validated after parsing, so oversized input still costs parse time first
  (roughly linear; an 8,000-level, 64 KB input took about 1.6 s to reject).
- Integer literals outside the signed 64-bit range (for example `9223372036854775808`) are
  accepted by both evaluators; only arithmetic results are wrapped, saturated or reported.
- Parse errors return `error`, not the `invalid_program` status listed in the requirements.
- `SemanticSpec` does not carry `scoping`, `evaluation_order` or `type_coercion` fields that
  Requirement 6.3 asks for; lexical scoping is a fixed MVP behavior, not a spec field.
- The reference evaluator uses Python recursion: measured at 75 nested user calls under the
  default recursion limit. It has no AST-depth enforcement and its legacy step counters are not the
  canonical contract; compare status and value only.
- `src/execution/types.py` shadows the standard-library `types` if a module in that directory is
  run as a script; use `python -m`.
- `src/cli.py` remains a placeholder. A local, uncommitted edit to
  `.kiro/specs/unknownlang/tasks.md` is intentionally not part of this release.

## Wave 1C.13.4 — Standalone IterativeEvaluator

- **Commit:** `4ef1bba9fed04e1e75ec7d3bce12a29a8ab62ae3` (`feat(execution): add standalone iterative evaluator`)
- **Branch:** `fix/wave1c-correction`
- **Status:** standalone component. **Production integration is pending**: `ExecutionEngine`
  and the CLI do not use it.

### Files in the commit (6)

- `src/execution/iterative_evaluator.py`
- `tests/test_iterative_evaluator_resource_limits.py`
- `tests/test_iterative_evaluator_contract.py`
- `tests/test_iterative_evaluator_boolean.py`
- `tests/test_iterative_evaluator_lifecycle.py`
- `tests/test_iterative_evaluator_smoke.py`

### Verification

| Check | Result |
|---|---|
| Standalone evaluator suite (the 5 test files above) | **342 passed, 2 xfailed**, exit code 0 |
| The 2 xfails | Strict; they document a known `ExecutionEngine` defect (below) |

This ledger does **not** claim that the whole repository passes: the standalone suite above is
the only suite verified for this milestone.

### Contract implemented

- **Execution steps (semantic expression-node counting).** One step per `literal`, `call` or
  `if_expr` node actually evaluated, charged before evaluation. Grammar wrappers, evaluator
  frames and function entry/return bookkeeping are free. A failed node still costs its step;
  an attempt rejected because the budget is exhausted does not. Unselected `if` branches and
  short-circuited operands cost nothing.
- **Iterative static AST-depth validation.** Runs before execution, with an explicit worklist
  and no Python recursion. Every top-level expression and every `def` body (called or not) is
  an independent root at depth 1; both `if` branches and both short-circuit operands count.
  `max_ast_depth` is accepted, `max_ast_depth + 1` is rejected with `ast_depth_exceeded`.
- **Explicit function call-depth enforcement.** Counts active user-function invocations
  (built-ins excluded); 100 are allowed and the 101st fails with `recursion_limit_exceeded`.
  Call depth and variable bindings are restored on return and on every failure path.
- **Signed 64-bit arithmetic boundaries.** Permanent tests for `INT64_MIN / -1` in all three
  overflow modes (wraparound gives `INT64_MIN`, saturating gives `INT64_MAX`, error-on-overflow
  reports an overflow error), plus truncating division and remainder with negative operands.
- **Decided semantics.** Empty source returns `success` with `value=None`; `(nope 1)` costs
  exactly two steps, then fails function resolution.

### Known limitations

- *(Resolved in Wave 1C.14; see above.)* **`ExecutionEngine` still uses Python recursion** for user-function calls. Programs near the
  language's 100-call limit can hit Python's recursion limit first and return a generic
  `error` instead of `recursion_limit_exceeded`. Recursion-boundary tests written for
  `ExecutionEngine` currently fail (14 tests) and are **not part of this release**.
- *(Resolved in Wave 1C.14: the engine no longer contains that code and the reference evaluator was corrected.)* **`ExecutionEngine` returned `2**63` for `INT64_MIN / -1`** in wraparound and saturating
  modes, which is not a signed 64-bit value. It is recorded as a known defect by two strict
  `xfail` tests; `engine.py` was intentionally not changed in this milestone.
- `ExecutionEngine` and `IterativeEvaluator` charge execution steps differently; production
  integration must adopt the semantic expression-node contract above.
- The evaluators are not a security sandbox (see the README).
