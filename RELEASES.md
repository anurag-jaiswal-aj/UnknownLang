# Release Ledger

Milestones in reverse chronological order. Each entry states what was verified and what was not.

## Wave 2.2.1 — Environment Foundation Acceptance and Integrity Closure
- **Branch:** `main`
- **Status:** Acceptance closure complete. Trusted-local development only. Official/untrusted execution blocked without Docker/WASM.
- **Commits:** `833d588` hash verification fix, `410cd2e` Wave 2.2.0 release.
- **Manifest integrity:** Explicit hash verification in `_verify_manifest_with_hash_checks()` detects tampering in grammar, semantic spec, and surface profile hashes.
- **Reconstruction:** Deterministic regeneration using stored seed and surface profile, with full identity verification.
- **Identity-affecting inputs:** All seed and surface profile fields stored; version fields validated.
- **Test results:** 1184 tests passed (including 17 conformance tests). `git diff --check` passed. Python 3.14.6 verified.
- **Remaining limitations:**
  - Python 3.11–3.13: unavailable (Lark not installed in those interpreter environments)
  - `invalid_program` boundary migration: deferred
  - Docker/WASM sandboxing: required for official/untrusted execution
  - Persistent environment resolution: placeholder implementation
  - Input size limits: documented in release notes, not yet enforced

## Wave 2.2.0 — Environment Lifecycle and Deterministic Derivation Foundation
- **Branch:** `main`
- **Status:** Foundation implementation. Trusted-local development only. Official/untrusted execution blocked without Docker/WASM.
- **Commits:** `b9d916a` Wave 2.2 implementation, `7d6fd9d` Wave 2.1.2 release, `c298429` Wave 2.1.1 closure.
- **Environment manager:** `src/benchmark/manager.py` with create_environment, validate_environment, verify_reconstruction, resolve_environment.
- **Derivation manifests:** Versioned `DerivationManifest` schema for deterministic reconstruction and identity verification.
- **Conformance corpus:** `tests/fixtures/conformance/` with runtime, surface translation, and derivation fixtures.
- **Validation:** Manifest schema version, env schema, generator versions, runtime semantics, and identity all explicitly validated and rejected on mismatch.
- **Test coverage:** 1184 tests passed (including 17 new conformance tests). `git diff --check` passed. Python 3.14.6 verified.
- **Scope:** No benchmark harness, task system, scoring, adapters, storage, replay, frontend, or sandbox implemented.
- **Remaining limitations:**
  - Python 3.11–3.13: unavailable (Lark not installed)
  - `invalid_program` boundary migration: deferred
  - Docker/WASM sandboxing: required for official/untrusted execution

## Wave 2.1.2 — Runtime Semantics Versioning Correction
- **Branch:** `main`
- **Status:** Foundation closure. Trusted-local development only. Official/untrusted execution blocked without Docker/WASM.
- **Version increment:** `RUNTIME_SEMANTICS_VERSION` `1` → `2`
- **Reason:** Correction to observable last-expression-result semantics (F1 correction).
- **Identity impact:** New environment IDs will include version `2`; old environment records retain version `1`.
- **Commits:** `c298429` base, version increment to be staged.
- **Validation:** 1,166 tests passed, exit code 0. Focused F1 and identity tests passed. `git diff --check` passed.
- **Remaining limitations:**
  - Python 3.11–3.13: unavailable (Lark not installed in those interpreter environments)
  - `invalid_program` boundary migration: deferred until a benchmark boundary exists
  - Official and untrusted execution: blocked without Docker/WASM isolation

## Wave 2.1.1 — Runtime foundation acceptance closure
- **Branch:** `main`
- **Status:** Foundation closure complete for the bounded scope. Trusted-local development only.
  Official and untrusted execution remain blocked without Docker/WASM.
- **Commits:** `0c6ee6b` foundation implementation, `e2e9ce5` release record, `3baa7d6` F1/F5 closure correction.
- **F1:** Definitions are declarations; the program returns the last expression value, or `None` when
  there is no expression. Source-order visibility is preserved and production/reference parity passes.
- **F2:** Token-aware surface translation is integrated through production facade, iterative evaluator
  and reference evaluator when a surface profile is supplied. Raw direct callers remain exposed to the
  frozen grammar limitation.
