# Evaluation and Scoring (Wave 2.0)

Status: **Proposed. Pending review and approval. Nothing here is implemented.**
Baseline: Wave 1C.16.1, commit `642b2c8`.

**Wave 2.0.2 authority:** [scoring-contract.md](scoring-contract.md) is now the normative source for
P1-P4, D1-D12, undefined values, pair-component bootstrap, resource-limit eligibility and D8. This
document explains the rationale and anti-gaming design. If an older formula here differs from the
scoring contract, the scoring contract wins.
Names of identifiers, categories, protocols and error classes are defined in the
[task schema](benchmark-task-schema.md) and are not redefined here.

## 1. Principles

1. **An invalid submission can never score.** Every stage failure scores 0. Nothing is silently
   dropped, retried in the model's favor or excluded from a denominator.
2. **Primary scores need no invented weights.** The primary score is binary per task, averaged with
   equal weights. Anything that needs a weight is a diagnostic.
3. **Every comparison is controlled.** A claim such as "the model is sensitive to renaming" is a
   paired difference on matched tasks, not a comparison of two unrelated accuracy numbers.
4. **Evidence is labelled.** Each metric says whether it comes from the specification, or is a design
   hypothesis that must be validated (section 10). No real-model result exists yet and none is
   claimed.
5. **Infrastructure failures are not model failures.** They are kept apart from model failures, are
   counted, and make a run incomplete rather than quietly lowering a score.

## 2. The attempt pipeline

One attempt is one `(model, task, sample index)`. It runs through fixed stages and stops at the
first stage that fails. The stage determines the failure category (section 3).

| Stage | Owner | Input | Output | Fails with |
|---|---|---|---|---|
| S0 Prompt | `PromptBuilder` | public view of the task, environment | prompt text and hash | `harness_fault` |
| S1 Generate | model adapter | prompt text | raw response text | `adapter_unavailable`, `no_response` |
| S2 Extract | harness | raw response | `ANSWER:` value, or the last fenced block | `extraction_failed` |
| S3 Validate | harness | extracted text | accepted submission | `invalid_answer`, `invalid_submission` |
| S4 Translate | harness | submission | canonical program text | `invalid_submission` (tokenization) |
| S5 Execute | production runtime | canonical program, limits | `ExecutionResult` | the runtime classes, section 3.2 |
| S6 Compare | harness | result, `expected` | pass or fail | `wrong_answer` |

Only S5 runs UnknownLang. No stage runs Python `eval` or `exec` on any model output, and no model
output reaches the host language: S2 to S4 treat the text as data and the runtime interprets it.
This is not process level isolation; see the [overview](wave2-overview.md), section 8.

For `value` tasks S5 does not run the answer. The answer is a **prediction** compared with
`expected`. S5 runs only for `program` tasks.

## 3. Failure taxonomy

### 3.1 Categories

`failure_category` is one of the values below. `detail` refines it. `ok` means the attempt passed.

| `failure_category` | Stage | Scored | `detail` values | Meaning |
|---|---|---|---|---|
| `ok` | S6 | 1 | | all checks passed |
| `adapter_unavailable` | S1 | void | `unreachable`, `timeout`, `adapter_error` | the model could not be reached. Infrastructure, not model behavior |
| `harness_fault` | any | void | `exception`, `unclassified_result`, `replay_mismatch` | an invariant of the harness failed. Always counted and reported |
| `no_response` | S1 | 0 | `empty`, `refusal` | the model answered but produced no usable text |
| `extraction_failed` | S2 | 0 | `no_answer_line`, `no_code_block` | no answer in the required form |
| `invalid_answer` | S3 | 0 | `unparseable`, `kind_not_allowed`, `bad_error_class` | the `ANSWER:` text is not a valid value |
| `invalid_submission` | S3, S4 | 0 | `oversize`, `empty`, `tokenization`, `bad_form`, `missing_definition`, `reserved_name`, `duplicate_parameter` | the program breaks a documented form rule |
| `syntax_error` | S5 | 0 | | does not parse |
| `name_error` | S5 | 0 | `identifier`, `function` | unknown identifier or function |
| `arity_error` | S5 | 0 | `user`, `builtin` | wrong argument count |
| `type_error` | S5 | 0 | `arithmetic`, `boolean`, `not`, `if` | a value of the wrong type reached an operation |
| `arithmetic_error` | S5 | 0 | `division_by_zero`, `overflow` | |
| `literal_range_error` | S5 | 0 | | an integer literal outside the signed 64-bit range |
| `resource_limit` | S5 | void | `steps`, `ast_depth`, `call_depth`, `output`, `wall_clock` | a limit was exceeded; retained diagnostically and makes the run provisional |
| `wrong_answer` | S6 | 0 | `wrong_value`, `wrong_kind`, `wrong_error_class`, `failed_tests` | the answer or the program's behavior differs from `expected` |

