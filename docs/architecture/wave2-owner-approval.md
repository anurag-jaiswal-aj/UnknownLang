# Wave 2 Owner-Approval Package

Status: **Owner-authorized scope recorded on 2026-11-24. Implementation and verification remain pending.**
Baseline: Wave 2.0.7, commit `94dea26`.

## Owner authorization record

- **Authorization source:** the project-owner authorization message for Wave 2.0.8 in the current Kiro session.
- **Effective date:** `2026-11-24`.
- **Owner identity:** not recorded; the authorization source is the current owner message only.
- **Authorized scope:** AM-01 through AM-16, F1 through F5 as technical implementation requirements,
  and T-01 through T-10 as proposed technical contracts.
- **Not authorized:** production implementation, official benchmark execution, Docker/WASM waiver,
  scientific-validity approval, or changing the user-owned `tasks.md`.

`owner_approved` means the owner authorized the documented scope and wording. It does not mean
`implemented` or `verified`. Those statuses require later code and validation evidence.

### Approved amendment register

| ID | Status | Date | Source | Affected area | Implementation milestone |
|---|---|---|---|---|---|
| AM-01 | `owner_approved` | 2026-11-24 | Requirements 5.2, 20.1-20.3 | environment identity | M2.1 |
| AM-02 | `owner_approved` | 2026-11-24 | Requirement 9.1, 4.4 | challenge/language-family scope | M2.4/M2.5 |
| AM-03 | `owner_approved` | 2026-11-24 | Requirement 10.4 | weighted scoring | M2.8 |
| AM-04 | `owner_approved` | 2026-11-24 | Requirements 3.5, 11.2 | providers | M2.7/M2.11 |
| AM-05 | `owner_approved` | 2026-11-24 | Requirement 12.5 | authoritative storage | M2.7 |
| AM-06 | `owner_approved` | 2026-11-24 | Requirement 20.8 | void/resource outcomes | M2.6/M2.8 |
| AM-07 | `owner_approved` | 2026-11-24 | Requirement 7.6 | status migration | M2.1 |
| AM-08 | `owner_approved` | 2026-11-24 | Requirement 11.5 | response extraction | M2.6 |
| AM-09 | `owner_approved` | 2026-11-24 | Requirements 15, 20.10 | execution eligibility | M2.6/secure deployment later |
| AM-10 | `owner_approved` | 2026-11-24 | Requirement 3.1-3.2 | research preregistration | M2.11 |
| AM-11 | `owner_approved` | 2026-11-24 | Requirement 3.3 | variant definition | M2.3/M2.5 |
| AM-12 | `owner_approved` | 2026-11-24 | Requirement 4.1 | bounded novelty search | M2.3 |
| AM-13 | `owner_approved` | 2026-11-24 | Requirements 6.5, 7.5 | collection/string scope | later language family |
| AM-14 | `owner_approved` | 2026-11-24 | Requirement 9.3 | program task counts | M2.5/M2.9 |
| AM-15 | `owner_approved` | 2026-11-24 | Requirements 13-19 | product phase scope | later product phase |
| AM-16 | `owner_approved` | 2026-11-24 | frozen grammar limitation | translator boundary | M2.2/M2.6 |

### Approved technical requirement register

| ID | Status | Date | Implementation meaning |
|---|---|---|---|
| F1 | `owner_approved` | 2026-11-24 | Definition-only programs return `None`; production/reference differential corpus required |
| F2 | `owner_approved` | 2026-11-24 | Translator is mandatory on every benchmark execution path; raw parser remains a documented limitation |
| F3 | `owner_approved` | 2026-11-24 | Preserve Python 3.11+ target only after import fixes and matrix validation |
| F4 | `owner_approved` | 2026-11-24 | Implement runtime-bound `environment_id` separately from legacy `language_id` |
| F5 | `owner_approved` | 2026-11-24 | Add structured result diagnostics with backward-compatible serialization migration |
| T-01 through T-10 | `owner_approved` | 2026-11-24 | Implement only after the canonical contracts and validation gates below are satisfied |

No research-validity decision is approved. R1-R13 retain their explicit `PENDING` or `DEFERRED`
statuses in the research register. Official/untrusted execution remains blocked until Docker/WASM
acceptance passes.


