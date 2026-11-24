# Wave 2.0.9 Decision Register

Status: **Owner-authorized scope recorded on 2026-11-24. Implementation and verification remain pending.**
The authorization source is the current Wave 2.0.9 Kiro message; no owner identity or signature is
recorded. No production implementation is authorized by this document.

This register is authoritative for the Wave 2 design. When an older Wave 2 document conflicts with
this register or [scoring-contract.md](scoring-contract.md), the older wording is superseded. The
normative requirements and original design are changed only by the approved amendment overlay in
`requirements.md`; no implementation status is implied by `owner_approved`.

## Decision status

| Status | Meaning |
|---|---|
| `DESIGN_DECISION` | Consistent with the current requirements and can be implemented after approval |
| `PROPOSED_AMENDMENT` | The proposal deliberately differs from a normative requirement. The exact amendment is recorded |
| `DEFERRED` | Not in Wave 2. The requirement remains open and must not be reported as satisfied |
| `BLOCKED` | Cannot be used for an official run until a prerequisite is approved or implemented |

## Register

### D-001: Task pair equivalence - `DESIGN_DECISION`

**Sources:** requirements.md Requirement 10.5 and 20.7; task schema T7/T8; Wave 2.0.1 review finding 1.

A pair has a `pair_group_id` and a control/treatment group. Pair validation compares a canonical
projection, not raw JSON equality.

| Variation | Surface query | Canonical query | Expected result |
|---|---|---|---|
| `information_condition` | identical | identical | identical |
| `example_policy` | identical | identical | identical |
| `environment:surface_names` | may differ | must be identical after each profile translation | identical |
| `environment:operator_meaning` | identical surface tokens | may differ after translation, because the meaning changes | must differ for a discriminating pair |
| `environment:semantic_config` | identical surface tokens | identical if syntax/meaning mapping is unchanged | must differ for a discriminating pair |
| combined variations | changes permitted only for listed factors | validated according to each listed factor | validated according to the listed factors |

All non-varied hashed fields must be equal after removing environment-derived fields explicitly listed
in the comparison projection. Environment IDs, generated public examples, expected values and rendered
reference text are derived fields, not evidence of an unrelated difference. Any unrelated difference
rejects the pair.

Examples:

```text
valid surface pair:
  control query:   (add 2 3)
  treatment query: (prax 2 3)
  both canonicalize to: (add 2 3)
  expected values: equal

valid semantic pair:
  control query:   (and false (div 1 0))
  treatment query: (and false (div 1 0))
  canonical query: identical
  short-circuit result: false
  eager result: division_by_zero

invalid pair:
  surface_names is the only declared variation, but canonical queries differ

invalid pair:
  semantic_config is declared, but the prompt template version or difficulty dimensions differ
```

### D-002: Task-set identity - `DESIGN_DECISION`

**Sources:** requirements.md 16.4-16.5 and 20.1-20.3; task schema task-set record; review finding on
identity collision.

`task_set_id` hashes the complete experiment-defining projection:

```text
{
  "task_set_schema_version": 1,
  "family_version": "f1",
  "blueprint": { "id": "bp1", "version": 1, "slots": [...] },
  "environment_assignments": [
    { "environment_id": "env_...", "split": "dev" | "heldout" }
  ],
  "task_assignments": [
    { "environment_id": "env_...", "slot_index": 0, "task_id": "task_..." }
  ],
  "pair_groups": ["pair_..."],
  "task_ids": ["task_...", ...]
}
```

`task_assignments` is authoritative and binds every task to exactly one `(environment_id, slot_index)`.
The convenience `task_ids` list must equal its sorted task IDs. `pair_groups` are sorted and included
so pair membership changes create a new task-set identity. Duplicate task IDs, duplicate slot IDs,
gapped slots and duplicate environment-slot assignments are rejected. Changing a split, family version,
blueprint slot, explicit assignment, environment, pair group or task changes the ID. The old design
hashed only task IDs, a blueprint ID and a schema version, so it could identify reversed dev/held-out
assignments as the same set. This decision closes that collision.

