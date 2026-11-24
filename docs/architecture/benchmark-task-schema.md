# Benchmark Task Schema (Wave 2.0)

Status: **Proposed. Pending review and approval. Nothing here is implemented.**
Baseline: Wave 1C.16.1, commit `642b2c8`.
Companion documents: [overview](wave2-overview.md), [decisions](wave2-decisions.md),
[requirements traceability](requirements-traceability.md), [scoring contract](scoring-contract.md),
[evaluation and scoring](evaluation-and-scoring.md), [experiment model](experiment-model.md),
[roadmap](roadmap-wave2.md), [runtime findings](runtime-findings.md).

This document is the single source of truth for identifiers, enumerations and field names. Other
documents refer to these names and do not redefine them.

The specification calls the benchmark unit a *challenge* (requirements.md, Requirement 9). This
document calls it a *task*. They are the same thing; "task" is used because several task types
(for example operator inference) are not challenges in the programming-puzzle sense.

## 1. Conventions

### 1.1 Canonical JSON and hashing

Every identifier in this document is a SHA-256 digest of canonical JSON.

* Encoding: JSON (RFC 8259), UTF-8 bytes of the text produced by
  `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)`.
* **Integers, strings, booleans, `null`, arrays and objects only.** Floats are forbidden in hashed
  content. Probabilities are stored as integer parts per million (`_ppm`). Ratios are stored as two
  integer counts.
* Object keys are ASCII strings.
* Arrays keep their order. Order that has no meaning (for example a set of environments) is sorted
  before hashing.
* This is not RFC 8785 (JCS): non-ASCII text is escaped. It is the same `json.dumps` configuration
  that `src/language/canonical.py` already uses. The existing `canonical_json` helper is **not**
  reused as is, because it silently accepts floats and converts unknown types with `str()`
  (see [runtime findings](runtime-findings.md), F9). A strict wrapper rejects both.

Digest text form: lowercase hex, 64 characters. Humans may see the first 12 characters; the store
must reject a short-form collision rather than guess.

### 1.2 Identifier forms

| Identifier | Form | Hashed content | Excluded from the hash |
|---|---|---|---|
| `environment_id` | `env_<sha256>` | `identity_core` of the environment record (section 3) | derivation, provenance, `runtime` cross-references |
| `surface_id` | `<sha256>` | the surface profile object | nothing |
| `task_id` | `task_<sha256>` | the task record | `task_id`, `verification`, `provenance`, `notes` |
| `pair_id` | `pair_<sha256>` | pair-group template/version, category, difficulty dimensions, information condition, protocol variation, canonical query projection, sorted environment ids | nothing |
| `task_set_id` | `tset_<sha256>` | task-set schema, family version, complete blueprint/version/slots, sorted `(environment_id, split)` assignments, sorted task ids | nothing |

`expected` is part of `task_id` (it is the claim). `verification` is not (it is the evidence for the
claim). Adding a second verification source later therefore does not change a task's identity.

### 1.3 Versions

| Version field | Bumped when |
|---|---|
| `env_schema_version` | the environment record layout changes |
| `profile_schema_version` | the surface profile layout changes |
| `runtime_semantics_version` | observable behavior of the runtime changes (section 3.3) |
| `schema_version` (task) | the task record layout changes |
| `template.version` | a task generator template changes the tasks it emits |
| `prompt.template.version` | prompt wording changes |

A change to any of these produces new identifiers. Old records stay readable because they name the
version they were built under. Nothing is migrated in place.

## 2. Environment reference

A task points to exactly one environment by `environment_id`. The environment is a separate,
immutable, content-addressed record. Section 3 defines it. The task never embeds the grammar,
semantics or surface profile.

## 3. Environment record

### 3.1 Why a new record

The existing `LanguageSpec.language_id` is not a sufficient environment identity. Measured on the
Wave 1C.16.1 code (see [runtime findings](runtime-findings.md), F4 and F6):

* `language_id` hashes the seed (name, features, difficulty, arithmetic, short circuit) and two
  caller supplied version strings. Name, features and difficulty do not change the grammar or the
  semantics. 36 different seeds produced 36 `language_id` values but only 6 distinct
  grammar-and-semantics fingerprints.
* `language_id` does not depend on runtime behavior. The behavior of the same seed changed in
  Waves 1C.15 and 1C.16, and its `language_id` did not.

The environment record carries two related fingerprints. `observable_fingerprint` describes the
byte-identical executable artifact, while `environment_id` also includes generator family/algorithm
versions and runtime semantics version required to reproduce and interpret it. This prevents a changed
recipe or runtime from silently reusing a scientific environment identity.

### 3.2 Fields

| Field | Type | In identity | Notes |
|---|---|---|---|
| `environment_id` | string | no (it is the hash) | `env_` + digest of `identity_core` |
| `identity_core.env_schema_version` | int | yes | |
| `identity_core.generator_family_version` | string | yes | generator family contract |
| `identity_core.generator_algorithm_version` | string | yes | generator algorithm contract |
| `identity_core.grammar_sha256` | digest | yes | canonical grammar bytes |
| `identity_core.semantic_spec_sha256` | digest | yes | complete semantic spec |
| `identity_core.surface_profile_sha256` | digest | yes | section 4 |
| `identity_core.semantic_fingerprint` | digest | yes | observable fingerprint, section 3.4 |
| `identity_core.surface_id` | digest | yes | digest of `surface_profile` |
| `identity_core.runtime_semantics_version` | int | yes | section 3.3 |
| `semantic.arithmetic` | `wraparound` \| `saturating` \| `error-on-overflow` | via fingerprint | |
| `semantic.short_circuit` | bool | via fingerprint | |
| `surface_profile` | object | via `surface_id` | section 4 |
| `runtime.grammar_sha256` | digest | via fingerprint | cross-reference |
| `runtime.language_id` | string | no | cross-reference to the existing `LanguageSpec` |
| `runtime.spec_version`, `runtime.algorithm_version` | string | no | passed to `LanguageGenerator.generate` |
| `derivation` | object or null | **no** | master seed and index, if generated (section 3.5) |
| `status` | `draft` \| `validated` \| `frozen` \| `retired` | no | lifecycle, section 3.6 |