This package records decisions needed before Wave 2.1 implementation. It does not change
`.kiro/specs/unknownlang/requirements.md` or `.kiro/specs/unknownlang/design.md` on its own.

## Part 1. Current project state

### Implemented

- Deterministic Wave 1 language generation.
- Frozen Lisp grammar and Lark parsing.
- Iterative production evaluator.
- Independent recursive reference evaluator.
- Signed 64-bit integer contract.
- Three arithmetic modes and two boolean evaluation modes.
- Lexical scoping and strict runtime types.
- AST depth, step and call-depth limits.
- Shared execution types and compatibility facade.
- Wave 1 tests: 1,142 passing on the verified local Python/Lark environment.

### Designed only

The following Wave 2 components have architecture documents but no production implementation:

- environment manager and surface translator;
- task schema validators and task generators;
- benchmark harness;
- scoring engine and weighted score;
- model adapter interface and adapters;
- filesystem store and hash-chain replay;
- report model;
- Docker/WASM official-run isolation;
- task-set generation and held-out split tooling.

`src/benchmark`, `src/challenge` and `src/models` remain placeholders. No Wave 2 benchmark runner
exists.

### Not safe for untrusted execution

The current runtime is not a process-level sandbox. It does not enforce host filesystem isolation,
network isolation, reliable memory isolation, or privilege separation. A watchdog subprocess would be
a trusted-local containment mechanism, not a security sandbox.

Only the following execution class is currently defensible:

```text
trusted_local = development or explicitly labelled local pilot
```

`official_sandboxed` and `untrusted` execution require Docker or WASM isolation first.

### Current runtime findings

- F1: definition-only programs return `True` in production and `None` in the reference evaluator.
- F2: raw grammar keyword-prefix ambiguity remains.
- F3: `canonical.py` and `serializer.py` fail on Python 3.11–3.13 because of missing typing imports.
- F4: legacy `language_id` is seed-derived and omits runtime behavior.
- F5: `ExecutionResult` lacks structured error kinds, step counts and AST-depth diagnostics.

These findings are documented in `runtime-findings.md`. None was silently fixed in this milestone.

## Part 2. Decisions requiring owner approval

Every row is intentionally unchecked. The lead agent cannot approve any normative amendment.

### AM-01 - Environment identity

**Original requirement:** Requirements 5.2 and 20.1–20.3 define identity around
`SHA256(canonical_seed + spec_version + algorithm_version)`.

**Current proposal:** Preserve legacy `language_id` as a compatibility identifier and add
`environment_id` over grammar, complete semantic specification, surface profile, generator family and
algorithm versions, and runtime semantics version.

**Exact proposed amendment:**

> The existing seed-derived `language_id` SHALL remain a compatibility identifier. The Wave 2
> benchmark SHALL additionally identify an executable environment with a versioned hash of its
> canonical grammar, complete semantic specification, surface profile, generator family and
> algorithm versions, and runtime semantics version. Generated timestamps and host runtime versions
> SHALL remain metadata. The two identifiers SHALL NOT be used interchangeably.

**Alternative:** Retain the seed-only identity and accept that runtime changes and observable-equivalent
seeds can share or split identities. This weakens reproducibility claims.

**Consequences:** New environment records and a runtime-version constant are required. Old
`language_id` values remain readable but are not sufficient for Wave 2 comparisons.

**Recommendation:** Approve AM-01.

**Owner approval:** `[x] Owner-authorized on 2026-11-24; implementation pending`

### AM-02 - Challenge capability scope

**Original requirement:** Requirement 9.1 requires array operations, string manipulation, recursion,
sorting and search.

**Current proposal:** Use only categories expressible by the Wave 1 language: syntax comprehension,
expression evaluation, semantic inference, control-flow reasoning, program construction, recursion and
error interpretation.

**Exact proposed amendment:**

> The MVP task categories SHALL be limited to capabilities expressible by the MVP language. Wave 2
> categories are syntax comprehension, expression evaluation, semantic inference, control-flow
> reasoning, program construction, recursion and error interpretation. Array, string, sorting and
> search categories require a later language-family extension.