- **F3:** Missing typing imports are fixed. Python 3.14.6 passes; Python 3.11–3.13 lack the installed
  Lark dependency in this environment and are not claimed verified.
- **F4/F5:** Runtime semantic version, strict identity helpers, conflict validation and structured result
  diagnostics are implemented. The `invalid_program` boundary migration remains deferred.
- **Validation:** 1,165 tests passed, exit code 0; focused foundation tests passed; `git diff --check` passed.
- **Scope:** No benchmark harness, task system, scoring, providers, storage, replay or sandbox was started.

## Wave 2.1.0 — Runtime and environment foundation
- **Branch:** `main`
- **Status:** Foundation implementation only. Trusted-local development scope; official and untrusted
  execution remain blocked without Docker/WASM. Benchmark harness, task system, scoring, providers,
  storage, replay and sandbox remain out of scope.
- **Scope implemented:** F1 definition-only results, token-aware surface translation boundary, strict
  benchmark canonicalization, runtime diagnostic fields with legacy serialization, environment identity
  helpers, generator conflict detection and fail-closed Wave 2 feature validation.
- **Validation:** 1,165 tests passed, exit code 0. Focused foundation tests: 219 passed, exit code 0.
  Python 3.14.6 imports and tests passed. Python 3.11–3.13 interpreters were present but lacked the
  installed Lark dependency, so their full matrix status is unavailable and not claimed passing.
- **Commit:** `0c6ee6b`
- **User work:** `.kiro/specs/unknownlang/tasks.md` remains untouched and unstaged.


## Wave 2.0.9 — Owner authorization recording and contract reconciliation
- **Branch:** `main`
- **Status:** **Owner-authorized scope recorded; implementation and official execution remain blocked.**
- **Commit:** `d08b847`
- **Authorization date:** `2026-11-24`, from the project-owner authorization message in the Wave 2.0.9 session. No owner identity or signature was recorded.
- **Approved scope:** AM-01 through AM-16, F1 through F5 technical requirements, and T-01 through T-10 proposed contracts. Scientific validity remains deferred. Trusted-local pilots are permitted only as non-official validation; Docker/WASM remains required for official/untrusted execution.
- **Validation:** documentation checks passed, Mermaid parsing passed, `git diff --check` passed, and the existing Wave 1 suite passed 1,142 tests with exit code 0.
- **Scope:** Documentation and approved requirement-overlay records only. No source, tests or user-owned `tasks.md` changes.
- **Decision:** Do not begin Wave 2.1 until the approved scope is implemented and its acceptance gates pass.

## Wave 2.0.7 — Decision register and contract gate closure
- **Branch:** `main`
- **Status:** **NEEDS_CHANGES / owner approval pending.** Lifecycle, approval-layer, research-register,
  replay and D8/void semantics are now explicit. No owner decision is approved and Wave 2.1 remains
  NO-GO.
- **Commit:** `f2b94f0`
- **Validation:** documentation checks passed, Mermaid parsing passed, `git diff --check` passed and
  the existing Wave 1 suite passed 1,142 tests with exit code 0.
- **Scope:** Documentation only. `requirements.md` and user-owned `tasks.md` were not modified.
- **Remaining:** owner must decide AM-01 through AM-16, F1/F3/F5, official security class, research
  scope, provider/storage policy and all deferred research gates.

## Wave 2.0.6 — Canonical contract reconciliation and owner decision register
- **Branch:** `main`
- **Status:** **NEEDS_CHANGES / owner approval pending.** This milestone reconciles identity, pair,
  task-set, fixture, replay, bootstrap and owner-register contracts. It does not approve any normative
  amendment and does not begin Wave 2.1.
- **Commit:** `190de13`, final identity/field correction in `57a4ee7`, and complete owner register in the current Wave 2.0.6 follow-up
- **Validation:** 121 documentation checks passed, all 7 Mermaid diagrams parsed, `git diff --check`
  passed, and the full Wave 1 regression suite passed 1,142 tests with exit code 0.
- **Scope:** Documentation only. No source, tests, requirements.md or user-owned tasks.md changes.
- **Remaining:** Owner approval is still required for AM-01 through AM-09, the complete omitted
  requirement register, trusted-local versus Docker/WASM execution, provider/storage scope, and the
  narrow-family research claim. Official/untrusted execution remains blocked.
