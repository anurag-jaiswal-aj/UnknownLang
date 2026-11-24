# Wave 2.0.1 Architecture Review and Design Corrections

Status: **Review complete. Wave 2 implementation remains blocked pending approval.**
Baseline reviewed: Wave 2.0 at `4fcd400`, Wave 1C.16.1 at `642b2c8`.

This review is independent of the first Wave 2 review. It re-derives the corrected definitions,
checks edge cases, compares the proposal with the normative requirements and design documents, and
reports runtime recommendations. It does not implement any production code or silently amend a
requirement.

## 1. Repository state and scope

Pre-flight found:

- branch: `main`
- local `main`: `4fcd400b8fd5a26c6844e9d30a9a3fba274da94e`
- `origin/main`: the same commit
- remote: public `https://github.com/anurag-jaiswal-aj/UnknownLang.git`
- `fix/wave1c-correction`: preserved at `3f7a8c6`
- user change: `.kiro/specs/unknownlang/tasks.md`, unchanged
- authorized temporary file: `tmp/mutate_if_metadata.py`, verified untracked and deleted

No source or test file was changed. The review found design corrections are required before approval.

## 2. Executive verdict

**Wave 2.0.1: NEEDS CHANGES.**

The five corrections from the first review improved the documents, but they do not yet form a
complete executable specification:

| Finding | Verdict |
|---|---|
| T8 paired discrimination | **FAIL**: T8 distinguishes renaming from semantic pairs, but T7 still requires the same query program and does not permit different surface text that translates to the same canonical query |
| Pair-component bootstrap | **FAIL**: the resampling unit is named, but zero-eligible-pair replicates, weighting, minimum units and percentile method are undefined |
| P3 adaptation metric | **FAIL**: it is still restricted to `k = 1`, has undefined void and empty-pair cases, and the report example represents an undefined result as zero |
| D8 efficiency | **FAIL**: multi-test aggregation and the exact search predicate are undefined, and the stated ratio range excludes zero |
| Guessing and headline | **FAIL**: the small-integer control is useful but not a gate, and the unweighted headline deliberately replaces a required weighted score without an approval decision |

The documents also contain unresolved contradictions in identity format, execution statuses, sandboxing,
provider requirements, storage, oracle fallback, program categories and implementation status.

## 3. Review of the five corrected findings

### 3.1 T8 paired discrimination and surface renaming: FAIL

#### Original problem

The first version required every `environment:*` pair to have different expected answers. That made
`environment:surface_names` invalid, because renaming a language while preserving meaning should keep
the expected answer equal.

#### Current corrected definition

T8 now says:

- `environment:operator_meaning` and `environment:semantic_config` pairs must be discriminating;
- `environment:surface_names`, `information_condition` and `example_policy` pairs must have equal
  expected values.

That part is correct.

#### Independent reasoning and counterexample

T7 still says paired tasks differ only in the declared `varies` fields and share "the query program",
with an exception only when the environment changes the query's meaning. A surface-renaming pair
necessarily has different surface query text:

```text
control:   (add 2 3)
treatment: (prax 2 3)
```

Both may translate to the same canonical query `(add 2 3)`, but the stored query programs are not
equal. The current T7 exception is about changed meaning, not changed surface names. A valid surface
pair therefore fails T7 before T8 can approve it.

#### Required correction

Define a canonical-query equivalence relation in T7:

- unchanged query text for `information_condition` and `example_policy` pairs;
- equal translated canonical query for `environment:surface_names` pairs;
- equal canonical query after each environment's profile translation for operator-meaning and semantic
  configuration pairs;
- exact differences in every other hashed field must still match `varies`.

T8 should remain as corrected. Add a negative test where surface text differs and canonical text is
equal, and a negative test where surface text differs and canonical text is not equal.

**Conclusion: FAIL.**

### 3.2 Pair-component cluster bootstrap: FAIL

#### Original problem

