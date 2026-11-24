# Wave 2 Requirements Traceability

Status: **Proposed. Approval required for every `DEVIATES`, `DEFERS`, `CONFLICTS` and
`BLOCKED` entry.** No normative requirements file was modified.

This matrix compares the actual normative documents with the Wave 2 proposal. `DESIGN` means the
architecture describes a path to satisfy the requirement but code is not yet implemented. `PARTIAL`
means some criteria are covered and others are not. `DEVIATES` means the proposal intentionally differs
and needs an amendment. `DEFERS` means the work is outside Wave 2 and remains open. `BLOCKED` means an
official run cannot claim compliance until a prerequisite exists.

## 1. Requirement matrix

| Requirement | Normative subject | Current Wave 2 disposition | Evidence and required action |
|---|---|---|---|
| R1 | Personas, priorities, zero-cost preference, 15-minute quick start | `PARTIAL / DEFERRED` | Product/persona work is not part of the architecture milestone. The zero-cost preference is satisfied. Persona and demo acceptance criteria remain open |
| R2 | Competitor research and technology assessment | `PARTIAL` | Design discusses benchmark differentiation but does not contain auditable source artifacts for every requested competitor or the full Racket/ANTLR/Lark/Trealla/WASM matrix. Add research evidence before claiming compliance |
| R3 | Primary/secondary hypotheses, 100 variants per difficulty, deterministic oracle, Ollama plus mock | `DEVIATES / BLOCKED` | No operational 50th-percentile protocol, grammar/token-diversity correlation, 100-variant generation contract or Ollama adapter exists. Add an amendment or implement those items |
| R4 | Novel-language differentiation, public-data verification, repeatability | `DEVIATES` | Surface profiles are controlled renamings over a fixed grammar, not entirely new languages. Global training-data absence cannot be proven. Replace with a bounded search claim or add a grammar family |
| R5 | Seed dictionary, identity, grammar, declarative generation, conflict checking, semantic dimensions, rejection | `PARTIAL / DEVIATES` | Generator accepts a `LanguageSeed`, not a dictionary; `detect_conflicts` is a stub; identity has a separate Wave 2 proposal; surface profiles are an added benchmark factor, not a semantic dimension. Approve D-003 and implement gates before compliance |
| R6 | Formal LanguageSpec fields, semantics, builtins, limits, examples, timestamp | `PARTIAL` | `SemanticSpec` fields are present, but current `LanguageSpec` lacks resource limits, examples, generated timestamp and explicit difficulty fields. Environment/task records can carry them, but the LanguageSpec contract remains incomplete |
| R7 | Lark AST, fixed engine, types, limits, typed statuses, lexical scope | `PARTIAL / BLOCKED` | Runtime and limits exist, but `invalid_program` is not emitted and no process sandbox exists. Adopt D-008 or amend R7.6; enforce Docker/WASM before untrusted official execution |
| R8 | Independent oracle, cross-validation, disagreement invalidation and mismatch reporting | `PARTIAL / DEVIATES` | Reference evaluator is separate from production evaluation but shares Lark/grammar and fallback T5 permits production plus closed form. Restrict claims or add an independent parser/oracle path; never use disagreement as a pass |
| R9 | Required challenge categories, difficulty, examples/tests, hidden edge cases, reference verification | `DEVIATES` | Current runtime cannot express arrays, strings, sorting or search. Current proposal permits fewer than 3 public or 10 total tests. Amend R9.1/R9.3 or extend the language |
| R10 | Workflow, test-case pass rate, public-hidden gap, weighted score, comparability | `PARTIAL / DEVIATES` | Workflow and gap are designed. Whole-task accuracy is primary and weighted score is not first-class. Scoring contract now requires weighted score W, but approval/amendment is still required |
| R11 | Adapter interface, OpenAI-compatible first, extensibility, prompt privacy, extraction | `PARTIAL / DEVIATES` | Interface is designed and mocks are first. Ollama is the proposed first real adapter; OpenAI is deferred; last-block/ANSWER extraction differs from entire-response fallback. Approve D-010 and amend R11.2/R11.5 if retained |
| R12 | Database fields, runs/results, SQLite MVP | `DEVIATES` | Files and hash chain are the proposed source of truth. Amend R12.5 to make SQLite optional/derived, or select SQLite |
| R13 | REST API, JSON, jobs, errors, OpenAPI | `DEFERS` | No API is implemented or authorized in Wave 2. Preserve as a later phase and amend phase ownership if these requirements are current MVP obligations |
| R14 | Frontend pages and user journeys | `DEFERS` | No frontend is implemented or authorized. Preserve as a later phase and amend phase ownership |
| R15 | Docker/WASM, CPU/memory/output/network/filesystem/security | `BLOCKED` | Watchdog subprocess is not a sandbox. Only trusted-local development may proceed without Docker/WASM; no untrusted or security-compliant official run |
| R16 | 80% tests, integration/E2E, seeds and reproducibility context | `DESIGN` | Architecture specifies unit/integration/E2E milestones, seed recording and manifests. Not implemented yet |
| R17 | Docker deployment, env config, local/free-tier deployment, compose services | `DEFERS / DEVIATES` | No deployment is implemented. The legacy design's compose topology also conflicts with the proposed files/no-API architecture. Amend phase ownership |
| R18 | Live demo, challenge creation, 2-3 models, result comparison | `DEFERS` | No demo or model integration is implemented. Preserve for later phase and do not mark historical checkboxes complete |
| R19 | 48-hour MVP and phase contents | `CONFLICTS` | Original design marks API/frontend/OpenAI/demo complete, but the actual repository does not contain them and Wave 2 defers them. Correct historical status or formally re-scope phases |
| R20 | Versioned execution, seeds, leakage, fairness, generalization, resource status, audit trail, sandbox | `PARTIAL / BLOCKED` | Versioning, seeds, leakage controls and audit trail are designed. Resource-limit scoring and sandboxing deviate. Approve D-005/D-009 and amend R20.8/20.10 if needed |