- **Decision:** Do not begin Wave 2.1 until `wave2-owner-approval.md` is completed by the owner.

## Wave 2.0.4 — Requirements and contract approval preparation
- **Branch:** `main`
- **Status:** **NEEDS_CHANGES.** This is an owner-approval package, not an implementation approval.
- **Commit:** `ffac612` (`docs/architecture/wave2-owner-approval.md` and contract corrections)
- **Scope:** No production implementation. No normative requirements were modified. The historical
  `design.md` completion/GO claims were corrected to distinguish Wave 1 implementation from planned
  or unimplemented capabilities.
- **Validation:** 129 documentation checks passed, all 7 Mermaid diagrams parsed, `git diff --check`
  passed, and the full repository suite passed 1,142 tests with exit code 0.
- **Open approval decisions:** AM-01 through AM-09, F1/F3/F5 runtime decisions, pair identity and
  D8 technical contracts, trusted-local versus Docker/WASM official execution, Ollama/provider order,
  and the narrow-family versus genuine-grammar research scope.
- **Decision:** Do not begin Wave 2.1. The owner must complete `docs/architecture/wave2-owner-approval.md`.

## Wave 2.0.2 — Architecture closure and requirements reconciliation
- **Branch:** `main`
- **Status:** **NEEDS_CHANGES.** Design-only closure documents are complete, but Wave 2 remains
  blocked by approval-required requirement amendments and security/provider/runtime prerequisites.
- **Commit:** `bbe0106` (`docs/architecture/` closure contracts and traceability)
- **Validation:** 125 documentation checks passed, all 7 Mermaid diagrams parsed, the planted-defect
  checker caught 21 defects with an unmodified control, and the full repository suite passed 1,142
  tests with exit code 0.
- **Scope:** No production code, runtime semantics or tests were changed. `tasks.md` remains the
  only user-owned working-tree modification.
- **Key blockers:** T7/T8 canonical pair equivalence, P3/bootstrap/D8 contracts are now specified;
  Requirement deviations remain open for Docker/WASM, weighted scoring/resource status, providers,
  SQLite, challenge categories, execution statuses and response extraction. The security-compliant
  official run remains blocked without Docker/WASM.
- **Decision:** Do not begin Wave 2 implementation. Obtain approval for `wave2-decisions.md` and the
  proposed amendments in `requirements-traceability.md` first.

## Wave 2.0.1 — Architecture review and design corrections
- **Branch:** `main`
- **Status:** Review only. Wave 2 implementation remains blocked pending approval.
  The review found five remaining failures in the corrected architecture: surface-pair matching,
  pair-component bootstrap edge cases, P3 void/empty behavior, D8 multi-test aggregation and range,
  and guessing/headline requirement deviations.
- **Commit:** `be650dc` (`docs/architecture/wave2-review.md`)
- **Verification:** 1,142 tests passed, exit code 0. The documentation checker passed 109 checks,
  all 7 Mermaid diagrams parsed, and 21 planted documentation defects were caught by the checker.
- **Runtime:** no production code changed. The authorized untracked `tmp/mutate_if_metadata.py`
  was verified and deleted. `.kiro/specs/unknownlang/tasks.md` remains untouched.
- **Decision:** Do not begin Wave 2 implementation until the blockers and SD1-SD10 decisions in
  `wave2-review.md` are approved.

## Wave 2.0 — Benchmark execution architecture and design
- **Branch:** `main`
- **Status:** **Documentation only. Proposed and awaiting approval. No code was written or changed.**
  The repository suite is unchanged: 1,142 passed, exit code 0.

### Commits
| Commit | Change |
|---|---|
| `545b999` | `docs/architecture/`: overview, task schema, evaluation and scoring, experiment model, roadmap, runtime findings, five ADRs |

This ledger entry and the README pointer are committed after the commit above.

### What the audit found
The brief calls the languages procedurally generated. The audit of the actual code measured:
- Only **6 distinct languages** exist. 36 seeds gave 36 `language_id` values and 6 distinct
  grammar-and-semantics fingerprints. The grammar and the operator names never vary.
- `language_id` does not depend on runtime behavior. It did not change when Waves 1C.15 and 1C.16
  changed behavior.

So the proposed design adds a **surface layer** (renamed keywords, operators and literals, optionally
permuted meaning inside a type class, all user identifiers mangled) that runs before the unmodified
runtime, and an environment identity built from what a model can observe.