The environment manager builds the `LanguageSeed` itself and pins the fields that do not affect
behavior: `name = "env"`, `features = ["arithmetic", "functions", "recursion", "short_circuit"]`,
`difficulty = 1`, `syntax_style = "lisp"`. Only `arithmetic` and `short_circuit` vary. Two
environments with the same semantics and the same surface profile are therefore the same
environment.

### 3.3 Runtime semantics version

`runtime_semantics_version` is an integer constant that does not exist in the runtime today. It is
proposed as an additive change in milestone M2.1 and requires approval
([runtime findings](runtime-findings.md), F4). It identifies the **observable behavior** of the
execution runtime. Its value for Wave 1C.16.1 is defined as `1`.

It is bumped for any change that can alter a program's `(status, value, error class)`, for example
the Wave 1C.15 literal range rule or the Wave 1C.16 strict types. It is not bumped for refactors,
performance work or new tests. A conformance corpus (section 11.3) makes the bump rule checkable:
if a corpus result changes and the version did not, the test suite fails.

### 3.4 Semantic and environment fingerprints

```
semantic_spec_sha256 = sha256(canonical_json({
  "arithmetic_mode": ..., "short_circuit_mode": ..., "evaluation_order": ...,
  "scoping": ..., "type_coercion": ...,
  "operations": { <canonical name>: { arity, arg_types, return_type, semantic_mode }, ... }
}))

observable_fingerprint = sha256(canonical_json({
  "grammar_sha256": sha256(LanguageSpec.grammar),
  "semantic_spec_sha256": ..., "surface_profile_sha256": ...
}))

environment_id = "env_" + sha256(canonical_json({
  "env_schema_version": 1,
  "generator_family_version": "f1",
  "generator_algorithm_version": "1.0.0",
  "observable_fingerprint": ...,
  "runtime_semantics_version": 1
}))
```

`observable_fingerprint` detects byte-identical executable environments. `environment_id` is the
scientific identity and additionally records the generator and runtime versions that produced and
interpret the environment. It contains no seed name, timestamp or host data. Python and Lark versions
are attested separately through the conformance corpus.

### 3.5 Derivation from a seed

A generated environment records `derivation = {family_version, master_seed, index}`. Derivation
must not depend on Python's `random` module. The byte-level stream protocol is:

```text
encode(seed)    = UTF-8(seed string)
encode(purpose) = UTF-8(purpose string)
frame(x)        = uint64_be(len(x)) || x
input           = b"unknownlang-derive-v1" || frame(encode(seed)) || frame(encode(purpose)) || uint64_be(index)
digest          = SHA-256(input)
```

Choice extraction uses rejection sampling from the digest stream, with a documented counter suffix
when more bytes are required. No modulo-biased choice or process hash is allowed. Details are in
[ADR-001](adr/ADR-001-environment-identity.md).

### 3.6 Lifecycle

`draft` (being built) then `validated` (all section 3.7 gates passed) then `frozen` (referenced by
a task set; immutable) then `retired` (no longer used for new task sets; **never deleted**, because
recorded experiments refer to it).

### 3.7 Environment validation gates

| Gate | Rule |
|---|---|
| E1 | The surface profile is a bijection between surface names and canonical names that preserves the type class: arithmetic operations only with arithmetic operations, `and`/`or` only with `and`/`or`, `not`, `eq`, `def`, `if`, `true`, `false` only with themselves. |
| E2 | Surface names are pairwise distinct. A profile is **either** `pseudo` **or** `familiar`, never a mixture. A `pseudo` profile uses only names that match `^[a-z]{4,8}$`, that are not canonical names, and that do not begin with `if`, `def`, `true` or `false`. A `familiar` profile uses exactly the canonical names (`def if add sub mul div mod and or not eq true false`), possibly permuted within a type class. A familiar profile with a permuted meaning (for example `add` meaning `sub`) is how the benchmark tests reliance on prior knowledge of familiar names. |
| E3 | Round trip: for every program in the conformance corpus, translating canonical to surface and back is the identity. |
| E4 | Differential: every corpus program, written in surface form and translated, gives the same `(status, value, error class)` as the canonical program on both the production and reference evaluators. |
| E5 | The semantic fingerprint recomputes from a fresh `LanguageGenerator` run. |
| E6 | `runtime_semantics_version` equals the running runtime's constant. |
| E7 | Every documentation claim generated for this environment passes its executable check (section 8.2). |
| E8 | Translated output contains only canonical reserved words and identifiers of the form `_u<N>`. This makes the keyword-prefix hazard unreachable ([runtime findings](runtime-findings.md), F2). |

## 4. Surface profile

A surface profile re-skins the language without touching the grammar or either evaluator. It is
data plus a deterministic translator that runs **before** the runtime.

```text
{
  "profile_schema_version": 1,
  "keywords":  { "<surface name>": "def" | "if" },
  "operators": { "<surface name>": "<canonical operation>" },
  "literals":  { "<surface name>": "true" | "false" }
}
```

