# Wave 2 Scoring Contract

Status: **Proposed normative design for Wave 2.0.2. It is not implemented.**

This document is authoritative for metric definitions. It resolves the undefined cases found in
Wave 2.0.1. The existing evaluation document remains explanatory; where it conflicts with this file,
this file wins. No definition here silently changes requirements.md. Requirement deviations are listed
in the traceability document.

## 1. Common records and eligibility

An attempt has one of these outcome classes:

- `scored_success`: the expected value or every required test passed;
- `scored_failure`: a response was available but extraction, validation, syntax, name, arity, type,
  arithmetic, literal-range or expected-result comparison failed;
- `void`: adapter unavailable, harness fault, wall-clock termination, or resource-limit termination.

A void attempt is recorded but contributes neither a pass nor a scored failure to correctness ratios.
A resource-limit result remains a distinct `resource_limit` diagnostic. An official result with any void
attempt is provisional; the proposed official-run rule requires zero void attempts.

For task `t` with `k >= 1` samples:

```text
n_t = number of scored samples
p_t = number of scored_success samples
v_t = number of void samples
s_t = p_t / n_t, if n_t > 0; otherwise null
```

`n_t + v_t = k`. A scored failure has `n_t` contribution one and `p_t` contribution zero. An all-void
task has `s_t = null`, not zero. Every report stores `p_t`, `n_t`, `v_t`.

A metric is **undefined** when its eligible population or denominator is empty. The stored value is
`null`; rendered output is `n/a`. A zero is valid only with a positive denominator. Every metric stores
`eligible`, `numerator`, `denominator` and `void_count` where applicable.

All averages below are arithmetic means over their stated units. They are not silently weighted by
number of tests, samples or environments unless the formula says so. Stored ratios use integer pairs.

## 2. Primary metrics

### P1 Category accuracy

For category `c` and environment subset `E`:

```text
P1(c, E) = sum(p_t for t in eligible tasks in c,E)
           / sum(n_t for t in eligible tasks in c,E)
```

Eligibility requires `n_t > 0`. Range `[0, 1]`, higher is better. If the denominator is zero, `null`.
The report includes scored tasks, scored samples and void samples. The primary pooled score is not a
partial-test score.

### P2 Unseen-environment accuracy

For each category with a defined P1 on held-out environments, compute P1. Then:

```text
P2 = mean(P1(c, heldout) for categories with defined P1)
```

Range `[0, 1]`, higher is better. If no category has a defined P1, `null`. The report includes the
category count and per-category values. P2 is a proposed research headline, not a replacement for the
normative weighted score unless Requirement 10.4 is amended.

For an official complete result, the task-set blueprint must require at least one eligible task in
every required category and both dev/held-out splits. A missing category or split makes the run
`provisional` or `invalid` according to the run policy; it must never silently shrink the macro-average
population. Diagnostic P2 may still be computed over defined categories, with the omitted-category
count and reason recorded.

### P3 Conditional adaptation loss

A pair group contains one control task and one or more treatment tasks. For every task, use `s_t` from
section 1. A group is eligible only when the control score is defined and at least one treatment score
is defined. Let:

```text
s_ctrl_g = control task score
s_trt_g  = mean(scores of defined treatment tasks in group g)
loss_g   = max(0, s_ctrl_g - s_trt_g)
effect_g = s_ctrl_g - s_trt_g
```

For variation `v`:

```text
P3_loss(v)   = mean(loss_g over eligible groups for v)
P3_effect(v) = mean(effect_g over the same eligible groups)
```

`P3_loss` is range `[0, 1]`, lower is better. `P3_effect` is range `[-1, 1]` and is diagnostic only,
not ranked. A model that fails all controls does not obtain a false zero loss: the loss is `null` when
there are no eligible groups. A scored-but-failed control is different from a void-only control because
it has `s_ctrl = 0` and can be eligible if a treatment score exists.

For `k = 1`, this uses every eligible group whose control and at least one treatment score are
defined. It does **not** reduce to “control passed and treatment failed”: a scored-but-failed control
has `s_ctrl = 0`, remains eligible, and contributes zero downside loss when the treatment succeeds.
For `k > 1`, it uses sample pass rates and never rounds them to a binary value. If all treatment
samples are void, the group is ineligible. Multiple treatments are averaged within the group, so one
control contributes once.

The report stores: group count, eligible group count, control defined/passed counts, treatment defined
counts, void counts, `P3_loss`, `P3_effect`, and the variation signature.

### P4 Transfer gap

```text
P4 = P2(dev) - P2(heldout)
```

Range `[-1, 1]`, closer to zero is better as a gap diagnostic. If either side is undefined, `null`.
P4 is not itself a quality score; a model with low accuracy in both splits can have a small gap.

## 3. Diagnostic metrics

