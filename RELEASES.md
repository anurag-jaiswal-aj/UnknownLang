# Release Ledger

Milestones in reverse chronological order. Each entry states what was verified and what was not.

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

- **`ExecutionEngine` still uses Python recursion** for user-function calls. Programs near the
  language's 100-call limit can hit Python's recursion limit first and return a generic
  `error` instead of `recursion_limit_exceeded`. Recursion-boundary tests written for
  `ExecutionEngine` currently fail (14 tests) and are **not part of this release**.
- **`ExecutionEngine` returns `2**63` for `INT64_MIN / -1`** in wraparound and saturating
  modes, which is not a signed 64-bit value. It is recorded as a known defect by two strict
  `xfail` tests; `engine.py` was intentionally not changed in this milestone.
- `ExecutionEngine` and `IterativeEvaluator` charge execution steps differently; production
  integration must adopt the semantic expression-node contract above.
- The evaluators are not a security sandbox (see the README).