### Runtime findings (reported, not fixed; approval requested)
| ID | Finding |
|---|---|
| F1 | A program ending in a definition returns `True` in production and `None` in the reference evaluator |
| F2 | A call named like `ifx` with two arguments is parsed as `(if x ...)`, in both evaluators |
| F3 | `src/language/canonical.py` raises `NameError` on Python 3.11 to 3.13, although `requires-python` is `>=3.11` |
| F4 | `language_id` does not depend on runtime behavior |
| F5 | No structured error kind and no step count on `ExecutionResult` |
| F6 to F12 | Limitations and housekeeping, including an untracked file `tmp/mutate_if_metadata.py` left by Wave 1C.16.1 |

### Decisions awaiting approval
Approve the architecture and five ADRs; rule on F1, F3, F4, F5 and F2 handling; rule on ten
specification deltas (SD1 to SD10), notably scoring resource-limit outcomes as 0 (SD5), adding surface
profiles as a variation (SD6), and the extraction rule (SD10); permission to delete the stray file.
The full list is in `docs/architecture/roadmap-wave2.md`, section 2.

### Verification performed
- Pre-flight: `main`, `origin/main` and the remote equal at `642b2c8`. Only `tasks.md` modified.
- Read-only audit probes of the real runtime (variation across seeds, keyword-prefix parsing,
  definition-last programs, structure quirks, error message families, parse scaling, `canonical.py`
  on four Python versions).
- Two environments and three tasks built from the real runtime. Every expected result was produced by
  both evaluators, which agreed. Every identifier was recomputed from the stated hashing rules.
- 109 automated documentation checks, all passing, including re-execution of every embedded result
  against the live runtime. 21 planted defects, all caught, with an unmodified control that passed.
- All 7 Mermaid diagrams parse with Mermaid 12.3.0 (parsed, not rendered).
- An independent review returned FAIL with five findings. All five were corrected. The corrected text
  was not reviewed again.

### Not verified
No implementation exists, no real model was run, the metrics are unvalidated hypotheses, difficulty and
blueprint numbers are proposals, timings come from one machine, and only Python 3.14.6 with Lark 1.3.1
was used. The benchmark measures behavior inside one small language family and makes no claim about
general reasoning.

## Wave 1C.16.1 — Conditional metadata consistency

- **Branch:** `main`
- **Status:** Corrects a metadata bug identified at Wave 1C.16. `if` now always uses
  `short-circuit` mode in `OperationInfo`. Full suite: 1142 passed, exit code 0.
  Before this milestone it was 1130 passed.

### Commits
| Commit | Change |
|---|---|
| `ae706ba` | `if` always uses `short-circuit` mode; `tests/test_if_metadata.py` |

### Metadata correction

`build_spec` in `SemanticRegistry` incorrectly grouped `if` with `and` and `or`, assigning
it a mode based on the seed's `short_circuit` setting. This is incorrect:

- `and` and `or` evaluate both operands in eager mode (`short_circuit=False`) before checking
  either. Their `semantic_mode` is `eager` or `short-circuit` depending on the seed.
- `if` always evaluates only the selected branch, regardless of the boolean evaluation mode.
  Its `semantic_mode` is always `short-circuit` (meaning lazy branch selection).

The fix removes `"if"` from the `{"and", "or", "if"}` set in `build_spec`, so it always
gets `"short-circuit"`. The runtime behavior was already correct in both evaluators.

### Verification

- Full suite on export of commit `ae706ba`: 1142 passed, exit 0.
- New tests `test_if_metadata.py`: 12 passed, exit 0.
- Mutation QA: 5 mutants. 2 applied and caught, 3 did not apply (exact text mismatch).
  Source files restored byte-for-byte.

### Compatibility

- No change to runtime behavior.
- No change to generated language identity/hash.
- No change to evaluator code.

## Wave 1C.16 — Strict runtime type semantics
- **Branch:** `main`
- **Status:** Closes the boolean-as-integer limitation recorded at Wave 1C.15. Both evaluators
  now implement one type contract. Full suite: 1130 passed, exit code 0. Before this milestone it
  was 1022 passed and 8 expected failures.