Reading: the surface name `vorn` has the meaning of the canonical operation `sub`. The canonical
operations are `add sub mul div mod and or not eq`. Their signatures come from the existing
`SemanticRegistry` and are not redefined. A profile is `pseudo` (all surface names are invented
words) or `familiar` (the surface names are the canonical names, possibly permuted); gate E2 forbids
a mixture. In a `familiar` profile a user identifier can never equal a surface name, so the
translator mangling in section 4.2 still applies to every other identifier.

### 4.1 What the profile varies

| Factor | Definition | Compared as a pair |
|---|---|---|
| names | the set of surface names differs and the meaning is the same up to renaming | `environment:surface_names` |
| meaning | the same surface names are assigned to different canonical operations | `environment:operator_meaning` |
| semantic configuration | arithmetic mode or short circuit mode differs | `environment:semantic_config` |

Factors can be combined by listing more than one in `varies` (section 6.2).

### 4.2 Translator contract

`to_canonical(surface_text, profile) -> (canonical_text, name_map)`:

1. Tokenize the surface text with a harness-owned tokenizer: `(`, `)`, integers `-?[0-9]+`,
   identifiers `[A-Za-z_][A-Za-z0-9_]*`. Anything else is a tokenization error.
2. Map keywords, operators and literals through the profile.
3. Map **every other identifier** to `_u1`, `_u2`, ... in order of first appearance.
4. Join tokens with single spaces.

Consequences, each verified in Wave 2.0 on the real runtime with a throwaway script:

* A surface program that uses a canonical name the surface language does not have (for example
  `(add 1 2)` where `add` is not a surface name) becomes `(_u1 1 2)` and fails with
  `Unknown function`. This is the correct behavior for the surface language. The canonical `add`
  is not reachable.
* A user function called `ifx`, which the raw runtime misparses as `(if x ...)`
  (F2), becomes `_u1` and works. `(forge ifx (a b) a)` followed by `(ifx 7 1)` returns 7.
* A user variable called `truex` is `_u1` and cannot collide with a boolean literal.
* Error messages produced by the runtime contain canonical or mangled names. Any text shown to a
  model is produced by the harness from the error **class** and the `name_map`, never copied
  from the raw message (the raw overflow message, for example, contains the text `<lambda>`).

The translator is a new component with its own correctness obligation. It is verified by property
tests against both evaluators (gate E4) and by an independently written second tokenizer inside
the test suite. It is a shared point of failure for both evaluators, so this is a stated residual
risk, not a solved one.

## 5. Task record

### 5.1 Fields

| Field | Type | Required | In `task_id` | Visible to the model | Rules |
|---|---|---|---|---|---|
| `schema_version` | int | yes | yes | no | `1` |
| `task_id` | string | yes | no | no | must equal the recomputed hash |
| `template` | `{id, version}` | yes | yes | no | `id` is `<category>.<name>`, lowercase |
| `category` | enum (6.1) | yes | yes | no | must be allowed for `template.id` |
| `protocol` | object (6.2) | yes | yes | no | |
| `environment_id` | string | yes | yes | yes, as the rendered language reference | must resolve to a `frozen` environment |
| `difficulty` | `{level, dimensions}` | yes | yes | no | section 5.3 |
| `information_condition` | enum (6.3) | yes | yes | yes, by effect | |
| `input` | object | no | yes | partly | `definitions: {source, visibility}`; see 5.4 |
| `prompt` | object | yes | yes | yes | `template`, `example_policy`, `public_examples`, and one of `query` or `spec` |
| `answer_spec` | object | yes | yes | yes | section 7 |
| `expected` | object | yes | yes | **no** | section 7 |
| `evaluation` | object | yes | yes | partly | `method`, `limits`, and `tests` for test suites |
| `verification` | object | yes | no | no | sources, agreement, gates |
| `provenance` | object | yes | no | no | generator, version, derivation seed. No timestamps in hashed content |
| `notes` | string | no | no | no | free text |

Unknown fields are rejected. A task with a missing required field is invalid, never defaulted.

### 5.2 Public view and private data

`project_public(task)` is the only function that produces what a prompt may be built from. It keeps
`environment_id`, `information_condition`, `prompt`, `answer_spec` and the public part of
`evaluation` (method, limits, and tests whose `visibility` is `public`). It drops `expected`,
hidden tests, `verification`, `provenance`, `protocol.role` and `difficulty`. The model adapter
interface accepts only a prompt built from this view (see the [experiment model](experiment-model.md),
section 5).

### 5.3 Difficulty

`difficulty.level` is an integer from 1 to 5, **computed** from `difficulty.dimensions`, not asserted
by the author. The dimensions follow design.md ("Challenge Difficulty Metrics"): `reasoning_steps`
(int), `nesting_depth` (int), `control_flow` (`none`, `conditional`, `short_circuit`, `recursion`),
and `state` (`none`, `simple`, `multiple`). The mapping from dimensions to level is a pure function
fixed in the template version. Challenge difficulty is independent of language difficulty
(requirements.md, Requirement 9, criterion 6): the environment does not influence the level.

The level is a **stratification label**. The scoring design never uses it as a weight
([evaluation and scoring](evaluation-and-scoring.md), section 5.4).

### 5.4 Task input definitions

`input.definitions` carries surface-language function definitions that are part of the task and not
of the environment. `visibility` is `public` (shown to the model) or `hidden`. A hidden definition
is how black-box function inference is built: the model sees the function name, its arity and
public examples, but not the body. The hidden source is loaded before every program run for the
task. It is excluded from `project_public`.