### D-003: Environment identity - `PROPOSED_AMENDMENT`

**Sources:** requirements.md 5.2, 6.1, 16.4, 20.1-20.3; runtime finding F4; ADR-001.

Keep the legacy `LanguageSpec.language_id` as a compatibility cross-reference. Add a distinct
`environment_id` whose identity core is:

```text
{
  "env_schema_version": 1,
  "generator_family_version": "f1",
  "generator_algorithm_version": "1.0.0",
  "grammar_sha256": "...",
  "semantic_spec_sha256": "...",
  "surface_profile_sha256": "...",
  "runtime_semantics_version": 1
}
```

`semantic_spec_sha256` covers arithmetic, boolean mode, fixed evaluation metadata, all operation
signatures and semantic modes. The grammar hash covers canonical serialized grammar. The surface hash
covers the complete profile schema and mapping.

The generator and runtime versions are identity-bearing because changing the recipe or runtime changes
the meaning of a reproducibility record even if one generated artifact happens to remain byte-identical.
A separate `observable_fingerprint` may be used to detect byte-identical outputs across versions.

Seed, derivation path, timestamps, Python/Lark versions, host data and the legacy language ID are
provenance or descriptive metadata, not identity fields. Python/Lark are attested in the run manifest
and checked through a conformance digest.

**Required amendment:** Requirement 5.2 currently defines language identity only as a seed/version
hash. Amend it to distinguish `language_id` compatibility identity from Wave 2 `environment_id`:

> The Wave 2 benchmark SHALL identify an executable environment with a versioned hash of its canonical
grammar, semantic specification, surface profile, generator versions and runtime semantics version.
The legacy language ID MAY remain as a seed-derived compatibility identifier. Generated timestamps and
runtime host versions SHALL remain metadata only.

### D-004: P3 unit and undefined values - `DESIGN_DECISION`

**Sources:** requirements.md 10.2-10.4 and 20.8; scoring-contract.md.

The statistical unit is a **pair group**, not an individual sample, task or environment. A pair group
contains one control and one or more treatments. Each task may have `k >= 1` samples.

For task `t`:

```text
n_t = number of scored samples
p_t = number of successful scored samples
s_t = p_t / n_t, when n_t > 0; otherwise null
```

For a pair group `g`, the control score must be defined. Treatment scores are all defined treatment
task scores in the group. Their arithmetic mean is `s_trt_g`. If there are no defined treatments, the
group is ineligible. Then:

```text
loss_g   = max(0, s_ctrl_g - s_trt_g)
effect_g = s_ctrl_g - s_trt_g

L_v     = mean(loss_g) over eligible pair groups for variation v
Delta_v = mean(effect_g) over the same eligible groups
```

`L_v` is lower-is-better and is the ranked adaptation-loss diagnostic. `Delta_v` is an unranked signed
effect. If no eligible group exists, both are `null`, never zero. A control with all void samples is
reported separately from a scored control with zero passes. Multiple treatments receive equal weight at
the pair-group level, so one shared control cannot be counted once per treatment.

Resource-limit and infrastructure-void samples are not scored samples. Ordinary invalid answers,
syntax errors, semantic errors and wrong answers are scored failures with score zero. This keeps
inconclusive execution separate from model correctness.

### D-005: Pair-component bootstrap - `DESIGN_DECISION`

**Sources:** scoring-contract.md and requirements.md 10.5/20.9.

For each variation `v`, construct an undirected graph whose vertices are environment IDs. Add an edge
for every pair group that varies an environment factor. Pair groups that vary only information or
example policy are vertices in their containing environment component. Connected components are the
bootstrap units.

The deterministic algorithm is:

```text
units = sorted(component IDs)
require len(units) >= 2 for a confidence interval
for draw_index in 0 .. B-1:
    sample B_units IDs from units with replacement using
      H(task_set_id | metric | draw_index | position)
    expand every sampled component, preserving duplicate draws
    recompute the statistic from the expanded pair groups
    if no eligible pair group exists, mark the replicate invalid
require valid_replicates >= ceil(0.95 * B)
otherwise report interval = null and a bootstrap_failure diagnostic
sort valid statistic values
quantile(p) uses linear interpolation at h = (N - 1) * p
interval = [quantile(0.025), quantile(0.975)]
```