**Alternative:** Add collections, strings, loops and sorting/search semantics before the benchmark.
That expands Wave 2 beyond the current frozen runtime.

**Consequences:** Wave 2 makes a narrower scientific claim and cannot claim coverage of the original
challenge categories.

**Recommendation:** Approve the narrow scope and plan a later language-family extension.

**Owner approval:** `[x] Owner-authorized on 2026-11-24; implementation pending`

### AM-03 - Weighted score and research headline

**Original requirement:** Requirement 10.4 mandates
`weighted_score = sum(raw_score_i * difficulty_weight_i) / sum(difficulty_weight_i)`.

**Current proposal:** Report the required weighted score `W` as a first-class metric. Retain unweighted
held-out accuracy as a separate research headline only.

**Exact proposed amendment:**

> The platform SHALL compute and report the normalized difficulty-weighted correctness score. An
> unweighted held-out accuracy MAY be reported as a separate research headline. Both values SHALL
> identify the task set, weight-function version, runtime version and prompt version.

**Alternative:** Use only unweighted accuracy. This directly drops a normative metric.

**Consequences:** Difficulty weights must be positive, versioned and present in the task-set blueprint.
All-void tasks contribute no weight. Incomplete runs are provisional and cannot be ranked officially.

**Recommendation:** Approve the weighted score and retain the unweighted metric as diagnostic/research
context.

**Owner approval:** `[x] Owner-authorized on 2026-11-24; implementation pending`

### AM-04 - Provider order

**Original requirements:** Requirement 3.5 names Ollama for the free local baseline. Requirement 11.2
names OpenAI-compatible APIs as the first implementation.

**Current proposal:** Deterministic mock first, local Ollama first real provider, optional
OpenAI-compatible transport later.

**Exact proposed amendment:**

> The first real provider SHALL be a local Ollama adapter. An OpenAI-compatible adapter MAY follow as
> an optional transport. A deterministic mock adapter SHALL always be available for tests. No paid or
> externally hosted provider is required for the zero-cost baseline.

**Alternative:** Implement an OpenAI-compatible provider first, requiring external network/credentials,
or retain Ollama as required first provider and reject the OpenAI-first criterion.

**Consequences:** No real provider is available until Ollama integration is implemented. Mock-only
runs validate engineering but not model behavior.

**Recommendation:** Approve mock-first and Ollama-first.

**Owner approval:** `[x] Owner-authorized on 2026-11-24; implementation pending`

### AM-05 - Storage

**Original requirement:** Requirement 12.5 requires SQLite for the MVP.

**Current proposal:** Content-addressed files and append-only hash-chained run records are the source
of truth. SQLite is a later disposable derived index.

**Exact proposed amendment:**

> Wave 2 SHALL use content-addressed files and append-only hash-chained run records as the source of
> truth. SQLite MAY be generated later as a disposable derived index and SHALL not be a second writable
> source of truth.

**Alternative:** Select SQLite as authoritative storage and define migrations, transactions, exports and
replay integrity there.

**Consequences:** Files are human-readable and zero-cost, but ad hoc querying is weaker and hash-chain
integrity is tamper-evident rather than tamper-proof.

**Recommendation:** Approve files for Wave 2 only if the claim is narrowed to trusted-runner auditability.

**Owner approval:** `[x] Owner-authorized on 2026-11-24; implementation pending`

### AM-06 - Resource-limit outcomes

**Original requirement:** Requirement 20.8 requires a distinct inconclusive status, not a failed or
incorrect result.

**Current proposal:** Resource-limit outcomes are void for correctness, retained diagnostically, and
make a run provisional. Official runs require zero resource-limit/infrastructure voids unless an
explicit approved cap is introduced.

**Exact proposed amendment:**

> Resource-limit outcomes SHALL be excluded from correctness numerators and denominators, retained as
> a distinct diagnostic, and make an official run provisional unless an approved resource-rate cap is
> satisfied. They SHALL never be silently converted to model failures or successes.

**Alternative:** Score resource outcomes as zero. This is easier to aggregate but conflicts with the
inconclusive requirement and conflates resource usage with correctness.

**Consequences:** A run with void attempts cannot be an official ranking result. Provisional diagnostic
metrics may still be displayed with void counts.