For a `test_suite` task the attempt category is the category of the **first failing test in declared
order**, and the number of failing tests is recorded in the diagnostics.

`void` attempts are not scored but are never dropped: the run records them, reports the coverage
(section 6.5) and is marked incomplete. A run may rerun void attempts by their attempt key. A
`wall_clock` event is deterministic only if the limit is exceeded on every machine, so any run that
contains one is flagged as non-reproducible and official runs must contain none (section 9).

### 3.2 Mapping runtime results to error classes

The runtime returns a status string and a free text message. The two do not separate parse errors
from runtime errors (parse errors have status `error`), so classification uses message families.
The table was captured from the Wave 1C.16.1 runtime. Each row was produced by executing a program
on the real runtime, and the reference evaluator returned the same message in every non-resource
case.

| Observed message (prefix or pattern) | Error class | Category and detail |
|---|---|---|
| status `step_limit_exceeded` | `resource` | `resource_limit` / `steps` |
| status `recursion_limit_exceeded` | `resource` | `resource_limit` / `call_depth` |
| status `ast_depth_exceeded` | `resource` | `resource_limit` / `ast_depth` |
| status `output_limit_exceeded` | `resource` | `resource_limit` / `output` |
| `Runtime error: Unexpected` (end of input) | `syntax` | `syntax_error` |
| `Runtime error: No terminal matches` | `syntax` | `syntax_error` |
| `Unknown identifier: <name>` | `name` | `name_error` / `identifier` |
| `Unknown function: <name>` | `name` | `name_error` / `function` |
| `Function '<name>' expected <n> arguments, got <m>` | `arity` | `arity_error` / `user` |
| `... requires <n> arguments, got <m>` and `... requires 1 argument, got <m>` (built-ins) | `arity` | `arity_error` / `builtin` |
| `Arithmetic operation '<op>' requires int arguments, got <type>` | `type` | `type_error` / `arithmetic` |
| `Boolean operation requires boolean arguments, got <type>` | `type` | `type_error` / `boolean` |
| `not requires boolean argument, got <type>` | `type` | `type_error` / `not` |
| `if condition must be boolean, got <type>` | `type` | `type_error` / `if` |
| `Runtime error: Division by zero`, `Runtime error: Modulo by zero` | `division_by_zero` | `arithmetic_error` / `division_by_zero` |
| `Runtime error: Integer overflow: ...` | `overflow` | `arithmetic_error` / `overflow` |
| `Integer literal out of range: ...` | `literal_range` | `literal_range_error` |

Rules:

* The arity rows are tested before the type rows. `Arithmetic operation 'add' requires 2 arguments,
  got 1` is an arity error even though it begins like the type message.
* **Anything not in the table is a `harness_fault` with detail `unclassified_result`.** An unknown
  message must stop a run loudly. It must not be guessed into a class. The conformance corpus
  ([schema](benchmark-task-schema.md), section 11.3) has to contain every row, and adding a message
  to the runtime without adding a row fails the test suite.
* The raw message is never shown to the model. The harness shows the error **class** and, where
  needed, a name restored from the translator's `name_map`. This is required because raw messages
  contain canonical names and implementation text (the overflow message contains `<lambda>` for
  `add`, `sub` and `mul`).
* Classifying by text is a workaround for a missing field. A structured `error_kind` on
  `ExecutionResult` is proposed as an additive runtime change
  ([runtime findings](runtime-findings.md), F5) and needs approval.

## 4. Per-attempt score

```
s(attempt) = 1   if failure_category = ok
s(attempt) = 0   for every scored category other than ok
void         for adapter_unavailable and harness_fault   (excluded from scoring, counted, run incomplete)
```