## 6. Enumerations

### 6.1 Categories

Each category is a capability claim. The right-hand column says what the category does **not**
establish.

| Category | Capability measured | Typical form and answer | Does not establish |
|---|---|---|---|
| `SYN` Syntax comprehension | Reading structure in an unfamiliar surface syntax: which tokens are calls, keywords, literals, and how forms nest | A program and a structural question (`count_calls`, `max_depth`, `count_if_expressions`); integer answer | Semantic understanding. A model can count parentheses with no understanding of the operators |
| `EVAL` Expression evaluation | Applying the stated or inferred semantics to compute a result, including predicting an error | A program; value or `ERROR <class>` | Ability to write programs |
| `INF` Operator and semantic inference | Inferring what an unfamiliar operator or configuration does from examples, then applying it | Public examples plus a query; value or error | Memory of familiar operators. Names are pseudo-words and meanings may be permuted |
| `CTRL` Control-flow reasoning | Predicting evaluation order effects: lazy `if`, short circuit versus eager `and`/`or`, which operand is evaluated | A program whose result depends on evaluation order; value or error | Anything the semantic configuration cannot reveal. Gate T8 ensures the task is sensitive |
| `CONS` Program construction | Writing an expression or function that meets a specification | Specification plus public examples; a program; graded by hidden tests | Efficiency beyond the resource limits |
| `REC` Function definition and recursion | Writing recursive functions within the call-depth limit | As `CONS`, with recursion required by the specification | Iteration, collections or higher-order functions. The language has none |
| `ERR` Error interpretation and correction | Reading an error class and repairing a faulty definition | `classify` form: faulty program, answer is the error class. `fix` form: faulty definitions, answer is corrected definitions graded by hidden tests | Debugging in a real language |

`CONS` and `REC` share a grader and differ in what they require. `ERR` has two forms and each uses
one of the two grading methods in section 7.

Adaptation to changed semantics and transfer to unseen environments are **not** categories. They are
experimental conditions applied to the categories above: adaptation through `paired` protocols
(6.2), transfer through the dev and held-out environment split of a task set (section 9). Making
them categories would hide the fact that the same capability is being measured under a changed
condition.

Requirements.md, Requirement 9, criterion 1 lists array operations, string manipulation, sorting
and search. The MVP runtime has only integers, booleans, lexically scoped first-order functions
and recursion. Those problem types cannot be expressed. This is recorded as a specification delta in
the [overview](wave2-overview.md), section 9.

### 6.2 Protocol

```text
{ "kind": "standalone" }
{ "kind": "paired", "pair_id": "pair_<sha256>", "role": "control" | "treatment",
  "varies": ["environment:semantic_config", "information_condition"] }
```

`varies` is a sorted, non-empty list drawn from `environment:surface_names`,
`environment:operator_meaning`, `environment:semantic_config`, `information_condition`,
`example_policy`.

A pair is valid only if the control task and every treatment task share `template`, `category`,
the query program (or, where the environment changes the meaning of the query, a query program
that translates to the same canonical program) and `difficulty.dimensions`, and differ in **exactly**
the fields named in `varies`. The check is mechanical (gate T7).

A `paired` task is scored like any other task. The pairing only controls how scores are
compared (section 6 of [evaluation and scoring](evaluation-and-scoring.md)).

### 6.3 Information conditions

| Value | The model sees |
|---|---|
| `FULL_DOC` | Reference for the task's environment: lexical rules, signatures, prose semantics, form rules, limits, plus public examples |
| `SIGNATURES_ONLY` | Reference with signatures and no behavior prose, plus public examples |
| `EXAMPLES_ONLY` | Lexical rules and public examples only |
| `DELTA_DOC` | Reference for the paired control environment plus an explicit list of differences to this environment |
| `STALE_DOC_EXAMPLES` | Reference for the paired control environment (now out of date) plus public examples produced by this environment, with no statement that anything changed |

Examples shown to the model are always **truthful**: each is produced by running the task's own
environment. A misleading example (`example_policy: misleading`) is one that is also consistent
with a plausible wrong hypothesis. It is never false.

### 6.4 Error classes

Used in `error` answers and in failure analysis. The mapping from runtime results is pinned in
[evaluation and scoring](evaluation-and-scoring.md), section 3.2.

`syntax`, `name`, `arity`, `type`, `division_by_zero`, `overflow`, `literal_range`, `resource`.

### 6.5 Other enumerations

* `answer_spec.type`: `value`, `program`.
* Value kinds: `int`, `bool`, `error`.
* Program forms: `definitions_only`, `expression`.
* `evaluation.method`: `exact_match`, `test_suite`.
* `prompt.example_policy`: `neutral`, `misleading`.
* Test `visibility`: `public`, `hidden`.
* Verification source names: `closed_form`, `production`, `reference`.
* Task status: `draft`, `validated`, `frozen`, `retired`. Not part of the identity.

## 7. Answers, expected results and evaluation

### 7.1 Answer forms the model must produce

| `answer_spec.type` | Required response form | Extraction |
|---|---|---|
| `value` | A final line `ANSWER: <int>`, `ANSWER: <bool literal in the task's surface names>` or `ANSWER: ERROR <error class>` | the **last** line of the response that matches `^ANSWER:[ ]*(.+?)[ ]*$` |
| `program` | One fenced code block containing the submission | the **last** fenced block |

Only the last candidate counts, so listing several candidates earns nothing. Boolean answers use the
surface literal names so the canonical names are never needed.