**Recommendation:** Approve the distinct-void policy.

**Owner approval:** `[x] Owner-authorized on 2026-11-24; implementation pending`

### AM-07 - Execution status

**Original requirement:** Requirement 7.6 requires `invalid_program`; the current runtime returns
`error` for parse failures.

**Current proposal:** Add a boundary mapping from legacy `error + error_kind=syntax` to
`invalid_program`, or change the runtime in a later approved runtime milestone.

**Exact proposed amendment:**

> The execution boundary SHALL expose `invalid_program` for parse and validation failures and retain
> `error` for executed semantic failures. During migration, the harness MAY map legacy `error` plus
> structured `error_kind=syntax` to `invalid_program`; the compatibility mapping SHALL be versioned
> and recorded in the run manifest.

**Alternative:** Keep all parse failures as `error` and amend the requirement instead.

**Consequences:** The runtime result contract, serializer and tests need a versioned migration. No
Wave 2 implementation can claim this status compliance before the migration or amendment.

**Recommendation:** Approve the boundary mapping first; implement runtime changes only in a later
approved milestone.

**Owner approval:** `[x] Owner-authorized on 2026-11-24; implementation pending`

### AM-08 - Response extraction

**Original requirement:** Requirement 11.5 permits extracting code from Markdown code blocks or the
entire response.

**Current proposal:** Use the last fenced block when present; otherwise use the entire response for
program tasks. Use the final `ANSWER:` line for value tasks.

**Exact proposed amendment:**

> Program extraction SHALL use the last fenced code block when one exists; otherwise the entire
> response SHALL be treated as the candidate program. Value tasks SHALL use the final `ANSWER:` line.
> Extraction method and failures SHALL be recorded.

**Alternative:** Accept only fenced blocks. This is stricter but drops the required entire-response
fallback.

**Consequences:** Prose-only responses may become syntax failures rather than extraction failures;
the extraction method and failure category must be explicit.

**Recommendation:** Approve the fallback with strict size and parsing rules.

**Owner approval:** `[x] Owner-authorized on 2026-11-24; implementation pending`

### AM-09 - Sandbox scope

**Original requirements:** Requirements 15 and 20.10 require Docker/WASM process isolation for
untrusted execution.

**Current proposal:** Trusted-local watchdog pilots are permitted. Official and untrusted execution
requires Docker/WASM.

**Exact proposed amendment:**

> Trusted-local design and development runs MAY use a watchdog subprocess and SHALL be labelled
> `trusted_local`. Official and untrusted execution SHALL require Docker or WASM isolation with no
> network, temporary filesystem, CPU/memory/output controls and an attested runtime image.

**Alternative:** Implement Docker/WASM before any benchmark execution.

**Consequences:** Trusted-local pilots can proceed without claiming security compliance. Official model
runs remain blocked until the sandbox is implemented and validated.

**Recommendation:** Approve trusted-local-only Wave 2 design validation, but do not approve official
execution without the sandbox.

**Owner approval:** `[x] Owner-authorized on 2026-11-24; implementation pending`

### AM-10 - Research hypothesis protocol

**Original requirements:** Requirement 3.1 requires a 50th-percentile comparison between models and
held-out language variants. Requirement 3.2 requires a complexity/degradation correlation.

**Proposed amendment:**

> The Wave 2 benchmark SHALL preregister the model population, percentile calculation, held-out
> endpoint, comparison statistic and non-circular analysis before real-model evaluation. Grammar-rule
> count and token-diversity correlation SHALL be deferred unless the benchmark generates observable
> grammar variation. Surface-name and semantic-configuration factors SHALL not be described as
> grammar complexity.

**Owner approval:** `[x] Owner-authorized on 2026-11-24; implementation pending`

### AM-11 - Variant count

**Original requirement:** Requirement 3.3 requires at least 100 unique language variants per difficulty
level in one execution.

**Proposed amendment:**

> For the fixed Wave 1 grammar family, a variant SHALL mean a reproducibly identified environment
> consisting of a validated surface profile and semantic configuration. Wave 2 SHALL generate at least
> 100 such variants per difficulty only if the owner accepts surface/environment variants as the unit.
> A requirement for 100 genuinely different grammar families is deferred to a later language-family
> milestone.