| Metric | Population and formula | Range/direction | Undefined behavior |
|---|---|---|---|
| D1 Syntax validity | program attempts reaching runtime parse; `non_syntax / runtime_parse_attempts` | `[0,1]`, higher | `null` if no program reaches runtime parse |
| D2 Execution rate | program attempts reaching comparison / attempts reaching runtime after no syntax error | `[0,1]`, higher | `null` if denominator zero |
| D3 Resource-limit rate | `resource_limit program attempts / program attempts reaching execution` | `[0,1]`, lower | `null` if no program attempt reaches execution; value tasks excluded |
| D4 Hidden-test pass fraction | hidden tests passed / hidden tests run, over program attempts with tests executed | `[0,1]`, higher | `null` if no hidden test ran |
| D5 Public-hidden gap | public pass fraction minus hidden pass fraction over the same attempt population | `[-1,1]`, closer to zero | `null` if either fraction undefined |
| D6 Stale-semantics rate | wrong value answers equal to control expected / wrong value answers in treatment tasks | `[0,1]`, lower | `null` if no wrong value answer exists |
| D7 Failure distribution | counts by failure category/detail, including void | nonnegative counts | always defined with zero counts |
| D8 Step efficiency | section 4 per-test thresholds and task/report aggregation | ratio `[0,infinity)`, lower | `null` if no eligible threshold or reference denominator |
| D9 Response stability | tasks with `k>1`; share matching the modal response/program hash, averaged over eligible tasks | `[1/k,1]`, higher | `null` if no eligible task; value tasks hash normalized answer, program tasks hash canonical submission |
| D10 Evaluation determinism | count of stored attempts whose deterministic replay differs | nonnegative integer, must be zero | always defined |
| D11 Coverage | scored or void attempt records / scheduled attempts | `[0,1]`, must be one for official runs | `null` if scheduled attempts is zero |
| D12 Mean chance floor | mean declared `chance_floor_ppm` over eligible value tasks with a floor | `[0,1000000]` ppm, context | `null` if no eligible value task has a floor |

For D4 and D5, public and hidden tests are counts of tests, not task samples. A test is run in declared
order and the attempt-level pass rule remains all required tests.

## 4. D8 algorithm

D8 uses the production evaluator for the candidate and the reference solution. The reference solution
is a verified program, not the recursive reference evaluator's resource accounting. The trusted harness
produces a validated `reference_cost_artifact` before scoring. It contains:

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

Scoring consumes this artifact and never reads private reference source code. The harness validates the
artifact's task ID, reference digest, runtime version, test IDs, expected results, step counts and
artifact hash. A disagreement or missing artifact makes D8 unavailable and the run provisional. The
reference evaluator is not used for candidate or D8 resource accounting.

For each test:

1. Translate the complete executed program.
2. Verify candidate and reference pass at `global_max_steps` with no wall-clock termination.
3. Define `passes(m)` as the deterministic result matching the expected result when only
   `max_steps = m` changes.
4. Binary-search the least `m` in `[0, global_max_steps]` for which `passes(m)` is true.
5. Store `submission_steps` and `reference_steps`.

The predicate is required to be monotone. If either upper-bound check fails, the threshold is null with
an explicit cause. Parsing and translation cost are not included in `steps_used`; wall-clock outcomes
never count as passing.

For each task, retain the full per-test vector. A valid test may have zero reference steps:

| submission steps | reference steps | ratio |
|---:|---:|---|
| 0 | 0 | null, counted in `zero_reference_tests` |
| positive | 0 | null, counted in `zero_reference_tests` |
| 0 | positive | 0 |
| positive | positive | submission/reference |

Zero-reference tests are valid evidence but cannot produce a finite ratio. They are retained in the
vector and reported, but excluded from ratio aggregation. A task is eligible only when at least one
valid test has a positive reference threshold. If all valid tests have zero reference steps, its ratio
is `null` with `undefined_reason: "no_positive_reference_steps"`. A failed upper-bound check is not a
zero-reference test; it is an unavailable threshold with an explicit cause.

Compute the task ratio as the median of `submission_steps / reference_steps` over tests with positive
reference steps. D8 is the median of defined task ratios over eligible passed program tasks. The report
stores test/task counts, zero-reference counts, unavailable counts and the reference threshold vector.
This is a conditional estimand: omitting zero-reference tests can bias comparisons if they cluster by
task type, so the report must expose the fraction and owners must not compare D8 without it.

Binary search takes at most `ceil(log2(global_max_steps + 1))` predicate evaluations after the upper
bound is established. With `global_max_steps = 100000`, this is 17. This count is a bound on search
runs, not a runtime-performance claim.

## 5. Pair-component bootstrap

### 5.1 Construction

For a metric tied to variation `v`, create a graph with environment IDs as vertices. Add an edge for
each pair group that varies an `environment:*` factor. Pair groups varying only information or example
policy belong to the environment's component. Connected components are sorted by their canonical ID.

P1, P2 and P4 use individual environment IDs as units. P3 uses pair components.

B is a mandatory report parameter. The Wave 2 default is `B = 2000`, and every interval record must
store `B`, `valid_replicates`, `invalid_replicates`, `minimum_valid_replicates`, the interval method and
bootstrap algorithm version. A draw count may not be selected implicitly or omitted from a report.