The first version resampled individual environments even though environment-changing pairs span at
least two environments. A pair could be split by resampling.

#### Current corrected definition

The current document introduces connected pair components: environments are vertices, environment
pairs are edges, and a connected component is resampled as a unit. It says a component drawn twice
counts twice, while P1/P2/P4 use individual environments.

#### Independent reasoning and counterexamples

The component idea is sound, but the statistic is not yet defined for all bootstrap draws.

1. **Zero eligible pairs.** If the only component containing `operator_meaning` pairs is absent from a
   bootstrap draw, the P3 denominator is zero.
2. **One component.** Two environments in one component are not two independent resampling units. The
   current rule "fewer than 2 environments" is therefore insufficient. The relevant count is the
   number of eligible components for the requested variation.
3. **Duplicate weighting.** A component drawn twice must duplicate all its pair observations, or the
   statistic must be computed once per component. The document does not choose. Those choices differ
   when components have unequal pair counts.
4. **Multiple treatments.** The document says treatments are averaged within a pair, but does not
   define whether a bootstrap resample weights pair means equally, control groups equally or
   components equally.
5. **Percentiles.** "2.5th and 97.5th percentiles" lacks the finite-sample interpolation/index rule.
6. **Paired model comparisons.** One sentence says paired comparisons reuse resampled environments,
   while P3 requires the same component draws.

#### Required correction

Specify, separately for each metric:

- the resampling units;
- the statistic calculated from a duplicated unit;
- the eligible-unit count required before an interval is emitted;
- the rule for a replicate with no eligible pair;
- the deterministic percentile method, such as a named nearest-rank rule or a fixed linear
  interpolation rule;
- that model comparisons reuse the same component draw sequence for P3 and the same environment draw
  sequence for environment-level metrics.

A conservative rule is: omit a P3 interval when fewer than two eligible components exist; discard and
redraw bootstrap replicates with no eligible pairs using a deterministic counter stream; compute the
pair statistic from the concatenated duplicated pair rows; and require a fixed minimum number of valid
replicates. The design must state whether discarded draws consume counters.

**Conclusion: FAIL.**

### 3.3 P3 adaptation metric: FAIL

#### Original problem

The first version said a signed effect was "better closer to 0", which treated a model that failed
everything as equivalent to a model that was unaffected by a manipulation.

#### Current corrected definition

P3 now defines:

```text
L_v = pairs with control passed and treatment failed / pairs with control passed
Delta_v = mean(s_control - s_treatment)
```

It says `L_v` is lower, is undefined rather than zero when no control passed, and that `Delta_v` is
not ranked.

#### Independent reasoning and counterexamples

The direction and the no-control-passed rule are improvements, but the definition still has gaps.

1. It explicitly defines `L_v` only for `k = 1`, while the experiment model permits `k > 1`.
2. `s_t = p_t / n_t` is undefined when every sample is void. That possibility exists because adapter
   failures and harness faults are excluded from the scored denominator.
3. `Delta_v` is undefined when the pair set is empty. The report example contains a zero fraction for
   an effect even though the prose says undefined values are `n/a`.
4. Multiple treatments are described informally, but the P3 formula does not state whether the unit is
   each treatment, a control with an averaged treatment, or a pair component.
5. A control with all void samples is not equivalent to a control with scored failures. The report must
   preserve that difference.
6. If `k > 1`, rounding a task pass rate to 0 or 1 loses information and creates an arbitrary threshold.

#### Required correction

Choose one definition and apply it everywhere. The least surprising option is task-level scoring for
all `k`:

```text
s_t = p_t / n_t, if n_t > 0; otherwise undefined
L_v = mean over eligible pairs of max(0, s_control - s_treatment)
Delta_v = mean over the same eligible pairs of (s_control - s_treatment)
```

Alternatively, use sample-index matching, but then both members must have the same sample indices and
void behavior must be specified. In either case:

- no eligible pair produces `null`, never `{num: 0, den: 1}`;
- no scored control produces `null` for conditional loss;
- void-only controls are reported separately from scored failures;
- multiple treatments are averaged at a stated level;
- the report schema, formulas and bootstrap use the same unit.

The companion signed effect may remain diagnostic and unranked. `L_v` must be the only ranked
adaptation-loss metric if that is the intended claim.

**Conclusion: FAIL.**

### 3.4 D8 resource-efficiency definition: FAIL

#### Original problem

The first version described D8 both as a ratio and as a pair of integers.

#### Current corrected definition

D8 now stores `(steps_submission, steps_reference)`, derives a ratio at report time, omits the ratio
when the reference value is zero, and says bisection takes at most `ceil(log2(max_steps + 1))` runs.

#### Independent reasoning and counterexamples

The search bound is reasonable only under conditions the document does not state:

- the pass predicate must be monotonic in `max_steps`;
- the candidate and reference must pass at the global upper bound before searching;
- wall-clock termination must not be treated as a deterministic pass/fail predicate;
- parsing and translation costs must be excluded or included consistently;
- a task with multiple public and hidden tests needs one aggregate threshold or a per-test vector.

The current attempt record still has one singular `minimal_steps`, while the report has
`median_minimal_steps_ratio`. Neither says how 10-test tasks become one pair. A valid program with
`steps_submission = 0` and positive reference steps has ratio `0`, so the current range `(0, infinity)`
is wrong. If both values are zero, the ratio is undefined.

#### Required correction

Store per-test thresholds:

```text
threshold[test_id] = {
  submission_steps: nonnegative integer,
  reference_steps: nonnegative integer
}
```

Then define the task aggregate, for example the median ratio over tests with positive reference
thresholds, while retaining the complete vector for diagnostics. The ratio range is `[0, infinity)`
when defined, and `null` when the denominator is zero. Define the bisection precondition, monotonicity
assumption, wall-clock treatment, upper bound, and whether runtime steps include a failing step.

**Conclusion: FAIL.**

### 3.5 Guessing controls and headline deviation: FAIL

#### Original problem

The first version treated a declared answer-space chance floor as if it constrained a model's priors.
It also replaced the required difficulty-weighted score with an unweighted research headline.

#### Current corrected definition

The current document correctly says the declared floor does not bound a model that guesses small
integers, and adds a `smallint` synthetic agent. It still says a higher observed rate means the task
set needs revision without defining the gate or the broader prior suite. It also labels the
unweighted unseen-environment accuracy as the headline while Requirement 10.4 mandates a weighted
correctness score.

#### Independent reasoning and counterexamples

A task whose expected value is often 0 can be guessed effectively by a small-integer agent even if
its formal answer space is large. The current `smallint` agent only covers integers 0 through 10; it
does not test common boolean, error-class, familiar-name or constant priors. Synthetic-agent
signatures are not acceptance gates unless a threshold and pre-run procedure are defined.

The unweighted headline is a deliberate methodological choice, not an implementation detail. It is
incompatible with the normative weighted-score criterion until that requirement is amended or the
weighted score is promoted to a required report field.

#### Required correction

Before official runs:

- run a seeded prior suite covering small integers, booleans, common error classes, constant answers,
  familiar operator priors and public-example lookup;
- define whether thresholds apply per task, category, split or task set;
- reject or revise a task set when a declared effective guessing rate exceeds its approved threshold;
- report the required weighted score with positive difficulty weights, even if the unweighted score is
  the research headline;
- report the weighting rule and denominator validation.

**Conclusion: FAIL.**

## 4. Formula and edge-case audit

The documents claim to define every metric, but several denominators can be zero. The common rule
should be: an undefined statistic is `null`/`n/a`, never zero, and its eligible-count fields are
stored beside it.

