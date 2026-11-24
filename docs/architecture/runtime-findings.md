# Runtime Findings from the Wave 2.0 Audit

Status: **Report only. Nothing in this document has been fixed.**
Baseline: Wave 1C.16.1, commit `642b2c8`.

The Wave 2.0 brief forbids modifying the runtime unless a design-critical defect is found, in which
case it is to be reported separately and approval requested. These are the findings. For each one
this document says what was observed, what it means for the benchmark, how the Wave 2 design already
avoids it, and what change is recommended.

Every observation below was produced by executing a program on the real runtime, or by reading the
code, as stated in the evidence line. The probe scripts were throwaway and are not committed.

| ID | Finding | Kind | Design-critical | Approval needed to change the runtime |
|---|---|---|---|---|
| F1 | Programs ending in a definition return different values in the two evaluators | defect | yes | yes |
| F2 | A call whose name starts with `if` or `def` can be parsed as a keyword form | defect | yes | yes (grammar is frozen) |
| F3 | `src/language/canonical.py` cannot be imported on Python 3.11 to 3.13 | defect | yes | yes |
| F4 | `language_id` does not depend on runtime behavior | gap | yes | yes (adds a constant) |
| F5 | The result has no structured error kind and no step count | gap | no | yes (additive) |
| F6 | Only 6 distinct languages exist, and three seed fields are inert | limitation | yes | no |
| F7 | The reference evaluator cannot run arbitrary candidate programs | limitation | no | no |
| F8 | Several definition quirks are silent | behavior | no | no |
| F9 | `canonical_json` accepts floats and converts unknown types with `str()` | gap | no | no |
| F10 | There is no source size limit | limitation | no | no |
| F11 | Dependency declarations do not match use | housekeeping | no | no |
| F12 | A stray file from Wave 1C.16.1 is untracked in the repository | housekeeping | no | yes (a deletion) |

## F1. Programs ending in a definition return different values

**Observed** (production against reference, the same language spec):

| Program | Production | Reference |
|---|---|---|
| `(def g (a) a)` | `success`, `True` | `success`, `None` |
| `(def g (a) a)` then `(def h (b) b)` | `success`, `True` | `success`, `None` |
| `5` then `(def g (a) a)` | `success`, `True` | `success`, `None` |
| `(add 1 2)` then `(def g (a) a)` | `success`, `True` | `success`, `None` |
| `(def g (a) a)` then `5` | `success`, `5` | `success`, `5` |
| empty source | `success`, `None` | `success`, `None` |

**Cause (by reading the code).** In production, `_handle_def_decl_frame` pushes a `RETURN` frame with
`result=True` for every definition, so when a definition is the last program element, `True` is the
program's value. The reference evaluator returns the value of the last **expression** and ignores
definitions. No existing test compares a definition-last program across the two evaluators, which is
why the 1,142 tests do not see it.

**Impact.** A submission that only defines a function has no agreed value, and the benchmark's two
evaluators would disagree on it. Requirement 8, criterion 6, says disagreement must mark a test case
invalid.

**Design response.** Program submissions are `definitions_only`, and the harness supplies the final
expression ([task schema](benchmark-task-schema.md), 7.3). The disagreement is never exercised.

**Recommendation.** Define the value of a program as the value of its last expression, and `None` if
it has no expression. Change production to stop returning `True` for a definition. Add the program
to the differential hand corpus. This is a behavior change and would bump the proposed
`runtime_semantics_version`.

## F2. Keyword-prefix misparse

**Observed** (identical in both evaluators):

| Program | Result | Reading |
|---|---|---|
| `(def ifx (a b) a)` then `(ifx true 1)` | `error`, `Unknown identifier: x` | parsed as `(if x true 1)` |
| `(def ifx (a b) a)` then `(ifx 7 1)` | `error`, `Unknown identifier: x` | parsed as `(if x 7 1)` |
| `(defg (a) a)` | `success`, `True` | parsed as the definition `(def g (a) a)` |
| `(def ifxy (a b c) a)` then `(ifxy 1 2 3)` | `success`, `1` | parsed as a call (no valid keyword reading) |
| `(def f (a) a)` then `(deff 4)` | `error`, `Unknown function: deff` | parsed as a call |

**Cause (inference from the grammar and the behavior).** The grammar treats `def` and `if` as
anonymous keyword tokens, and the parser is Lark's Earley parser with a dynamic lexer, which does
not require a word boundary after a keyword. A call whose name begins with a keyword is ambiguous
with the keyword form when the arity makes both readings valid, and the parser chooses the keyword
form.