* `value` tasks: `ok` iff the extracted value equals `expected` exactly, with type exact equality.
* `program` tasks: `ok` iff every test passes, every public and hidden test.

For `k` samples per task, the task keeps the integer pair `(p_t, n_t)` of passes and scored
samples. Ratios are computed only when a report is rendered, from integers, using exact rational
arithmetic and a fixed rounding for display (round half to even, four decimals). Stored records
contain no floats.

A response that passes only some tests scores 0. This is a deliberate choice (section 5.2).

## 5. Metrics

Notation: `T_c` is the set of tasks in category `c`. `p_t` and `n_t` are passes and scored samples of
task `t`. `E` is a set of environments.

### 5.1 How to read the tables

Each metric states: what it measures, its formula, its range, which direction is better, how it can be
gamed, and its evidence status. Evidence status is one of: **Spec** (required by requirements.md),
**Design** (follows from the design and is checkable by construction), or **Hypothesis** (expected
to behave as described, validated only against synthetic agents in section 10, with no real model
evidence yet).

### 5.2 Primary metrics

| Metric | Measures | Formula | Range | Better | How it can be gamed | Evidence |
|---|---|---|---|---|---|---|
| **P1 Category accuracy** `A_c(m, E)` | Whether the model solves tasks of one capability | `sum_{e in E} sum_{t in T_c,e} p_t / sum n_t` | [0, 1] | higher | Answering from priors on tasks whose answer is easy to guess: controlled by chance floors (T10) and non-trivial answers (T9). Hard-coding public examples: hidden tests are disjoint (T6) | Spec (requirements.md, Requirement 10, criterion 2) |
| **P2 Unseen-environment accuracy** `U(m)` (the headline) | Mean performance on held-out environments | Mean of defined category accuracies on held-out standalone tasks, as defined in scoring-contract.md | [0, 1] or null | higher | Learning the generator family (section 8.2, risk R4) | Design. The required weighted score W is reported separately; replacing it requires SD7 approval |
| **P3 Conditional loss** `L_v(m)` with diagnostic signed effect `Delta_v(m)` | Cost of one manipulation among eligible control/treatment pair groups | Pair-group means over task pass rates; exact formula and k/void/multiple-treatment rules are in scoring-contract.md | `L_v` [0,1]; `Delta_v` [-1,1]; null when no eligible group | `L_v` lower; `Delta_v` unranked | Prior-semantics agents should lose on treatment pairs; all-void controls remain undefined, not zero | Hypothesis |
| **P4 Transfer gap** `G_T(m)` | The difference between environments that were used in development and sealed ones | `U_dev(m) - U_heldout(m)` | [-1, 1] | closer to 0 | Tuning prompts on dev environments inflates `U_dev`. The sealed split is the control. Environment difficulty can differ by chance, so the control agent in section 10 is reported next to it | Hypothesis |

The P3 family, one row per variation signature `v` (the `varies` list of the pair):

| `v` | Reading |
|---|---|
| `environment:surface_names` | Sensitivity to renaming with meaning unchanged. Isolates dependence on familiar names |
| `environment:operator_meaning` | Cost of changing what the same names mean. In a `familiar` profile this exposes reliance on prior knowledge |
| `environment:semantic_config` | Cost of a changed arithmetic or boolean mode, with the documentation of the new environment provided |
| `environment:semantic_config` + `information_condition` (`DELTA_DOC`) | Adaptation when the change is stated explicitly |
| `environment:semantic_config` + `information_condition` (`STALE_DOC_EXAMPLES`) | Adaptation when the change must be inferred from examples that contradict the documentation |
| `information_condition` (`FULL_DOC` against `EXAMPLES_ONLY`) | Dependence on documentation as against inference from examples |
| `example_policy` | Sensitivity to misleading but truthful examples |

Why the primary score is binary and not partial credit: a program that passes 7 of 10 tests may be a
correct idea with one slip or a table lookup of the public examples. A partial score cannot tell
these apart and rewards the second. Partial results are a diagnostic (D4), and the gap between public
and hidden pass rates (D5) is the overfitting signal.