Duplicate components contribute duplicate pair groups. P3 model comparisons use the identical sampled
component IDs and positions for both models. Environment-level metrics use sorted environment IDs as
their units and do not use pair components. The default `B = 2000` is a design parameter, not a
scientific claim; it is recorded in the report.

### D-006: D8 step efficiency - `DESIGN_DECISION`

**Sources:** scoring-contract.md, runtime finding F5 and requirements.md 7.5/20.8.

D8 is measured per test using the production evaluator for both the candidate and the verified
reference solution. Translation and parsing happen before the step predicate and are not included in
`steps_used`. Wall-clock termination is never a successful predicate.

For each test, first verify that the candidate/reference pass with `max_steps = global_max_steps` and
that the observed result matches the expected result. If either fails, that threshold is `null` and the
task is excluded from D8. Otherwise binary-search the least nonnegative integer `m` in
`[0, global_max_steps]` for which the same test passes. The pass predicate is monotone because changing
only the step limit cannot change a deterministic program result.

Store the per-test vector:

```text
{
  "test_id": "t1",
  "submission_steps": 17,
  "reference_steps": 11
}
```

The task ratio is the median of `submission_steps / reference_steps` over tests with a positive
reference denominator. A zero submission threshold yields ratio zero. A zero reference threshold is
omitted from the ratio and counted in `zero_reference_tests`. If no test has a positive reference
threshold, the task ratio is `null`. The complete vector remains diagnostic. The report uses the median
of defined task ratios for D8 and records the number of eligible tests/tasks.

Binary search takes at most `ceil(log2(global_max_steps + 1))` predicate evaluations after confirming
the upper bound. A failed upper-bound check is not silently treated as inefficiency; it is
`d8_unavailable` with its cause.

### D-007: Global undefined-statistic policy - `DESIGN_DECISION`

Every metric has an eligible population. If its denominator is zero, its value is `null`, its display is
`n/a`, and the record stores the eligible numerator and denominator plus void counts. Zero is a measured
zero only when the denominator is positive.

### D-008: Runtime status and structured result contract - `PROPOSED_AMENDMENT`

**Sources:** requirements.md 7.6; runtime finding F5; current `src/execution/types.py`; design.md
legacy contract.

The proposed Wave 2 boundary status enum is:

```text
success
error
step_limit_exceeded
recursion_limit_exceeded
output_limit_exceeded
ast_depth_exceeded
invalid_program
```

Until the runtime is changed, the harness may map the current runtime's parse `error` plus
`error_kind=syntax` to boundary `invalid_program`, but this is a compatibility adapter, not runtime
compliance. The normative requirement must be amended or the runtime must be changed before claiming
compliance.

The additive runtime fields are `error_kind`, `error_detail`, `steps_used` and `ast_depth_reached`.
The old four-key `to_dict()` shape remains unchanged initially; a diagnostic serializer carries the
new fields. The reference evaluator does not claim production resource-step parity.

### D-009: Execution eligibility - `PROPOSED_AMENDMENT` / `BLOCKED`

Trusted local development and scientific pilot runs may use the watchdog design with an explicit
trusted-run label. Official security-compliant or untrusted execution requires Docker/WASM, no network,
a temporary filesystem, CPU and memory limits, and an image/runtime attestation. A watchdog subprocess
is not a sandbox.

### D-010: Providers and storage - `PROPOSED_AMENDMENT`

Mocks are first for zero-cost testing. Ollama is the first real provider because Requirement 3.5 names
it and it is local. An OpenAI-compatible adapter may follow as an optional transport. Files and a hash
chain are the Wave 2 source of truth; SQLite is a later derived index. Requirements 11.2 and 12.5 need
amendment if this order and storage choice are retained.

### D-011: Worked examples and task-set validation - `DESIGN_DECISION`

The earlier worked examples were not valid golden vectors:

- Task 2 exposed the same division error as its expected result in a public example, violating T9.
- The earlier Task 3 record said `pass_rule: all_hidden` while the normative test-suite rule requires
  all public and hidden tests to pass. The corrected golden vector now uses `all_tests`; its new task
  ID is recorded after regeneration.

The records were regenerated after correction; their old IDs were not preserved.

### D-012: Derived randomness encoding - `DESIGN_DECISION`

**Sources:** requirements.md 5.3, 16.4 and 20.3; reproducibility findings.

Hash-derived choices use a byte-level protocol, not an informal concatenation or Python process hash:

```text
input = b"unknownlang-derive-v1"
        || uint64_be(len(seed_utf8)) || seed_utf8
        || uint64_be(len(purpose_utf8)) || purpose_utf8
        || uint64_be(index)
digest = SHA256(input)
```

Additional digest bytes use a counter suffix and unbiased rejection sampling. The protocol is part of
the generator algorithm version and is covered by identity/reproducibility vectors.

### D-013: Run lifecycle and scientific status - `DESIGN_DECISION`

Run state, coverage and scientific status are separate fields. `complete` means every scheduled
attempt has a record, including void records. `official` is a scientific status requiring complete
coverage, approved sandbox class, matching conformance, zero prohibited voids and D10=0. `provisional`
means a complete but non-official run. `invalid` means integrity or unrecoverable harness failure.
Missing attempts keep coverage incomplete and allow resume while the run is running; existing attempt
records are immutable. This contract is authoritative in `experiment-model.md`, section 2.1.

### D-014: Three approval layers - `DESIGN_DECISION`

Owner decisions are separated into engineering scope approval, provisional research-protocol approval,
and post-pilot scientific-validity assessment. Approving the first two never establishes construct
validity, statistical power, difficulty calibration or a general-reasoning claim.

### D-015: Trust topology - `PROPOSED_AMENDMENT`

The model adapter and provider process are trusted components outside candidate execution. Candidate
programs run only inside the approved execution class. The adapter may access the local model endpoint
when explicitly configured, but candidate execution has no network access. Prompts, responses and
validated artifacts cross process boundaries as serialized data. Credentials are adapter-process
configuration and never enter task, attempt or identity records. Official/untrusted execution requires
Docker/WASM; watchdog-only execution is trusted-local and non-official.

### D-016: Research register and decision status - `DESIGN_DECISION`

Every research question has `question`, `required_evidence`, `method`, `decision_gate`, `owner` and
`current_status`. Status vocabulary is `proposed`, `owner_approved`, `implemented`, `verified`,
`deferred` or `blocked`. No design document may use `verified` for an unimplemented Wave 2 component,
and no owner approval may be inferred from a passing Wave 1 suite.


## Decision log

| ID | Consequence |
|---|---|
| D-001 | Pair validators compare canonical execution projections and reject unrelated differences |
| D-002 | Split/family/blueprint changes create new task-set IDs |
| D-003 | Environment identity includes generator and runtime versions; observable fingerprint remains separate |
| D-004 | P3 uses pair-group means over task sample rates and explicit nulls |
| D-005 | P3 bootstrap uses deterministic connected components and explicit invalid-replicate rules |
| D-006 | D8 stores per-test thresholds and defines task/report medians |
| D-007 | All undefined metrics are null/n/a, never zero |
| D-008 | Runtime status compliance remains blocked until the status amendment or runtime update is approved |
| D-009 | Security-compliant official runs remain blocked without Docker/WASM |
| D-010 | Ollama/mocks/files are the proposed zero-cost path; normative provider/storage requirements need amendment |
| D-011 | Worked examples are regenerated and old IDs are not preserved |
| D-012 | Derived randomness uses byte-framed SHA-256 and unbiased rejection sampling |
| D-013 | Run state, coverage and scientific status are independent lifecycle dimensions |
| D-014 | Engineering, provisional research, and post-pilot validity approvals are separate |
| D-015 | Trusted adapter/provider and untrusted candidate execution have separate trust boundaries |
| D-016 | Research questions have explicit evidence, gate, owner and status fields |