**Impact.** A model that names its helper function `ifx`, `iffy` or similar may be marked wrong for a
reason that has nothing to do with its reasoning. This is a validity threat to the benchmark.

**Design response.** The surface layer maps **every** user identifier to `_u<N>` before the runtime
sees the program, so the hazard cannot be reached on the benchmark path. Verified: `(forge ifx (a b) a)`
followed by `(ifx 7 1)` returns 7 through the translator. Gate E8 checks that translated output
contains no other identifier.

**Recommendation.** Leave the frozen grammar alone for now. Record the issue in the language
documentation, and consider a word-boundary rule (`/if\b/`) in a future grammar version, which would
need its own milestone.

## F3. `canonical.py` and `serializer.py` fail on Python 3.11 to 3.13

**Observed.** Executing the modules on each interpreter:

| Interpreter | Result |
|---|---|
| Python 3.11 | `canonical.py`: `NameError: name 'Optional' is not defined`; `serializer.py`: `NameError: name 'ClassVar' is not defined` |
| Python 3.12 | same |
| Python 3.13 | same |
| Python 3.14 | both import normally |

**Cause.** `canonical.py` uses `Optional` without importing it and has no postponed-annotation
import. `serializer.py` uses `ClassVar` without importing it. Python 3.14 evaluates these annotations
lazily; earlier versions fail at module definition time.

**Impact.** `pyproject.toml` declares `requires-python = ">=3.11"`, but the package is not compatible
with that declaration. The benchmark cannot claim cross-version reproducibility until both imports are
fixed and a Python 3.11–3.14 matrix passes.

**Design response.** The Wave 2 canonical module remains separate, and the run manifest records
Python/Lark versions. This does not repair the existing package contract.

**Recommendation.** Add the missing imports or postponed annotations, then run the full test matrix.
Narrowing `requires-python` is the fallback if older support is intentionally withdrawn.
## F4. `language_id` does not depend on runtime behavior

**Observed.** `compute_language_id` hashes the canonical seed, `spec_version` and `algorithm_version`,
all of which are inputs. The runtime's behavior changed in Waves 1C.15 (literal range check) and
1C.16 (strict types), and the `language_id` of any seed did not change.

**Impact.** Two results from different runtime behavior carry the same language identity. For a
benchmark whose first requirement is reproducibility (Requirement 20, criteria 1 to 3), that makes
results incomparable without anyone noticing.

**Design response.** The Wave 2 environment identity separates an observable fingerprint from a
scientific identity that includes generator family/algorithm versions and
`runtime_semantics_version` ([task schema](benchmark-task-schema.md), section 3.4). The conformance
corpus makes a missing runtime-version bump fail validation.

**Recommendation.** Add `RUNTIME_SEMANTICS_VERSION = 1` to the execution package, defined as the
behavior of commit `642b2c8`, and make the environment manager import it. Define and version the
byte-framed derivation protocol. Bump the runtime constant whenever observable `(status, value, error
class)` behavior changes.

## F5. No structured error kind and no step count

**Observed.** `ExecutionResult` has `status`, `value`, `output` and `error_message`. The following
were observed:

* Parse errors have status `error`, the same as runtime errors, and are distinguished only by the
  message text (`Runtime error: Unexpected end-of-input...`, `Runtime error: No terminal matches...`).
* The overflow message for `add`, `sub` and `mul` is `Runtime error: Integer overflow: <a> <lambda> <b>`,
  where `<lambda>` is a Python implementation detail. For division it is `... <a> / <b>`.
* Resource limits are typed statuses. Step consumption is not reported.

**Impact.** Failure classification has to match message text, which is fragile. Efficiency
diagnostics need extra runs.

**Design response.** A pinned message table with a loud failure on any unknown message
([evaluation and scoring](evaluation-and-scoring.md), 3.2). Raw messages are never shown to a model.
Step efficiency is found by bisection on `max_steps`.

**Recommendation.** Add optional `error_kind`, `error_detail`, `steps_used` and `ast_depth_reached`
fields after the existing dataclass fields. Keep the current four-key `to_dict()` shape and provide a
versioned diagnostic serializer. Use the status/error contract in
[wave2-decisions.md](wave2-decisions.md), D-008. Existing callers remain compatible; the benchmark
must not classify by free-text messages after structured fields are available.

## F6. Six distinct languages, three inert seed fields