Resource-limit outcomes are distinct `void` results, not correctness failures. They are excluded from
correctness numerators and denominators, retained as diagnostics, and make a run provisional. This
follows Requirement 20, criterion 8 and requires the owner decision recorded as SD5/AM-06. An official
run must satisfy the approved resource-limit policy; no resource outcome is silently converted to zero.

### 5.3 Diagnostic metrics

Diagnostics explain primary scores. They are never combined into a headline number.

| Metric | Measures | Formula | Range | Better | How it can be gamed | Evidence |
|---|---|---|---|---|---|---|
| **D1 Syntax validity** | Whether submissions parse | `(program attempts that reached S5 and did not fail with syntax_error) / (program attempts that reached S5)`. Syntax errors are found when the runtime parses, which is inside S5 | [0, 1] | higher | A trivial program such as `1` always parses. Meaningful only next to P1 | Design |
| **D2 Execution rate** | Whether valid programs run without a runtime error | `(attempts reaching S6) / (attempts reaching S5 without syntax_error)` | [0, 1] | higher | Same as D1 | Design |
| **D3 Resource-limit rate** | Programs that exceed a limit | `resource_limit program attempts / program attempts reaching execution` | [0, 1] or null | lower | None. Value tasks are excluded | Design / SD5 |
| **D4 Hidden-test pass fraction** | Partial correctness of `program` tasks | `sum hidden tests passed / sum hidden tests`, over attempts that reached S5 | [0, 1] | higher | Special-casing the public examples. Disjoint hidden tests expose this | Design |
| **D5 Test generalization gap** | Overfitting to the shown examples | `public pass fraction - hidden pass fraction`, same population as D4 | [-1, 1] | closer to 0 | A model that passes neither has gap 0, so read it with D4 | Spec (Requirement 10, criterion 3) |
| **D6 Stale-semantics rate** | Whether wrong answers match what the earlier or familiar semantics would give | `(wrong value answers equal to the control task's expected) / (wrong value answers)` over treatment tasks | [0, 1] | lower | Defined only on `value` tasks. A model that guesses randomly has a low rate and a low P1 | Hypothesis |
| **D7 Failure distribution** | Where attempts fail | counts by `failure_category` and `detail` | counts | n/a | None | Design |
| **D8 Step efficiency** | Cost of correct solutions | Per-test thresholds and median task/report aggregation, with zero-reference and failed-upper-bound rules, as defined in scoring-contract.md | [0, infinity) or null | lower, over eligible passed program tasks | Requires production reference-solution runs and step diagnostics; wall-clock is not a pass predicate | Design / F5 |
| **D9 Response stability** | Agreement across `k > 1` samples | Modal normalized answer hash for value tasks or canonical-program hash for program tasks, averaged over eligible tasks | `[1/k, 1]` or null | higher | A consistently wrong model can still be stable; read with correctness | Design |
| **D10 Evaluation determinism** | Whether the harness is deterministic | number of stored attempts whose deterministic re-evaluation differs from the record | integer | must be 0 | An invariant. A nonzero count invalidates the run | Spec (Requirement 20, criterion 1) |
| **D11 Coverage** | Completeness | `scored attempts / scheduled attempts` | [0, 1] | must be 1 for comparisons | None | Design |
| **D12 Mean chance floor** | Context for accuracy | mean of `chance_floor_ppm` over scored tasks | [0, 1000000] ppm | context | None | Design |

### 5.4 Weights and difficulty

requirements.md, Requirement 10, criterion 4 defines `weighted_score = sum(raw_i x w_i) / sum(w_i)`. The
design computes it with the default `w_i = 1`, which equals P1 pooled over all tasks. A difficulty
weight such as `w_i = level` can be computed as a **sensitivity row**, always shown next to the
unweighted number and never used as the headline. Any weight is arbitrary until it can be
justified from data, and no such data exists. If a ranking of models changes between the two, the
report flags it.

## 6. Aggregation

### 6.1 The four levels

| Level | Unit | Defined as | Used for |
|---|---|---|---|
| Task | one task, `k` samples | the integer pair `(p_t, n_t)` and per-sample failure categories | diagnostics and pairing |
| Environment | one environment `e` | `A_e(m) = mean over categories c present in e of (sum_{t in T_c,e} p_t / sum n_t)` | per-environment reporting, bootstrap clusters |
| Model | one model on one task set | P1 to P4, D1 to D12 | model results |
| Aggregate | several models on one task set | the table of model results, with intervals, plus paired differences between models | comparison |