| Metric | Edge case requiring a written rule |
|---|---|
| P1 category accuracy | no tasks, or all attempts void, gives denominator zero |
| P2 unseen accuracy | no held-out standalone tasks gives `\|C\| = 0` |
| P3 conditional loss/effect | no eligible pairs, void-only controls, `k > 1`, and zero-pair bootstrap draws |
| P4 transfer gap | no eligible dev or held-out accuracy |
| D1 syntax validity | no program reaches the denominator stage |
| D2 execution rate | no parseable program reaches execution completion |
| D3 resource rate | value tasks cannot exceed runtime resource limits; the denominator must be program attempts, not all scored attempts |
| D4 hidden fraction | no hidden tests or no executable program attempts |
| D5 public-hidden gap | either component fraction may be undefined |
| D6 stale-semantics rate | no wrong value answers |
| D8 step efficiency | zero reference steps, multi-test aggregation, failed search precondition |
| D9 response stability | value tasks have no canonical program hash; invalid/void responses and empty task sets need a rule |
| D11 coverage | zero scheduled attempts |
| D12 chance floor | no scored tasks with a declared floor; program tasks need a floor policy |
| environment accuracy | category denominators can be zero after void attempts |
| bootstrap intervals | minimum units, zero-denominator replicates and percentile interpolation are unspecified |
| weighted score | weights must be positive and the empty-input denominator must be rejected |

Ranges should be stated as:

- P1, P2, D1-D4, D6, D11 and D12: `[0, 1]` when defined;
- P4 and D5: `[-1, 1]` when defined;
- P3 conditional loss: `[0, 1]` when defined;
- P3 signed effect: `[-1, 1]`, diagnostic only;
- D8 ratio: `[0, infinity)` when the reference denominator is positive;
- D9: `[1/k, 1]` for a nonempty eligible task population with `k > 1`, not `(0, 1]` in the abstract.

## 5. SD1-SD10 decisions against the normative specification

The proposal does not silently approve any delta. The exact requirement, proposed change, consequence
and recommendation are recorded here.

| Delta | Normative requirement | Proposed change | Consequence | Recommendation |
|---|---|---|---|---|
| SD1 categories | Requirement 9.1: templates are array operations, string manipulation, recursion, sorting and search | Replace them with `SYN`, `EVAL`, `INF`, `CTRL`, `CONS`, `REC`, `ERR` because Wave 1 has only integers, booleans and first-order functions | The current runtime cannot implement most normative categories; the proposal measures a different benchmark | **Amend Requirement 9.1**, or extend the language before claiming compliance. Do not call this satisfied as written |
| SD2 first provider | Requirement 3.5 requires at least one provider, specifically Ollama, plus a mock. Requirement 11.2 says OpenAI-compatible APIs first | Use mocks first and defer local HTTP/Ollama to M2.11 | Wave 2 remains offline and zero-cost, but no real provider exists | **Amend requirements or implement an approved local Ollama adapter before official runs.** Do not add a paid API |
| SD3 sandbox | Requirements 15.1-15.4 and 20.10 require Docker/WASM isolation, no network and resource controls | Use a subprocess watchdog in Wave 2 and no process-level sandbox | This is not safe for untrusted submissions and does not meet the security requirement | **Block official/untrusted execution until sandboxed.** Trusted local design validation may proceed only if explicitly limited |
| SD4 storage | Requirement 12.5 requires SQLite for the MVP, while 12.1 says database implementation is deferred post-MVP | Use plain files and a hash chain as source of truth, with a future derived SQLite index | No database server or cost, but direct noncompliance with the SQLite criterion | **Amend Requirement 12** to make files authoritative and SQLite optional, or choose SQLite |
| SD5 resource status | Requirement 20.8 says over-limit submissions are distinct inconclusive, not failed/incorrect | Keep `resource_limit` distinct but score it 0 | This prevents expensive-program gaming but violates the explicit scoring language | **Do not approve silently.** Prefer exclude from correctness denominators, report separately, and require an approved coverage/resource cap for official runs; otherwise amend Requirement 20.8 |
| SD6 surface profiles | Requirement 5.6 names only arithmetic and short-circuit semantic dimensions; Requirement 4.4 claims entirely new programming languages | Add validated surface profiles and translation without changing the evaluator | Gives unfamiliar names and controlled syntax comparisons, but is not a new grammar or language family | **Approve only as a benchmark factor**, and amend the “entirely new programming languages” claim or add a future grammar family |
| SD7 weighted score | Requirement 10.4 mandates `sum(raw_i * difficulty_weight_i) / sum(difficulty_weight_i)` | Use unweighted category accuracy as the headline and weighted score only as sensitivity | Deliberately diverges from a normative metric | **Report the required weighted score as a first-class metric**, even if an unweighted research headline is retained, or amend Requirement 10.4 |
| SD8 examples/tests | Requirement 9.3 requires 3-5 public examples and 10-20 total tests; 9.4 requires hidden edge cases | Proposal permits 2-5 public and 5-15 hidden, and one-query value tasks | Some proposed program tasks have fewer than 10 total tests; answer tasks have no test-suite equivalent | **Enforce 3-5 and 10-20 for program challenges**, define a separate rule for value tasks, or amend Requirement 9.3 |
| SD9 status | Requirement 7.6 requires `invalid_program`; design.md also lists it | Classify parse failures as `syntax_error` inside a harness while runtime returns `error` | Multiple status contracts coexist and clients cannot rely on one | **Choose one contract.** Prefer adding/standardizing a structured `invalid_program` boundary status, or amend the requirement and old design together |
| SD10 extraction | Requirement 11.5 requires code from markdown blocks or the entire response | Accept the last fenced block for programs and `ANSWER:` lines for values | Safer and less ambiguous, but direct behavior change from the requirement | **Amend Requirement 11.5**, or support a clearly specified entire-response fallback with extraction diagnostics |