**Owner approval:** `[x] Owner-authorized on 2026-11-24; implementation pending`

### AM-12 - Novelty and public-data verification

**Original requirement:** Requirement 4.1 requires verifying that no language version exists in public
repositories or training datasets and recording the result with a timestamp.

**Proposed amendment:**

> The platform SHALL report a bounded search over named public repositories, indexes and datasets,
> including query method, search timestamp and “not found in searched sources” results. It SHALL NOT
> claim to prove absence from all training datasets. Family-level contamination remains an explicit
> research limitation.

**Owner approval:** `[x] Owner-authorized on 2026-11-24; implementation pending`

### AM-13 - Collection and string limits

**Original requirement:** Requirement 6.5 and Requirement 7.5 include collection and string limits.

**Proposed amendment:**

> Collection and string limits SHALL be deferred for the integer/boolean Wave 2 language because the
> language has no collection or string values. The requirement becomes active when a later language
> family adds those types. Wave 2 SHALL retain output, AST, step and call-depth limits.

**Owner approval:** `[x] Owner-authorized on 2026-11-24; implementation pending`

### AM-14 - Program test-count scope

**Original requirement:** Requirement 9.3 requires 3–5 public examples and 10–20 total tests per
challenge.

**Proposed amendment:**

> Program-construction challenges SHALL contain 3–5 public examples and 10–20 total tests, including
> hidden edge cases. Single-query value tasks are a separate form and SHALL declare their answer-space,
> query and verification rules; they SHALL not be described as satisfying the program-challenge count.

**Owner approval:** `[x] Owner-authorized on 2026-11-24; implementation pending`

### AM-15 - API, frontend, deployment and demo phase scope

**Original requirements:** Requirements 13–19 describe API, frontend, deployment, demo and MVP phase
contents.

**Proposed amendment:**

> API, frontend, deployment, cloud, authentication and demo requirements are assigned to a later
> product phase. Wave 2 is a local design/benchmark-core phase and SHALL not claim those capabilities
> are implemented. The historical Phase 1 checklist is planning context, not repository acceptance.

**Owner approval:** `[x] Owner-authorized on 2026-11-24; implementation pending`

### AM-16 - Raw parser workaround

**Original requirement:** The frozen parser/interpreter contract remains normative for direct runtime
callers.

**Proposed decision:**

> The benchmark SHALL use the surface translator on every benchmark execution path, including
> submissions, hidden definitions, appended test calls and reference-generated surface programs. The
> raw keyword-prefix parser ambiguity remains a documented Wave 1 limitation and is not claimed fixed.
> A grammar word-boundary correction requires a later grammar-version decision.

**Owner approval:** `[x] Owner-authorized on 2026-11-24; implementation pending`



These corrections do not approve normative amendments, but they are required before implementation.

## Part 3. Technical corrections



Use `pair_group_id` as the sole authoritative field. A pair group contains exactly one control and at
least one treatment. Its hash input is role-labelled and includes:

- pair schema version;
- template/version;
- category and difficulty dimensions;
- sorted variation list;
- role-labelled member task projections;
- role-labelled environment IDs;
- information conditions and example policies;
- canonical query projection.

The member projection excludes the pair ID, task ID, verification and provenance to avoid circular
hashing. `pair_id` is not an alias and must not remain in normative records.

### T-02 Canonical comparison projection

- information/example policy: exact query text and canonical query equal;
- surface-name variation: surface text may differ, canonical translated query must equal;
- operator-meaning variation: surface tokens remain equal, canonical meaning may differ;
- semantic configuration: canonical query remains equal, expected results must differ;
- all non-varied hashed fields must equal.

Structured expected results compare type/kind and value/error class, not JSON formatting.

### T-03 D8 trusted reference-cost artifact

A trusted harness executes the verified reference solution using the production evaluator and emits a
validated artifact containing:

```json
{
  "task_id": "task_...",
  "reference_digest": "sha256:...",
  "runtime_semantics_version": 1,
  "tests": [{"test_id": "t1", "reference_steps": 11, "upper_bound_verified": true}],
  "provenance": {"sources": ["production", "reference"], "agreement": true},
  "artifact_sha256": "..."
}
```