Macro averaging over categories (equal weight per category) is the headline; the micro average (equal
weight per task) is reported next to it. Because every environment is built from the same blueprint
(schema, section 9) the two differ only by the blueprint's slot counts, which are known and
published.

### 6.2 Pairing

Pair membership and canonical-query equivalence are defined by D-001 and T7/T8 in the task schema. A
pair-group score uses task scores `s_t`; multiple treatments are averaged within the group so one
control contributes once. Undefined task scores exclude the group. P3 is therefore computed by the
contract in [scoring-contract.md](scoring-contract.md), not by raw sample or environment counts.

### 6.3 Uncertainty

The complete deterministic bootstrap algorithm, component construction, duplicate handling, minimum
units, invalid replicates and percentile rule are in [scoring-contract.md](scoring-contract.md).
Environment-level metrics use environment units. P3 uses connected pair components. Paired model
comparisons reuse the exact same unit draws. Undefined bootstrap results are `null`, never zero.

### 6.4 Comparability

Two results are comparable only if `task_set_id`, `prompt.template` version,
`runtime_semantics_version` and `family_version` are equal. The reporting layer refuses to place
results that differ in these values into one table.

### 6.5 Incomplete runs

If any attempt is `void`, coverage D11 is below 1. The report shows the number of void attempts by
category and marks all derived numbers as provisional. A provisional result is never ranked
against complete ones.

## 7. Distinguishing capabilities: the controlled experiments

A benchmark that only checks whether a model can evaluate small Lisp expressions cannot separate
familiarity from understanding. The environment factors are varied one at a time on matched tasks.

### 7.1 Factor design

| Factor | Levels | Realized by |
|---|---|---|
| Names | `familiar`, `pseudo` | surface profile kind |
| Meaning | identity assignment, permuted assignment (within a type class) | surface profile mapping |
| Semantic configuration | arithmetic mode (3) and boolean mode (2): 6 combinations | environment semantics |
| Information | `FULL_DOC`, `SIGNATURES_ONLY`, `EXAMPLES_ONLY`, `DELTA_DOC`, `STALE_DOC_EXAMPLES` | task field |
| Example policy | `neutral`, `misleading` | task field |

### 7.2 Controlled comparisons

| Comparison | Pair `varies` | What it isolates | What a difference does and does not show |
|---|---|---|---|
| Same syntax, different semantics | `environment:semantic_config` or `environment:operator_meaning`, names fixed | Dependence on stated or inferred meaning as opposed to a default | A large cost is consistent with reliance on a default meaning. It does not show why the default was chosen |
| Different syntax, same semantics | `environment:surface_names` | Dependence on familiar surface forms | A large cost is consistent with surface memorization. It could also be a tokenizer effect (R9) |
| Different syntax and semantics | both of the above, listed together | The combined cost. With a full 2 x 2 group of four tasks the interaction `(d_both - d_names - d_meaning)` can be computed | Interaction needs a four-cell group, not a pair. Deferred to M2.9 |
| Familiar against unseen operators | `environment:surface_names` between a `familiar` and a `pseudo` profile with the same meaning | Benefit of familiar names when the meaning really is familiar | |
| Familiar names with a misleading meaning | `environment:operator_meaning` inside a `familiar` profile, for example `add` means `sub` | Whether a model follows the documentation or the name | A high cost with a high D6 means wrong answers match the familiar meaning |
| Training examples against held-out tasks | `heldout` against `dev` environments (P4), and public against hidden tests (D5) | Generalization beyond what was seen while developing, and beyond the shown examples | Tests transfer within this language family only |
| Repeated against novel environments | the same dev/heldout split. Attempts are stateless, so "repeated" means "seen during development", not "seen earlier in a conversation" | Memorization of specific environments | |
| Reasoning under changed semantics | `environment:semantic_config`, with `DELTA_DOC` and `STALE_DOC_EXAMPLES` treatments | Adaptation to a change that is announced as against one that must be inferred | |
| Documentation against inference | `information_condition` | Whether success needs written rules or can come from examples | |
| Sensitivity to misleading examples | `example_policy` | Whether a plausible wrong hypothesis is adopted | Examples are always truthful |