### Additional normative gaps not represented by SD1-SD10

- Requirement 3.1 requires a primary 50th-percentile hypothesis. The architecture has no hypothesis
  test, percentile comparison protocol or report field.
- Requirement 3.2 requires grammar rule count and token-diversity complexity and a degradation
  correlation. The architecture records difficulty dimensions but no grammar/token diversity metric.
- Requirement 3.3 requires at least 100 unique language variants per difficulty per execution. The
  audited runtime has six semantic fingerprints; surface profiles may expand names, but the proposal
  does not define the count or prove 100 variants per difficulty.
- Requirement 4.1 requires verifying that a generated language does not exist in public repositories
  or training data and recording a timestamp. The proposal correctly says leakage cannot be proved,
  but it does not define a compliant verification artifact.
- Requirement 6.5 requires collection and string limits although the MVP has no such types. The
  proposal calls them inapplicable; that is another explicit delta.
- Requirement 12.1-12.4 require database fields and run/result storage semantics that the file model
  must map explicitly if the requirement is retained.
- Requirements 13-19 specify API, frontend, deployment, demo and phase contents. Wave 2 defers them;
  the requirements need phase scoping rather than silent omission.

## 6. F1-F5 implementation-ready recommendations

### F1: definition-only program result mismatch

**Observed:** production returns `True` when the final top-level form is a definition; the reference
returns `None`. The production definition handler pushes a success result, while the reference ignores
definition values.

**Language-contract recommendation:** a definition is a declaration, not an expression value. A program
returns the value of its last evaluated expression, or `None` when it contains no expressions. This
matches the reference behavior and the benchmark's `definitions_only` submission plan.

**Smallest correction:** in production, stop pushing `True` as a definition result. Add differential
cases for:

- definition only;
- multiple definitions only;
- expression then definition;
- definition then expression;
- empty source;
- definitions used by a later expression.