### 7.2 `exact_match`

The extracted value is parsed into `{kind, value}` or `{kind: "error", error_class}` and compared to
`expected.value` for equality. Equality is type exact: integer `1` and boolean true are different
values (Wave 1C.16 strict typing). A wrong kind is `wrong_answer` with detail `wrong_kind`.

`answer_spec.chance_floor_ppm` records the probability that a guess from the answer space is
correct. A boolean answer has a floor of 500000. A task whose floor exceeds 100000 (10%) must be
rebuilt as a composite of several queries that must **all** be right, which lowers the floor to the
product (gate T10).

### 7.3 `test_suite`

For each test, the harness builds the program
`input.definitions (if any) + submission + test.call`, translates it, and runs it with the task's
limits. The test passes when the result equals `test.expected`. Tests are run in declared order.
The attempt **passes** only if every test, public and hidden, passes. Partial results are recorded as
diagnostics and never raise the primary score ([evaluation and scoring](evaluation-and-scoring.md),
section 5.2).

`definitions_only` submissions are checked by the harness before running: every top level form is a
definition, every `must_define` entry is present with the stated arity, no definition reuses a
reserved surface name, and no definition repeats a parameter name. These are documented language
rules, not hidden traps. Each violation has a distinct `invalid_submission` detail.

Requiring definitions only means the harness, not the submission, supplies the final expression.
That keeps task grading clear of the definition-last behavior difference between the evaluators
(F1).

### 7.4 Limits

```json
{ "max_steps": 100000, "max_ast_depth": 1000, "max_call_depth": 100,
  "max_submission_bytes": 4096, "wall_clock_ms": 2000 }
```

`max_steps`, `max_ast_depth` and `max_call_depth` are the runtime's existing deterministic limits.
`max_submission_bytes` is checked by the harness before parsing, because the runtime has no source
size limit. Measured on the development machine, parse time grew about linearly: 1,000 expressions
(10 KB) took 0.27 s, 4,000 (40 KB) took 1.14 s and 16,000 (160 KB) took 5.15 s. These figures are
machine specific. The cap values are placeholders until the calibration in milestone M2.11.
`wall_clock_ms` is a backstop for the harness, not a scoring rule (see the
[overview](wave2-overview.md), section 8).

`max_collection_size` and `max_string_size` from requirements.md, Requirement 7, criterion 5 do not
apply: the MVP language has neither collections nor strings.

## 8. Language reference document and prompts

### 8.1 Prompts are derived, not stored

A task stores structured prompt inputs. The prompt text is produced by a versioned
`PromptBuilder(prompt.template)` from `project_public(task)` and the environment. The attempt
record stores the prompt's hash (see the [experiment model](experiment-model.md)). Changing wording
means a new `prompt.template.version`, never an edit in place.

### 8.2 Documentation claims are executable

The language reference is generated from templates. Each sentence template that states a behavior
("`vorn` subtracts its second argument from its first", "arithmetic wraps around at 64 bits") is
paired with an executable check, run against the environment before it is frozen (gate E7). A
documentation sentence that the runtime contradicts blocks the environment. This protects the
benchmark against the most damaging unfairness: documentation that is wrong.

## 9. Task sets, blueprints and splits

A **task set** is the unit that is run and reported.

```text
{ "task_set_id": "tset_<sha256>", "schema_version": 1, "family_version": "f1",
  "blueprint": { "id": "bp1", "version": 1, "slots": [...] },
  "environments": [ { "environment_id": "env_...", "split": "dev" | "heldout" } ],
  "tasks": [ "task_..." ] }
```

A **blueprint** is a fixed list of slots, each `(category, form, difficulty level, information
condition, protocol)`. **Every environment in a task set is instantiated from the same blueprint.**
If a slot cannot be filled for an environment (for example no discriminating query exists), the
environment is rejected and the next derivation index is tried. This balanced design makes
environments comparable and lets micro and macro averages agree (see
[evaluation and scoring](evaluation-and-scoring.md), section 6).

The first blueprint is a proposal, chosen for cost and not yet calibrated: 14 slots per environment
(`EVAL` 2, `SYN` 1, `INF` 3, `CTRL` 2, `CONS` 2, `REC` 2, `ERR` 2). With `E` environments, `B` slots
and `k` samples, a model is run on `E x B x k` attempts, for example `20 x 14 x 1 = 280`. Paired
protocols add treatment tasks on top of this count.

The split assigns whole environments to `dev` (public, used for development and prompt tuning) or
`heldout` (sealed; see the anti-leakage rules in
[evaluation and scoring](evaluation-and-scoring.md), section 8). **A task never changes split.**

## 10. Versioning policy

* Any change to a hashed field of an existing object creates a new object with a new identifier.
* Task sets are immutable. Fixing a bad task produces a new task, a new set and a new
  `task_set_id`. The old set stays valid and is marked `retired` with a pointer to its successor.
* A reported score always names its `task_set_id`, `prompt.template` version,
  `runtime_semantics_version` and `family_version`. Scores from different values of these are not
  comparable and the reporting layer refuses to place them in one table.

## 11. Validation rules

### 11.1 Task rules