```text
units = sorted(eligible units)
if len(units) < 2: interval = null; reason = insufficient_units
for draw in 0..B-1:
    for position in 0..len(units)-1:
        digest = SHA256(task_set_id | metric_id | draw | position)
        choose an index using unbiased rejection sampling
    expand selected units, preserving duplicate positions
    recompute the metric from expanded rows
    if denominator is zero: invalid_replicate
require valid_replicates >= ceil(0.95 * B)
if not: interval = null; reason = insufficient_valid_replicates
sort valid values
quantile(p) = linear interpolation at (N-1)*p
return [quantile(.025), quantile(.975)]
```

The bootstrap stream uses this exact encoding for every selection position:

```text
fields = [task_set_id, metric_id, draw_index, position]
bytes  = UTF-8(json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
digest = SHA256(bytes)
```

Rejection retries append `rejection_index` as a fifth JSON array field. Strings are UTF-8; integer
values are JSON decimal integers; no platform-native binary encoding or delimiter concatenation is
allowed. The digest is interpreted as a big-endian unsigned 256-bit integer. For `m = len(units)`:

```text
limit = floor(2^256 / m) * m
while x >= limit:
    rejection_index += 1
    hash the five-field array
selected_index = x mod m
```

The first rejection index is zero. `draw_index` ranges from zero through `B-1`; `position` ranges from
zero through `len(units)-1`. Duplicate units duplicate their observations. Paired model comparisons use
the same draw, position and rejection sequence.

### 5.3 Worked example

Suppose three pair components contain eligible pair-group losses:

```text
C1: [0.0, 1.0]
C2: [0.5]
C3: [0.0, 0.0, 1.0]
```

The observed group-weighted loss is `5/12`. A bootstrap draw `[C1, C1, C3]` expands to
`[0,1,0,1,0,0,1]`, giving `3/7`. A draw `[C2,C2,C2]` gives `0.5`. A draw containing only components
with no eligible groups is invalid, not zero. With fewer than two eligible components, no interval is
reported.

## 6. Required report fields

Every metric record includes:

```json
{
  "value": {"num": 3, "den": 7},
  "eligible": 7,
  "numerator": 3,
  "denominator": 7,
  "void_count": 0,
  "undefined_reason": null
}
```

For an undefined statistic:

```json
{
  "value": null,
  "eligible": 0,
  "numerator": 0,
  "denominator": 0,
  "void_count": 4,
  "undefined_reason": "no_eligible_pair_groups"
}
```

## 7. Required weighted score

Requirement 10.4 requires a normalized difficulty-weighted correctness score. The report must include
it separately from the proposed unweighted held-out research headline:

```text
W = sum(raw_task_score_t * difficulty_weight_t)
    / sum(difficulty_weight_t)
```

Weights must be positive integers, and the weight function and version must be recorded in the
 task-set blueprint. The default proposal is `difficulty_weight_t = 1` until pilot data justifies
another function; this still reports the required formula rather than replacing it.

Only tasks with `n_t > 0` are eligible. Void samples do not contribute to either the numerator or task
weight. A task with both scored and void samples contributes its scored pass rate and retains its full
difficulty weight. An all-void task contributes no weight and is reported in `void_task_count`.

If any task is void, the run is provisional. An official complete run requires no void attempts and
complete category/split coverage. A provisional run may display W for diagnostics, but it cannot be
ranked beside an official run. If no task has a defined score, W is `null` with
`undefined_reason: "no_scored_weighted_tasks"`. Missing attempts are not silently treated as zero and
are recorded as `missing_attempt_count`.
## 7.1 Composite chance floors

A declared `chance_floor_ppm` is a probability for a complete task answer under a named baseline
guessing policy. It is not automatically the product of marginal query floors.

The product rule is valid only when all of the following are declared and justified:

- component answers are independently sampled;
- the baseline distribution is uniform or otherwise explicitly specified;
- task correctness requires all component answers;
- no shared prompt, correlated prior or deterministic answer strategy changes the joint distribution.

If independence is not justified, the task must use an empirically measured seeded baseline or an
explicit conservative upper bound for the joint answer space. The report stores the baseline policy,
its version, the joint distribution method, component floors and the complete-task floor. A marginal
floor must never be advertised as a guarantee against correlated guessing.

## 7.2 Official weighted-score and chance-floor requirements

An official task set must define positive weights, a versioned weight function, and a complete-task
chance-floor policy. A composite task with uncertain joint probability is provisional until its floor
is measured or conservatively bounded.

## 8. Official eligibility

A run is `complete` only when every scheduled attempt has a record. A run is `official` only when:

- coverage is one;
- no harness fault, adapter void or wall-clock event exists;
- no resource-limit event exists unless an approved amendment defines a nonzero cap;
- the conformance digest matches;
- D10 is zero;
- the task-set and prompt comparability keys match the experiment design;
- the execution environment satisfies the approved sandbox class.

These are integrity and eligibility gates, not hidden scoring rules.