Scoring consumes the artifact and never reads private reference source code. Missing or mismatched
artifacts make D8 unavailable and the run provisional.

### T-04 Content-addressed validation

Before any task, environment, task-set or artifact is used, the resolver must recompute its full
content hash, verify its filename and embedded ID, verify every cross-reference and verify every
referenced artifact digest. Hash chains detect accidental modification but are not signatures.

### T-05 Golden fixtures

The current examples remain illustrative. They are not normative golden fixtures because no committed
Wave 2 validator or fixture runner exists. Before implementation, regenerate them with T1-T15, TS1-TS4,
T7-T9, pair identity, public/hidden, expected-result and environment-identity checks.

Task 2's narrative must match its JSON. Task 3's five-test example remains outside Requirement 9.3's
10-20 total challenge-test requirement unless SD8 is approved or the fixture is expanded.

### T-06 D8 zero-reference handling

Use the required table:

| Submission | Reference | Ratio |
|---:|---:|---|
| 0 | 0 | null |
| positive | 0 | null, counted as zero-reference |
| 0 | positive | 0 |
| positive | positive | submission/reference |

A task is eligible only when at least one valid test has positive reference steps. Zero-reference
counts and excluded-task counts are reported. Infinity is never serialized.

### T-07 Bootstrap bytes

For each selection, hash the UTF-8 bytes of strict canonical JSON:

```text
[task_set_id, metric_id, draw_index, position]
```

Rejection retries append `rejection_index` as a fifth field. Interpret SHA-256 as an unsigned
big-endian integer, use `floor(2^256 / m) * m`, rejection sampling and `x mod m`. No Python random,
platform-native encoding or modulo-only sampling.

### T-08 Scoring eligibility and P3 interpretation

P3 uses defined task pass rates for all eligible pair groups. A scored-but-failed control contributes
zero downside loss; an all-void control is ineligible. The signed effect remains diagnostic and is
shown beside the downside-only loss.

P2 may compute a diagnostic mean over defined categories, but official complete runs require every
blueprint category and both splits to have scored coverage. P4 is null if either split P2 is null.
D1-D3 and D9/D12 use the eligibility rules in `scoring-contract.md`.

The weighted score excludes all-void tasks from both numerator and weight denominator. Any void attempt
makes a run provisional; it cannot be ranked as official. Missing attempts are distinct from scored
failures and are never assigned zero silently.

### T-10 Composite chance floors

Marginal per-query chance floors may be multiplied only when the baseline guessing distribution is
explicitly independent and the task requires all component answers. Otherwise the owner must choose an
empirical seeded baseline or conservative joint bound. A marginal floor is not a guarantee against
correlated guesses.



## Part 4. Security decision



- watchdog subprocess may be used as a backstop;
- no claim of sandbox security;
- no untrusted users or public submissions;
- no official security-compliant benchmark ranking;
- results labelled `trusted_local` and provisional unless all scientific gates pass;
- lower scope, but the research claims remain limited.

### Alternative B - Docker/WASM before benchmark execution

- implement no-network, temporary-filesystem and resource-isolated execution first;
- attest image/runtime identity;
- validate CPU, memory and output limits;
- permit official/untrusted benchmark execution only after sandbox acceptance tests pass;
- larger implementation scope, but satisfies the security requirement.

**Recommendation:** Choose Alternative A for local architecture validation only. Choose Alternative B
before any official or untrusted model-generated execution.

**Owner decision:** `[x] Alternative A owner-authorized on 2026-11-24  [ ] Alternative B  [ ] Needs discussion`

## Research register