### Commits
| Commit | Change |
|---|---|
| `210e286` | strict operand types and type-aware equality in both evaluators; eager `and`/`or` order in the reference; `tests/test_strict_type_semantics.py`; the eight expected-failure tests are now ordinary tests |
| `cb67f84` | literal-order test now proves the literal check runs first (it used `(print 1)`, which is not a builtin) |

This ledger entry and the README update are committed after the commits above.

### Type contract
| Construct | Operands | Type error (status `error`) |
|---|---|---|
| `add`, `sub`, `mul`, `div`, `mod` | both `int` | `Arithmetic operation '<op>' requires int arguments, got <type>` |
| `and`, `or` | both `bool` | `Boolean operation requires boolean arguments, got <type>` |
| `not` | `bool` | `not requires boolean argument, got <type>` |
| `if` | condition `bool` | `if condition must be boolean, got <type>` |
| `eq` | any two values | none. Same type: value equality. Different types: `false` |

- Operands are evaluated first. Arithmetic checks each operand, left to right, before the
  division-by-zero and overflow checks. `(div 1 false)` is therefore a type error.
- Short-circuit `and`/`or` check the left operand, then evaluate the right operand only when the
  left one does not decide the result. The right operand must then be `bool`.
- Eager `and`/`or` evaluate both operands, left then right, before either is checked. An error in
  the right operand is reported first (design.md, "Key distinction").
- `if` evaluates only the selected branch in both modes. The recursive examples in design.md need
  a lazy `if`.
- Type checks run on evaluated operands, when the operation runs. Literal range (1C.15) is still
  checked before execution.
- No check accepts an int where a bool is required, and no check uses `isinstance(x, int)`.
  Arithmetic compares exact types. Boolean checks use `isinstance(x, bool)`, which is exact because
  `int` is not a subclass of `bool`. A branch is chosen by truthiness only after that check.
- Error text is identical in both evaluators. Status and text are checked by exact-match tests.

### Equality decision
Values of different types are never equal, so `(eq 1 true)` is `false`.
- design.md declares `eq` as `["any", "any"] -> "bool"` with `value_equality` semantics.
  `OperationInfo` in `src/language/semantics.py` declares the same signature. A type error would
  make `eq` undefined on a declared input.
- `type_coercion: strict` means no value of one type equals a value of another.
- The spec does not state the mixed-type case in words. This rests on the declared signature.
  See the decisions list below.

### Production and reference changes
- Production (`src/execution/iterative_evaluator.py`): `_eval_arithmetic` checks each operand with
  `type(x) is int`. `_eval_eq` returns `type(a) is type(b) and a == b`.
- Reference (`src/oracle/reference_evaluator.py`), written separately: the same arithmetic and
  equality rules. `_eval_boolean_op` evaluates both operands of an eager `and`/`or` before checking
  either. Its helper `_require_bool_operand` is local. The reference imports no production helper.
- Before this milestone the reference checked the left operand of an eager `and`/`or` before it
  evaluated the right one. `(and 1 (div 1 0))` returned a boolean error instead of the division error.

### Compatibility
- Programs that relied on bool-as-int now return `error`, for example `(add 1 true)` and
  `(div 4 true)`. Before, they returned 2 and 4.
- `(eq 1 true)` and `(eq 0 false)` now return `false`. Before, they returned `true`.
- The arithmetic error text changed from `requires integer arguments` to
  `requires int arguments, got <type>`. No existing test asserted the old text.
- Valid int and bool programs are unchanged.

### Verification
- Full suite: 1130 passed, exit code 0. The same count and exit code on an exported copy of
  commit `210e286`.
- Focused groups, each with its own exit code: new and converted type and literal tests 321 passed
  (exit 0); standalone evaluator tests 488 passed (exit 0); production execution tests 154 passed
  (exit 0); reference evaluator tests 27 passed (exit 0); language layer 136 passed (exit 0).
- `tests/test_strict_type_semantics.py` (100 tests): hand-derived status, exact type, value and
  text for every evaluator and arithmetic mode, plus exact production/reference agreement.
- Seeded random differential corpus: still passes. Its error rate rose, as expected.
- Differential probe of 49 type-sensitive programs in both modes: 2 production/reference
  divergences before the fix (both eager `and`/`or` ordering), 0 after.