| Rule | Check |
|---|---|
| T1 | `schema_version` is known. No unknown fields. No missing required fields. |
| T2 | `task_id` equals the recomputed hash. |
| T3 | `environment_id` resolves to a `frozen` environment. |
| T4 | `category` is allowed for `template.id`. |
| T5 | `expected` is confirmed by production and the independent reference evaluator, plus a `closed_form` when available. If the reference is outside its envelope, reject/defer the task; do not silently replace the independent oracle with production plus a closed form. Disagreement makes the task `INVALID` and it is never used (requirements.md, Requirement 8, criterion 6). |
| T6 | Hidden tests are disjoint from public examples and from the query: no equal canonical call program. |
| T7 | Paired tasks pass the canonical comparison projection in D-001: exact query text for information/example variations; equal translated canonical query for surface renaming; permitted canonical divergence only for declared operator-meaning changes; all non-varied hashed fields equal. |
| T8 | Pairs are checked by running both environments. A pair that varies `environment:operator_meaning` or `environment:semantic_config`, alone or together with other factors, must be **discriminating**: the treatment `expected` differs from the control `expected`, otherwise it cannot measure adaptation. A pair that varies only `environment:surface_names`, `information_condition` or `example_policy` must have **equal** `expected` values, because renaming or rewording must not change the answer, and a difference means the pair is not matched. |
| T9 | Non-triviality: for `value` answers, `expected` is not equal to any literal in the query and not equal to any public example result. |
| T10 | `chance_floor_ppm` is at most 100000. |
| T11 | Oracle envelope: every expected result and reference solution stays at call depth 40 or less. Tasks outside the envelope are rejected/deferred, not verified by production plus a closed form alone. The reference evaluator was measured at about 75 nested calls under the default Python recursion limit. |
| T12 | Leakage lint: no hidden test call, hidden definition source or reference solution text appears anywhere in the prompt built from the public view. |
| T13 | Identifiability (`INF`): for every surface operator used by the query, the public examples leave exactly one consistent canonical meaning within its type class. |
| T14 | Every `must_define` name and arity in the answer spec is consistent with the reference solution. |
| T15 | `limits` do not exceed the global caps recorded in the blueprint. |

### 11.2 Task set rules

| Rule | Check |
|---|---|
| TS1 | Every environment instantiates every blueprint slot. |
| TS2 | Every task's environment belongs to the set. |
| TS3 | Held-out environments share no `environment_id` with the dev split. |
| TS4 | Every pair has a control and at least one treatment, all in the set. |

### 11.3 Conformance corpus

A fixed list of programs with pinned `(status, value, error class)` results, covering every
language feature, every error class, every arithmetic boundary and every message family in
[evaluation and scoring](evaluation-and-scoring.md), section 3.2. It has three uses: it defines
when `runtime_semantics_version` must be bumped, it is run at the start of every experiment as an
attestation (the digest of its results goes into the run manifest), and it detects drift in the
Python or Lark version.

## 12. Worked examples

These three tasks were built for this document with a throwaway script (not committed). Every
expected result was produced by running the canonical program through **both** the production
engine and the reference evaluator, and the two agreed in every case. Every identifier was computed
with the rules in section 1. The surface translation was done by a throwaway implementation of
section 4.2. They are illustrative. When the components are implemented, these examples are
regenerated and become golden vectors (milestone M2.1).

### 12.1 Environments

Environment `A` (short circuit boolean mode, wraparound arithmetic) and a surface profile with
pseudo-word names and a permuted meaning assignment: `vorn` means `sub`, `klet` means `mul`, `prax`
means `add`, `snel` means `div`, `dwim` means `mod`, `zeph` means `and`, `quil` means `or`, `ontu`
means `not`, `rilo` means `eq`, `forge` is `def`, `fork` is `if`, `aye` is `true`, `nay` is `false`.

```json
{
  "environment_id": "env_97960dff81c1c9376f4def607b14ec9a032cb21c7144d555859941cefc068cd3",
  "identity_core": {
    "env_schema_version": 1,
    "runtime_semantics_version": 1,
    "semantic_fingerprint": "2fdbd6c732ac31ace435cf50cf2a7c41692b0bfccde43ce7744fb38d390c7a5c",
    "surface_id": "e93de4929af7b970cc115fabcb8c6b8da26f1ff38eb5ad809918ee5d0e2cc470"
  },
  "runtime": {
    "algorithm_version": "1.0.0",
    "grammar_sha256": "d104c8ec37f6edd0fd91fe1ad627ae09bc5c12722f0b9c935aee6ebde7fa053a",
    "language_id": "lang_c9af44343fcca3bc60480e246361693acf776911a476b2846cd1d82494829ef9",
    "spec_version": "1.0.0"
  },
  "semantic": {
    "arithmetic": "wraparound",
    "short_circuit": true
  },
  "surface_profile": {
    "keywords": {
      "forge": "def",
      "fork": "if"
    },
    "literals": {
      "aye": "true",
      "nay": "false"
    },
    "operators": {
      "dwim": "mod",
      "klet": "mul",
      "ontu": "not",
      "prax": "add",
      "quil": "or",
      "rilo": "eq",
      "snel": "div",
      "vorn": "sub",
      "zeph": "and"
    },
    "profile_schema_version": 1
  }
}
```

Environment `B1` has the same surface profile and the same arithmetic mode and differs only in
`semantic.short_circuit = false`. Its `environment_id` is
`env_b570d50acf956d1fcd207237d274528aaf3ccaa4e9f977f027a55676f80705a3`. The two share the grammar
hash and `surface_id` and differ in `semantic_fingerprint`.

### 12.2 Task 1: operator inference from examples (`INF`)

Capability: infer the meaning of three unfamiliar operators from examples and combine them. No
operator has a familiar name, and no documentation of behavior is given (`SIGNATURES_ONLY`).