| ID | Question | Required evidence/method | Decision gate | Owner | Status |
|---|---|---|---|---|---|
| R1 | Does the family require adaptation? | preregistered held-out study with model population and endpoint | AM-10, AM-11 | owner + research lead | PENDING |
| R2 | Are tasks calibrated for floor/ceiling? | pilot difficulty and model-performance data | AM-10 | owner + research lead | DEFERRED |
| R3 | Are categories distinct? | category-level performance and factor analysis after pilot | AM-10 | owner + research lead | DEFERRED |
| R4 | Family-level contamination | bounded source-search protocol and new-family policy | AM-12 | owner | PENDING |
| R5 | Documentation versus inference | FULL_DOC versus EXAMPLES_ONLY controlled comparison | AM-10 | research lead | PENDING |
| R6 | Equal difficulty across semantic configurations | balanced task-set calibration | AM-10, AM-11 | research lead | DEFERRED |
| R7 | Required environment count/power | preregistered power analysis from pilot effects | AM-10 | research lead | DEFERRED |
| R8 | Prompt sensitivity | multiple prompt-template pilot | AM-10 | research lead | DEFERRED |
| R9 | Tokenizer effects | token-matched or measured surface controls | AM-02, AM-10 | research lead | PENDING |
| R10 | Fairness of familiar-name permutations | paired familiar/pseudo pilot with signed effects | AM-02, AM-10 | owner + research lead | PENDING |
| R11 | Error-class answers versus raw messages | human/model usability pilot | AM-07, AM-08 | research lead | DEFERRED |
| R12 | Human baseline | approved human study protocol | AM-10 | owner + research lead | DEFERRED |
| R13 | Interactive learning | bounded interactive protocol design and pilot | AM-15 | owner + research lead | DEFERRED |

These statuses are planning statuses, not owner approvals. No research question is scientifically
resolved by the Wave 1 regression suite or by documentation checks.

## Part 5. Research scope

### Alternative A - narrow family claim

The benchmark measures adaptation to surface names, operator mappings and six arithmetic/boolean
configurations within one small integer/boolean/function language family. It does not claim entirely
new language generation, grammar-complexity effects or general reasoning. The 100-variant requirement
is interpreted as 100 reproducible environment/profile variants, subject to an explicit definition.

### Alternative B - genuine grammar-family generation

Implement multiple grammar families, new operation/type capabilities, grammar-rule and token-diversity
measurements, and a 100-variant-per-difficulty generator. This is a new language-runtime milestone,
not a Wave 2 harness-only milestone.

**Recommendation:** Choose Alternative A for Wave 2 and amend the broader novelty/complexity claims.
Choose Alternative B only if the owner wants to expand scope substantially.

**Owner decision:** `[x] Alternative A owner-authorized on 2026-11-24  [ ] Alternative B  [ ] Needs discussion`

## Part 6. Final approval checklist

The owner authorization has marked the decisions listed below as `owner_approved`. This does not mark
anything implemented or verified. Research-register items remain pending/deferred, and alternative B
options remain unselected.

- `[x] owner_approved` AM-01 environment identity
- `[x] owner_approved` AM-02 challenge capability scope
- `[x] owner_approved` AM-03 weighted score and headline
- `[x] owner_approved` AM-04 provider order
- `[x] owner_approved` AM-05 storage source of truth
- `[x] owner_approved` AM-06 resource-limit treatment
- `[x] owner_approved` AM-07 execution status migration
- `[x] owner_approved` AM-08 response extraction
- `[x] owner_approved` AM-09 sandbox scope
- `[x] owner_approved` AM-10 research hypothesis protocol
- `[x] owner_approved` AM-11 variant-count definition
- `[x] owner_approved` AM-12 bounded novelty/public-data verification
- `[x] owner_approved` AM-13 collection/string-limit scope
- `[x] owner_approved` AM-14 program test-count scope
- `[x] owner_approved` AM-15 API/frontend/deployment/demo phase scope
- `[x] owner_approved` AM-16 raw-parser translator workaround
- `[x] owner_approved` F1 definition-only runtime contract
- `[x] owner_approved` F2 raw-parser translator boundary
- `[x] owner_approved` F3 Python support and compatibility matrix
- `[x] owner_approved` F5 structured execution-result contract
- `[x] owner_approved` T-01 authoritative pair-group identity
- `[x] owner_approved` T-03 trusted reference-cost artifact boundary
- `[ ]` official execution class and Docker/WASM policy
- `[ ]` Composite chance-floor policy and correlated-guess baseline
- `[ ]` research scope: narrow family or genuine grammar-family generation
- `[ ]` historical `design.md` status corrections

Until these fields are completed by the owner, Wave 2.1 implementation must not begin.