Do not infer a new declaration visibility rule from this fix. The existing source-order/hoisting
behavior needs its own contract test. Bump `runtime_semantics_version` if the behavior changes, and
make old result sets non-comparable. Keep the reference evaluator independent; do not share a result
helper.

### F2: keyword-prefix parsing ambiguity

**Observed:** raw `(ifx 7 1)` can be read as `(if x 7 1)`, and similar `def` prefixes are ambiguous.

**Benchmark-path recommendation:** the surface translator can prevent this if and only if it is applied
to every model submission, hidden definition, test call and reference-generated surface program. Its
postcondition must be that output contains only canonical reserved words and `_u<N>` identifiers.

Required tests:

1. user function names `ifx`, `iffy`, `defg`, `deff`;
2. parameter names with keyword prefixes;
3. canonical familiar profiles and pseudo profiles;
4. hidden definitions and appended test calls;
5. transformed output containing no noncanonical identifiers;
6. translated program and canonical program agreeing in both evaluators.

**Conclusion:** the proposed benchmark path is conditionally safe. The raw runtime defect is not fixed,
and direct runtime callers remain exposed. Do not claim F2 is globally fixed.

### F3: Python compatibility

**Observed:** executing `canonical.py` fails with `NameError: Optional is not defined` on Python 3.11,
3.12 and 3.13; it imports on Python 3.14. The package declares `requires-python >=3.11`.

**Recommendation:** add `from typing import Optional` or postponed annotations, then run a CI matrix for
3.11-3.14 with a compatible Lark range. This is the smallest compatibility correction. Narrowing
`requires-python` is an acceptable fallback only if support for older versions is intentionally
withdrawn. Do not claim cross-version reproducibility before the matrix passes.

### F4: environment identity

The proposed environment identity is directionally correct but omits an explicit generator version from
the identity core. Add it.

#### Identity-bearing fields

```text
environment_schema_version
generator_family_version
generator_algorithm_version
canonical_grammar_sha256
semantic_spec_sha256
surface_profile_sha256
runtime_semantics_version
```

`semantic_spec_sha256` must cover the complete semantic object: arithmetic mode, boolean mode,
evaluation order, scoping, type coercion and every operation signature/mode. The grammar hash must be
of canonical serialized grammar. The surface hash must cover the complete profile schema and mapping.

```text
environment_id = "env_" + sha256(canonical_json(identity_core))
```

#### Descriptive but not identity-bearing fields

- original master seed and derivation index;
- seed name, features and difficulty when they are inert;
- Python and Lark versions;
- generated timestamp;
- provenance, host and storage path;
- the legacy `language_id` as a cross-reference.

If a seed field changes observable output, it must enter the identity through the resulting canonical
artifact or become an explicit identity field. Never rely on a manually supplied runtime version that
can disagree with the running code: the environment manager must import the runtime constant.

#### Collision and reproducibility tests

- Same identity core serialized with different dictionary insertion order gives the same ID.
- Different arithmetic mode, boolean mode, grammar, semantic operation mapping, surface profile,
generator version or runtime version gives a different ID.
- Same derived environment from two processes and different `PYTHONHASHSEED` values gives the same ID.
- Different derivation paths that produce byte-identical observable artifacts give the same ID.
- A changed conformance corpus digest without a runtime version bump fails validation.
- Full digests are stored; a short display prefix is never an identity.

This environment ID should coexist with the legacy `LanguageSpec.language_id` until a migration is
approved. The two must not both be called the authoritative language identity.

### F5: structured execution results

Add optional fields at the end of the existing frozen dataclass so existing positional construction
continues to work:

```python
@dataclass(frozen=True)
class ExecutionResult:
    status: str
    value: Any = None
    output: str = ""
    error_message: str = ""
    error_kind: str | None = None
    error_detail: str | None = None
    steps_used: int | None = None
    ast_depth_reached: int | None = None
```

Recommended `error_kind` values:

```text
syntax, name, arity, type, division_by_zero, overflow,
literal_range, resource, unknown
```