### 7.3 Signatures a researcher can look for

These are patterns **consistent with** a hypothesis. None proves it.

| Hypothesis | Pattern | Alternative explanations to rule out |
|---|---|---|
| The model relies on knowledge of familiar names | high `A` in `familiar` profiles with identity meaning; large `Delta` for `environment:operator_meaning` in `familiar` profiles; high D6 | the model follows the prompt less carefully for long documents |
| The model memorizes surface forms | large `Delta` for `environment:surface_names`, no change in meaning | tokenizer effects (R9) |
| The model infers semantics from evidence | `A` on `INF` tasks under `SIGNATURES_ONLY` and `EXAMPLES_ONLY` close to `FULL_DOC`; small `Delta` for `information_condition` | examples that happen to fix the answer by pattern. Gate T13 and an unseen query control this |
| The model adapts to changed semantics | small `Delta` for `STALE_DOC_EXAMPLES`; positive benefit of `DELTA_DOC` over `STALE_DOC_EXAMPLES` | the changed semantics were simply easier. Compare against the same tasks with `FULL_DOC` in the changed environment |
| The model transfers | `G_T` near 0, with a control agent gap near 0 | dev and held-out environment difficulty differing by chance |

### 7.4 What this does not claim

The benchmark measures behavior inside **one small language family**: ten operations over integers
and booleans, first-order functions, six semantic configurations, and surface re-skinning. It does
not measure general intelligence, general reasoning, or ability to learn arbitrary new languages. It
shows how a model behaves under specific, controlled manipulations of that family. Whether a result
generalizes beyond the family is an open question ([overview](wave2-overview.md), section 12, R1 and R4) and would need new
families, not more environments from this one.

## 8. Anti-gaming and anti-leakage

### 8.1 Against gaming the score

| Threat | Control |
|---|---|
| An invalid submission earning credit | Every stage failure scores 0 and is never excluded (section 1) |
| Writing an expensive program to avoid a wrong answer | `resource_limit` is void, counted in coverage/resource diagnostics, and an official-run policy blocks incomplete or excessive-resource runs |
| Hedging with several answers | Only the last `ANSWER:` line or the last code block counts (schema 7.1) |
| Copying a public example | Answer not equal to any public result (T9) |
| Hard-coding the shown examples | Hidden tests disjoint from public ones (T6); D5 shows the gap |
| Guessing | An answer-space floor above 10 percent is rejected (T10). That floor is declared by the task author and does not bound a model that guesses from priors such as small integers. The `smallint` agent (section 10) measures the empirical guess rate, and tasks where it exceeds 10 percent are revised |
| Reading hidden data from the prompt | Leakage lint (T12) and the public view type (schema 5.2) |
| A model changing its own evaluation | The model adapter returns text only. Only the runner creates a record. See the [experiment model](experiment-model.md), section 5 |
| Crashing the harness to void an attempt | `harness_fault` is counted, reported, and an official run must have none |
| Special-casing a published environment | Sealed held-out seeds (8.2) |

### 8.2 Against benchmark leakage

The generator code is public, so any environment and task can be regenerated by anyone. Procedural
generation **reduces** contamination risk. It does not remove it (design.md, section 15, says so
too).

| Control | Effect | Residual risk |
|---|---|---|
| Sealed held-out seeds with a commitment: the SHA-256 of the seed list and a secret salt is published before an evaluation round, the list is revealed afterwards | A model cannot have been tuned on those exact environments | If the salt is lost the commitment cannot be checked |
| New seeds per evaluation round, chosen after the models under test were released | Training data cannot contain the specific tasks | The family is still public (R4) |
| Dev environments are public and clearly separated | Honest development without touching the held-out set | Developers may still overfit to dev. P4 measures that |
| Surface re-skinning | A memorized solution in the canonical names does not match the surface form | A model could learn the re-skinning rules |
| A canary string in every published task artifact | A later model that reproduces it indicates contamination | Detects, does not prevent |
| Prompt leakage lint (T12) | No hidden item reaches the prompt | |
| Family version in every result | Results from a retired family are never mixed with new ones | |