## 2. Exact amendment proposals

These are proposed wording changes, not applied changes.

### AM-01: environment identity

**Current:** Requirement 5 criterion 2 defines language identity as
`SHA256(canonical_seed + spec_version + algorithm_version)`.

**Proposed:**

> The existing seed-derived `language_id` SHALL remain a compatibility identifier. The Wave 2
> benchmark SHALL additionally define an `environment_id` over canonical grammar, complete semantic
> specification, surface profile, generator family/algorithm versions and runtime semantics version.
> Generated timestamps and host runtime versions SHALL remain metadata. The two identifiers SHALL NOT
> be used interchangeably.

### AM-02: challenge capability scope

**Current:** Requirement 9 criterion 1 requires array operations, string manipulation, recursion,
sorting and search.

**Proposed:**

> The MVP task categories SHALL be limited to capabilities expressible by the MVP language. Wave 2
> categories are syntax comprehension, expression evaluation, semantic inference, control-flow
> reasoning, program construction, recursion and error interpretation. Array/string/sorting/search
> categories require a later language-family extension.

### AM-03: weighted score and headline

**Current:** Requirement 10 criterion 4 requires a weighted correctness score.

**Proposed:**

> The platform SHALL compute and report the normalized difficulty-weighted score. An unweighted
> held-out accuracy MAY be reported as a separate research headline. Both values SHALL identify their
> task-set, weight-function and prompt versions.

### AM-04: provider order

**Current:** Requirement 3 criterion 5 names Ollama; Requirement 11 criterion 2 names OpenAI-compatible
APIs first.

**Proposed:**

> The first real provider SHALL be a local Ollama adapter. An OpenAI-compatible adapter MAY follow as
> an optional transport. A deterministic mock adapter SHALL always be available for tests. No paid or
> externally hosted provider is required for the zero-cost baseline.

### AM-05: storage

**Current:** Requirement 12 criterion 5 requires SQLite for the MVP.

**Proposed:**

> Wave 2 SHALL use content-addressed files and append-only hash-chained run records as the source of
> truth. SQLite MAY be generated later as a disposable derived index and SHALL not be a second writable
> source of truth.

### AM-06: resource-limit outcomes

**Current:** Requirement 20 criterion 8 requires a distinct inconclusive status, not a failed/incorrect
result.

**Proposed:**

> Resource-limit outcomes SHALL be excluded from correctness numerators and denominators, retained as a
> distinct diagnostic, and make an official run provisional unless an approved resource-rate cap is
> satisfied. They SHALL never be silently converted to model failures or successes.

### AM-07: execution status

**Current:** Requirement 7 criterion 6 requires `invalid_program`, while the runtime currently returns
`error` for parse failures.

**Proposed:**

> The execution boundary SHALL expose `invalid_program` for parse/validation failures and retain
> `error` for executed semantic failures. During migration, the harness MAY map legacy `error` plus
> structured `error_kind=syntax` to `invalid_program`; the compatibility mapping SHALL be versioned.

### AM-08: response extraction

**Current:** Requirement 11 criterion 5 permits a Markdown code block or the entire response.

**Proposed:**

> Program extraction SHALL use the last fenced code block when one exists, otherwise the entire response
> SHALL be treated as the candidate program. Value tasks SHALL use the final `ANSWER:` line. Extraction
> method and failures SHALL be recorded.

### AM-09: sandbox scope

**Current:** Requirements 15 and 20 require Docker/WASM process isolation.

**Proposed:**

> Trusted-local design and development runs MAY use a watchdog subprocess and SHALL be labelled
> `trusted_local`. Official/untrusted execution SHALL require Docker or WASM isolation with no network,
> temporary filesystem, CPU/memory/output controls and an attested runtime image.

## 3. Missing requirements to add to the decision register

The following are not SD1-SD10 but must be dispositioned:

- Requirement 3.1: define model population, percentile method, held-out endpoint and avoid circular
  selection when testing the 50th-percentile hypothesis.
- Requirement 3.2: either add real grammar/token-diversity variation or amend the hypothesis to a
  measurable surface/semantic complexity factor.
- Requirement 3.3: define what counts as a unique variant and generate at least 100 per difficulty,
  or amend the count to a later family-extension phase.
- Requirement 4.1: replace global training-data absence with a bounded source-search protocol and
  timestamped result.
- Requirement 6.5: either implement collection/string limits or state that they are deferred with a
  later language-family amendment.
- Requirements 13-19: assign API, frontend, deployment and demo criteria to later phases explicitly;
  do not retain historical `[x]` claims that the repository cannot support.

## 4. Approval gate

Wave 2 is approval-ready only after the project owner accepts the proposed amendments or chooses to
implement the original requirements. Until then, the traceability status remains accurate: the
architecture is coherent as a proposed trusted-local design, but it is not compliant with all current
normative requirements.