`error_detail` carries `identifier`, `function`, `arithmetic`, `boolean`, `not`, `if`, `steps`,
`call_depth`, `ast_depth`, `output`, or an implementation-independent detail. Raw messages remain
for compatibility and diagnostics but are not used for benchmark classification after migration.

Rules:

- `success`: `error_kind = null`; `steps_used` is the number of semantic expression steps charged,
  including a failing expression if one is charged before failure.
- `error`: `error_kind` identifies syntax, name, arity, type, arithmetic or literal range.
- resource statuses: `error_kind = resource`, with the specific `error_detail`.
- parse errors retain existing public status during compatibility, while the structured field says
  `syntax`; whether to expose `invalid_program` is an SD9 decision.
- `steps_used` and `ast_depth_reached` are production diagnostics. The reference evaluator does not
  claim resource-limit parity; cross-evaluator comparisons ignore these fields.
- Existing `to_dict()` behavior should be preserved initially, or versioned with a new diagnostic
  serializer, because callers may assert the current four-key dictionary shape.

This is additive and backward-compatible if the old status strings and four-key serialization remain.
It should be implemented only after SD9 and the runtime status contract are approved.

## 7. Remaining risks

- The surface translator becomes a shared failure point for production and reference checks.
- The runtime has no process-level sandbox and currently has parser/source-size exposure.
- The reference evaluator is not a production oracle for deep candidates or resource limits.
- The language family is small and public; procedural generation does not prevent family-level
  contamination.
- Difficulty, task count, power and sample-size choices are uncalibrated.
- The current runtime and design documents have incompatible execution status vocabularies.
- A fixed grammar plus token renaming may not justify the claim that the benchmark contains entirely
  new programming languages.

## 8. Decisions required before implementation

1. Fix T7 to compare canonical translated queries for surface-renaming pairs.
2. Complete the pair-component bootstrap algorithm and all P3 denominator rules.
3. Define D8 per-test and per-task aggregation, zero handling and monotonic search preconditions.
4. Add denominator/`null` rules for every metric and align the report schema.
5. Decide whether the required weighted score is first-class, and define approved guessing gates.
6. Decide SD1-SD10 explicitly, especially SD3, SD5, SD6, SD7, SD9 and SD10.
7. Resolve the old design status contract versus the current runtime status contract.
8. Approve the environment identity fields, including generator version and runtime version.
9. Approve or reject F1 and F3 before changing runtime or support declarations.
10. Approve the additive F5 result fields and serialization migration.
11. Decide how Requirements 3.1-3.5, 4.1, 4.4, 6.5 and 13-19 are scoped to Wave 2.

No Wave 2 production implementation should begin while these decisions remain open.

## 9. Wave 2.0.2 disposition

The five Wave 2.0.1 failures remain historically recorded above. Their closure contracts are now
specified in:

- [wave2-decisions.md](wave2-decisions.md), D-001 through D-012;
- [scoring-contract.md](scoring-contract.md), the authoritative metric and bootstrap definitions;
- [requirements-traceability.md](requirements-traceability.md), the requirement and amendment matrix.

Additional findings incorporated from the Wave 2.0.2 specialist review are:

- `task_set_id` must include split assignments, family version and complete blueprint content;
- the worked control-flow and recursive examples must be regenerated because they violate T9 and the
  all-tests contract;
- `serializer.py` has the same Python 3.11–3.13 annotation-import defect as `canonical.py`;
- the reference fallback outside its envelope is not sufficient to claim full independent-oracle
  compliance;
- the fixed grammar and surface layer cannot support an unqualified claim of entirely new language
  families;
- adapter import restrictions and an unsigned hash chain are trusted-runner controls, not security
  boundaries.

The architecture is more internally specified, but final approval remains blocked by the proposed
normative amendments, the Docker/WASM requirement for security-compliant official runs, and the
unimplemented runtime/provider prerequisites.