* **R4: family-level contamination.** A model trained specifically on this generator could solve the
  family without general adaptation ability. The only real defense is a new family
  (new operation classes or new semantic dimensions), which is a future wave. Until then the
  benchmark must say that it measures this family.

## 9. Reproducibility

| Source of variation | Control |
|---|---|
| Random choices in generation | Hash derived streams, no `random` module (schema 3.5) |
| Runtime behavior | `runtime_semantics_version` in the environment identity, conformance corpus (schema 11.3) |
| Python and Lark versions | Recorded in the run manifest. A digest of the conformance corpus results is stored; a different digest is a hard error |
| Floating point | None in hashed content. Ratios are computed from integers at report time |
| Time | Timestamps and latencies are in a separate `volatile` section, excluded from comparisons and from hashes |
| Evaluation order | Tests run in declared order. Ties in rankings are broken by identifier |
| Model sampling | Not reproducible for stochastic models. Responses are stored, and evaluation (not generation) is what replay reproduces ([experiment model](experiment-model.md), section 8) |
| Wall clock limit | A backstop only. Any `wall_clock` event flags the run as non-reproducible |

An official run requires: coverage 1, zero `harness_fault`, zero `wall_clock` events, D10 equal to 0,
and a matching conformance digest.

## 10. Validating the metrics themselves

The metrics are design hypotheses until they are shown to separate known behaviors. Before any real
model is run (milestone M2.8, using the agents built in M2.7), the metrics are exercised with deterministic synthetic agents whose
behavior is known by construction. These are mock adapters, and they need no network and no cost.

| Agent | Behavior | Expected signature (checked exactly) |
|---|---|---|
| `oracle` (privileged, test only) | returns the reference answer or solution | P1 = 1 for every category, all paired effects 0, D1 = D2 = 1. Rejected by official runs |
| `prior` | answers as if the paired control environment applied (canonical meaning) | high P1 on control tasks, low on discriminating treatments, large P3, D6 close to 1 |
| `constant` | always the same fixed answer | P1 near the chance floor of the task set, P3 near 0 |
| `random` | uniformly random syntactically valid answers (seeded) | P1 near the chance floor, D1 high |
| `hardcoder` | returns a lookup table of the public examples | high public pass, near 0 hidden pass, D5 large |
| `smallint` | answers a small integer from 0 to 10 for every value task (seeded) | its P1 on value tasks is reported as the **effective chance floor** and must stay at or below 10 percent. A higher value means the task set needs revision |
| `syntax_only` | valid programs with wrong behavior | D1 = 1, P1 near 0 |
| `bomber` | infinite recursion | `resource_limit` on every program task, score `void`, provisional run |
| `garbage` | text with no answer | `extraction_failed` or `no_response`, score 0 |
| `hedger` | prints several candidate answers | only the last is read, no gain over a single answer |

Each row is a test that must pass. If a metric does not separate the agents it is designed to
separate, the metric is wrong and is changed before it is used on a real model. This validates the
**plumbing and the definitions**. It says nothing about whether the metrics measure real model
ability, which can only be learned from data on real models and, ideally, from comparison with
human performance (R12).

## 11. Open questions for this document

These are research questions, not engineering choices. The full list, R1 to R13, is in the
[overview](wave2-overview.md), section 12. Those that bear most on scoring:

* **R2: difficulty calibration.** Are tasks hard enough for strong models and easy enough for small
  local models? Unknown until a pilot.
* **R3: construct validity of categories.** Whether the seven categories load on distinct abilities
  needs data from many models. With free local models only, the sample of models is small and
  this cannot be claimed.
* **R5: documentation against inference.** Whether `FULL_DOC` and `EXAMPLES_ONLY` separate reading
  from inference cleanly.
* **R7: sample size.** Number of environments needed for a given effect size.
* **R8: prompt sensitivity.** Prompt wording may move results more than the manipulations. More than
  one prompt template per task set may be required.
* **R9: tokenization.** Pseudo-word names tokenize differently from familiar words. A cost under
  renaming may reflect tokens, not unfamiliarity.
* **R10: fairness of misleading familiar names.** Whether permuted familiar names test adaptation or
  only punish trust in names. Both readings are defensible.