**Observed.** 36 seeds were generated by varying arithmetic mode (3), short circuit (2), difficulty
(1, 3, 5) and features (2 sets). Results:

* The grammar text was identical for all 36.
* There were 36 distinct `language_id` values and **6** distinct fingerprints of
  grammar-plus-semantics.
* Changing `name`, `features` (including adding an unknown custom feature) or `difficulty` did not
  change the grammar or the semantics.
* `difficulty` influences only the `algorithm_version` string inside the grammar spec, which
  `LanguageGenerator.generate` does not use for the language.
* The seed validator accepts five syntax styles, and the grammar builder accepts only `lisp`.

**Impact.** This is the reason the surface layer exists (overview, section 2).

**Design response.** The environment manager pins the inert fields to constants, hashes the
fingerprint and not the seed, and layers the surface profile on top.

**Recommendation.** None for the runtime. Whether the inert fields should stay in the seed is a
language-design question outside Wave 2.

## F7. The reference evaluator is not a general oracle

**Observed.** README.md and RELEASES.md (Wave 1C.14) state that the reference evaluator uses Python
recursion, was measured at about 75 nested user-function calls, and has no resource limit parity with
production. This was **not re-measured** in Wave 2.0; the figure is taken from those documents. The
reference evaluator returned the same messages as production in every non-resource case probed.

**Impact.** Candidate programs cannot be cross-checked on the reference evaluator, and tasks whose
reference solution recurses deeply cannot be verified by it.

**Design response.** The reference evaluator is used where tasks and environments are built, not on
model submissions, and tasks stay at call depth 40 or less when a second source is needed
(rule T11).

## F8. Silent definition quirks

**Observed** (identical in both evaluators):

| Program | Result |
|---|---|
| `(def add (a b) 99)` then `(add 1 2)` | `3` (the built-in wins; the definition is silently ignored) |
| `(def f (x x) x)` then `(f 1 2)` | `2` (duplicate parameter accepted, last binding wins) |
| `(def f (x) 1)` then `(def f (x) 2)` then `(f 0)` | `2` (redefinition replaces) |
| `(def f (true) 1)` then `(f 5)` | `1` (a parameter named `true` is accepted) |
| `(f 1)` then `(def f (x) x)` then `(f 2)` | `error`, `Unknown function: f` (use before definition) |

**Design response.** The harness rejects reserved names and duplicate parameters in submissions
before running them, and the language reference states these as rules of the language the model is
asked to use.

## F9. `canonical_json` is permissive

**By reading the code.** `canonicalize_value` returns floats unchanged and converts any other type
with `str()`. A set, for example, would be serialized with whatever order `str` produces, which is
not guaranteed stable. A float would be serialized by `json.dumps`, whose representation is stable
for a given Python version but is not an identity-grade canonical form.

**Design response.** A strict wrapper with no floats and no type conversion
([task schema](benchmark-task-schema.md), 1.1).

## F10. No source size limit

**Observed.** Parse time for a program of many short expressions, on the development machine, in
production:

| Top-level expressions | Source bytes | Time |
|---|---|---|
| 1,000 | 9,999 | 0.27 s |
| 4,000 | 39,999 | 1.14 s |
| 16,000 | 159,999 | 5.15 s |

Time grew roughly linearly (about 4.2 and 4.5 times for each 4 times larger input). These figures
come from one machine and one run each. README.md already lists this as a known limitation. A
deeply nested program was measured in Wave 1C.14 and is not repeated here.

**Design response.** A submission byte cap checked before parsing and a watchdog. The cap values are
placeholders until calibration (M2.11).

## F11. Dependency declarations

**Observed.** `pyproject.toml` lists `fastapi`, `uvicorn` and `httpx`. A search of `src` and
`tests` finds no import of any of the three, and no async test. `lark>=1.1.0` is unpinned and the
installed version is 1.3.1. `requires-python` is `>=3.11` (see F3).

**Design response.** Wave 2 adds no third party dependency, records the Lark version in each run
manifest, and uses a conformance digest to detect behavior drift between Lark versions. The unused
dependencies are left untouched.

## F12. An untracked file from Wave 1C.16.1

`tmp/mutate_if_metadata.py` is untracked in the repository root. It is a mutation-testing script that
the assistant wrote inside the repository by mistake in Wave 1C.16.1 and never committed. It has not
been touched in Wave 2.0 and is not staged. Removing it is a deletion in the user's repository, so
permission is requested.