- Mutation QA: 24 mutants (12 production, 12 reference). 24 caught, 0 survived, 0 failed to apply.
  Every mutant was caught by the type tests. Covered: bool accepted by arithmetic, bool check
  removed, bool/int equality by value, `1` equal to `true`, boolean operand checks removed
  (short-circuit, eager, `not`, `if`, helper), `if` accepting an int, div/mod skipping the type
  check, eager order reintroduced, and one-sided raises or message text that split the evaluators.

### Known limitations and decisions needing approval
- **Type checks are runtime only.** An operand that is never evaluated is not type-checked: the
  skipped operand of a short-circuit `and`/`or`, an untaken `if` branch, or a function body that is
  never called. The design's boolean table supports this for `and`/`or`. Literal range differs:
  1C.15 rejects an out-of-range literal before execution, even in an untaken branch. Please confirm
  this split.
- **Short-circuit with a non-boolean left operand and an erroring right operand.** The spec does
  not say which error comes first. Both evaluators report the left operand's type error. Only
  agreement is tested for this case.
- **`SemanticSpec` metadata for `if`.** `build_spec` labels `if` as `eager` when `short_circuit` is
  false, but the runtime evaluates `if` lazily in both configurations, and design.md ties eager
  evaluation to boolean operators only. Not changed here. Recommend labelling `if` as
  short-circuit in both configurations.
- **Mixed-type equality** rests on the declared `any` signature, not on a sentence in the spec. A
  type error instead would need typed `eq` overloads in design.md.
- **No numeric ordering.** The MVP built-ins have no `<` or `>`, so no ordering contract applies.
- **Error text is an implementation choice.** The spec defines the status (`error`), not the text.

## Wave 1C.15 — Language contract closure
- **Branch:** `main`
- **Status:** Closes two Wave 1C.14 limitations (integer literal range, `SemanticSpec` metadata).
  Full suite: 1022 passed, 8 expected failures (`xfail`, strict), exit code 0.

### Commits
| Commit | Change |
|---|---|
| `eac475b` | integer-literal range check in both evaluators, with `tests/test_int_literal_contract.py` |
| `6028f47` | fixed `evaluation_order`, `scoping`, `type_coercion` on `SemanticSpec`, with tests |

This entry, the README edit and the recursion-boundary docstring fix are committed afterwards.

### Integer literal contract
- A literal is valid iff `-9223372036854775808 <= value <= 9223372036854775807`.
- The grammar is unchanged (`NUMBER` is still `-?\d+`). Each evaluator checks the parsed tree
  once, after parsing and before any evaluation, so a bad literal is rejected wherever it
  appears: nested, in a function body that is never called, or in an untaken `if` branch.
  No steps are consumed and no output is produced.
- Result: status `error`, message
  `Integer literal out of range: <text> (must be between -9223372036854775808 and 9223372036854775807)`.
  No new exception type; the existing `ExecutionError` is used.
- Arithmetic modes are unaffected: they still govern arithmetic results only.
- The production check uses `Tree.iter_subtrees`. `Tree.scan_values` is recursive in Lark and
  failed 5 existing deep-nesting tests before it was replaced.
- Compatibility: a program containing an out-of-range literal previously ran with a Python
  big integer and now returns `error`.

### SemanticSpec
- Requirement 6 criterion 3 requires `evaluation_order`, `scoping`, `arithmetic` and
  `type_coercion` in the semantics object. Requirement 5 criterion 6 and design.md defer them
  only as configurable dimensions. The two are consistent, so they are fixed metadata.
- New fields, with defaults so existing constructions keep working: `evaluation_order =
  "left-to-right"`, `scoping = "lexical"`, `type_coercion = "strict"`. Any other value raises
  `ValidationError`. `SemanticRegistry.build_spec` populates them. They are not seed options
  and do not change the language identity hash.

### Known limitations and decisions needing approval
- **Booleans are accepted as integers.** `(add 1 true)` returns 2 and `(eq 1 true)` returns true
  in both evaluators (Python `bool` is an `int`). design.md specifies `type_coercion: strict`, so
  the recorded metadata is not yet fully true. Not changed here because it alters runtime
  behavior. Eight strict `xfail` tests document it and will fail loudly once it is fixed.
- Parse errors still return `error`, not `invalid_program`.
- Reference evaluator resource-limit parity and parser source-size limits remain out of scope.

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