Query `(vorn (klet 3 5) (prax 6 2))` translates to `(sub (mul 3 5) (add 6 2))`. Both evaluators give
`7`. Gate T13 holds: for each of `vorn`, `klet` and `prax`, exactly one canonical operation in the
arithmetic class fits the public examples. Gate T9 holds: 7 is neither a literal in the query nor a
public result.

```json
{
  "answer_spec": {
    "allowed_kinds": [
      "int",
      "bool",
      "error"
    ],
    "chance_floor_ppm": 0,
    "type": "value"
  },
  "category": "INF",
  "difficulty": {
    "dimensions": {
      "control_flow": "none",
      "nesting_depth": 2,
      "reasoning_steps": 3,
      "state": "none"
    },
    "level": 2
  },
  "environment_id": "env_97960dff81c1c9376f4def607b14ec9a032cb21c7144d555859941cefc068cd3",
  "evaluation": {
    "limits": {
      "max_ast_depth": 1000,
      "max_call_depth": 100,
      "max_steps": 100000,
      "max_submission_bytes": 256,
      "wall_clock_ms": 2000
    },
    "method": "exact_match"
  },
  "expected": {
    "kind": "value",
    "value": {
      "kind": "int",
      "value": 7
    }
  },
  "information_condition": "SIGNATURES_ONLY",
  "prompt": {
    "example_policy": "neutral",
    "public_examples": [
      {
        "program": "(vorn 9 4)",
        "result": {
          "kind": "int",
          "value": 5
        }
      },
      {
        "program": "(vorn 4 9)",
        "result": {
          "kind": "int",
          "value": -5
        }
      },
      {
        "program": "(klet 6 7)",
        "result": {
          "kind": "int",
          "value": 42
        }
      },
      {
        "program": "(prax 6 7)",
        "result": {
          "kind": "int",
          "value": 13
        }
      },
      {
        "program": "(snel 17 5)",
        "result": {
          "kind": "int",
          "value": 3
        }
      },
      {
        "program": "(dwim 17 5)",
        "result": {
          "kind": "int",
          "value": 2
        }
      }
    ],
    "query": {
      "program": "(vorn (klet 3 5) (prax 6 2))"
    },
    "template": {
      "id": "prompt.answer",
      "version": 1
    }
  },
  "protocol": {
    "kind": "standalone"
  },
  "provenance": {
    "generator": "wave2.0-hand-authored-example",
    "generator_version": 0
  },
  "schema_version": 1,
  "task_id": "task_d8b39b4a758e8637f2014878a3905ffeee7d3db80262fecca75be04c9ed46e2f",
  "template": {
    "id": "inf.operator_by_examples",
    "version": 1
  },
  "verification": {
    "agree": true,
    "gates": {
      "answer_not_in_public_results": true,
      "identifiable": true
    },
    "sources": [
      {
        "name": "production",
        "result": {
          "kind": "int",
          "value": 7
        }
      },
      {
        "name": "reference",
        "result": {
          "kind": "int",
          "value": 7
        }
      }
    ]
  }
}
```

### 12.3 Task 2: paired control-flow task under an unannounced semantic change (`CTRL`)

Capability: notice from evidence that evaluation order changed, and apply it. This is the
`treatment` member of a pair. The `control` member is the same query in environment `A` with
`FULL_DOC`, whose verified expected result is the boolean false (short circuit skips the division).
The treatment environment `B1` evaluates both operands eagerly, so the query raises a division error.
The treatment shows the stale reference of environment `A` plus examples from `B1`. The second
example `(quil aye (snel 1 0))` already shows the division error in `B1`, so the change is inferable
from the evidence without any statement of change. Gate T8 holds: the two expected results differ.

```json
{
  "answer_spec": {
    "allowed_kinds": [
      "int",
      "bool",
      "error"
    ],
    "chance_floor_ppm": 0,
    "error_classes": [
      "syntax",
      "name",
      "arity",
      "type",
      "division_by_zero",
      "overflow",
      "literal_range",
      "resource"
    ],
    "type": "value"
  },
  "category": "CTRL",
  "difficulty": {
    "dimensions": {
      "control_flow": "short_circuit",
      "nesting_depth": 2,
      "reasoning_steps": 2,
      "state": "none"
    },
    "level": 3
  },
  "environment_id": "env_b570d50acf956d1fcd207237d274528aaf3ccaa4e9f977f027a55676f80705a3",
  "evaluation": {
    "limits": {
      "max_ast_depth": 1000,
      "max_call_depth": 100,
      "max_steps": 100000,
      "max_submission_bytes": 256,
      "wall_clock_ms": 2000
    },
    "method": "exact_match"
  },
  "expected": {
    "kind": "value",
    "value": {
      "error_class": "division_by_zero",
      "kind": "error"
    }
  },
  "information_condition": "STALE_DOC_EXAMPLES",
  "prompt": {
    "example_policy": "neutral",
    "public_examples": [
      {
        "program": "(zeph aye (prax 1 2))",
        "result": {
          "error_class": "type",
          "kind": "error"
        }
      },
      {
        "program": "(zeph nay (prax 1 2))",
        "result": {
          "error_class": "type",
          "kind": "error"
        }
      },
      {
        "program": "(ontu nay)",
        "result": {
          "kind": "bool",
          "value": true
        }
      }
    ],
    "query": {
      "program": "(zeph nay (snel 1 0))"
    },
    "template": {
      "id": "prompt.answer",
      "version": 1
    }
  },
  "protocol": {
    "kind": "paired",
    "pair_id": "pair_f314ca0bf73be4f7c6bef7ae9a6b65d6bbe70566644e772ffa78f056a134b8ce",
    "role": "treatment",
    "varies": [
      "environment:semantic_config",
      "information_condition"
    ]
  },
  "provenance": {
    "generator": "wave2.0-hand-authored-example",
    "generator_version": 0
  },
  "schema_version": 1,
  "task_id": "task_0d4bb9712e3e0ca2c4db96dc4391891ced221418b6f0cb49cf80a3ecbf5a0a3e",
  "template": {
    "id": "ctrl.short_circuit_probe",
    "version": 1
  },
  "verification": {
    "agree": true,
    "gates": {
      "base_expected": {
        "kind": "bool",
        "value": false
      },
      "discriminating_vs_base": true
    },
    "sources": [
      {
        "name": "production",
        "result": {
          "error_class": "division_by_zero",
          "kind": "error"
        }
      },
      {
        "name": "reference",
        "result": {
          "error_class": "division_by_zero",
          "kind": "error"
        }
      }
    ]
  }
}
```

### 12.4 Task 3: recursive construction with hidden tests (`REC`)

Capability: write a recursive function from a specification. The reference solution, in surface form,
is `(forge tally (n) (fork (rilo n 0) 0 (prax n (tally (vorn n 1)))))`. It translates to
`(def _u1 (_u2) (if (eq _u2 0) 0 (add _u2 (_u1 (sub _u2 1)))))`. Each expected value matches the
closed form `n(n+1)/2` and both evaluators. The largest hidden test uses `n = 39`, which keeps the
call depth inside the oracle envelope (gate T11). The primary score is 1 only if all five tests pass.

```json
{
  "answer_spec": {
    "form": "definitions_only",
    "must_define": [
      {
        "arity": 1,
        "name": "tally"
      }
    ],
    "type": "program"
  },
  "category": "REC",
  "difficulty": {
    "dimensions": {
      "control_flow": "recursion",
      "nesting_depth": 3,
      "reasoning_steps": 5,
      "state": "none"
    },
    "level": 2
  },
  "environment_id": "env_97960dff81c1c9376f4def607b14ec9a032cb21c7144d555859941cefc068cd3",
  "evaluation": {
    "limits": {
      "max_ast_depth": 1000,
      "max_call_depth": 100,
      "max_steps": 100000,
      "max_submission_bytes": 4096,
      "wall_clock_ms": 2000
    },
    "method": "test_suite",
    "tests": [
      {
        "call": "(tally 0)",
        "expected": {
          "kind": "int",
          "value": 0
        },
        "sources": [
          "closed_form",
          "production",
          "reference"
        ],
        "test_id": "t1",
        "visibility": "public"
      },
      {
        "call": "(tally 4)",
        "expected": {
          "kind": "int",
          "value": 10
        },
        "sources": [
          "closed_form",
          "production",
          "reference"
        ],
        "test_id": "t2",
        "visibility": "public"
      },
      {
        "call": "(tally 1)",
        "expected": {
          "kind": "int",
          "value": 1
        },
        "sources": [
          "closed_form",
          "production",
          "reference"
        ],
        "test_id": "t3",
        "visibility": "hidden"
      },
      {
        "call": "(tally 10)",
        "expected": {
          "kind": "int",
          "value": 55
        },
        "sources": [
          "closed_form",
          "production",
          "reference"
        ],
        "test_id": "t4",
        "visibility": "hidden"
      },
      {
        "call": "(tally 39)",
        "expected": {
          "kind": "int",
          "value": 780
        },
        "sources": [
          "closed_form",
          "production",
          "reference"
        ],
        "test_id": "t5",
        "visibility": "hidden"
      }
    ]
  },
  "expected": {
    "kind": "test_suite",
    "pass_rule": "all_tests"
  },
  "information_condition": "FULL_DOC",
  "prompt": {
    "example_policy": "neutral",
    "public_examples": [
      {
        "program": "(tally 0)",
        "result": {
          "kind": "int",
          "value": 0
        }
      },
      {
        "program": "(tally 4)",
        "result": {
          "kind": "int",
          "value": 10
        }
      }
    ],
    "spec": {
      "arity": 1,
      "behavior": "returns the sum of the integers from 1 through n; returns 0 when n is 0",
      "domain": "n is an int with 0 <= n <= 39",
      "function_name": "tally"
    },
    "template": {
      "id": "prompt.program",
      "version": 1
    }
  },
  "protocol": {
    "kind": "standalone"
  },
  "provenance": {
    "generator": "wave2.0-hand-authored-example",
    "generator_version": 0
  },
  "schema_version": 1,
  "task_id": "task_9236f8560f51ada6561f0626e7c90fee34da4d76011be490ca84e8cd51c5b271",
  "template": {
    "id": "rec.sum_to_n",
    "version": 1
  },
  "verification": {
    "agree": true,
    "gates": {
      "hidden_tests_disjoint_from_public": true,
      "oracle_depth_budget_respected": true
    },
    "reference_solution": {
      "max_call_depth_used": 40,
      "surface": "(forge tally (n) (fork (rilo n 0) 0 (prax n (tally (vorn n 1)))))"
    }
  }
}
```

## 13. Open items for this document

* The mapping from difficulty dimensions to `level` is not defined here. It is part of each
  template and is calibrated in M2.11 from pilot data.
* The blueprint is a proposal. Its slot counts are not measured.
* Exact surface name generation (alphabet and length distribution) is an implementation detail of
  M2.2. The only constraints here are gates E1 and E2.
* Hidden definitions (`input.definitions` with `visibility: hidden`) are specified but have no
  worked example yet.
