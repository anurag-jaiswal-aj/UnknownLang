# ADR-003: Evaluation methodology

Status: **Proposed. Pending approval.**
Related: [evaluation and scoring](../evaluation-and-scoring.md).

## Context

The benchmark must say more than pass or fail, but richer scores invite arbitrary weights, and the
goal is a measurement with defensible meaning. No real model has been run, so any claim about what a
metric shows is a hypothesis.

## Decision

1. **The primary score per task is binary.** A program passes only if every public and hidden test
   passes. A value passes only on exact, type exact equality.
2. **The headline is the unweighted mean over categories** of pooled accuracy on held-out environments.
   No difficulty weights, and no combined "adaptation index".
3. **Capability claims are paired differences** on matched tasks that differ in exactly the manipulated
   factor, always read together with accuracy.
4. **Uncertainty is a cluster bootstrap over environments**, with a deterministic resampling stream.
5. **Failures are a closed taxonomy.** Infrastructure failures are `void` and counted. A run with void
   attempts is incomplete and never ranked.
6. **Resource-limit outcomes score 0** and are reported as their own category (specification delta SD5).
7. **Diagnostics are never merged into the primary score**: partial test pass fraction, the gap
   between public and hidden tests, syntax validity, the rate of answers matching a stale semantics,
   step efficiency, response stability.
8. **Metrics are validated before use**, against deterministic synthetic agents whose behavior is
   known by construction.

## Alternatives considered

| Alternative | Why it was rejected |
|---|---|
| Partial credit as the primary score | Cannot separate a near miss from a lookup table of the shown examples. It rewards the second |
| A difficulty weighted headline | The weights would be invented. A sensitivity row is provided instead |
| A single scalar mixing accuracy, adaptation and efficiency | Hides the structure the benchmark exists to expose, and the mixture weights would be arbitrary |
| Excluding resource-limit attempts as "inconclusive" | A model could avoid a wrong answer by writing an expensive program. Kept distinct instead of excluded |
| Item response theory or Elo style ratings | Needs many models and many tasks per model. With a handful of free local models the estimates would be unstable. Revisit when data exists |
| Plain binomial intervals over tasks | Tasks in one environment are not independent. The environment is the resampling unit |
| `pass@k` as the headline | Stochastic sampling is a model property. The default is one deterministic sample, and `k` samples give a pass rate and a stability diagnostic |
| Retrying void attempts until they pass | Would let infrastructure noise decide results. Void attempts are rerun by key and reported |

## Consequences

Positive: every number has a definition, a range, a direction and a stated gaming route. The primary
score cannot be raised by emitting invalid output, hedging, hard-coding examples, or being expensive.
Comparisons that matter to the research claims are paired by construction.

Costs: binary scoring is harsh, and a model that is nearly right looks like one that is wrong in the
headline (the diagnostics show the difference). Paired designs need more tasks than unpaired ones.
Cluster bootstrap with few environments gives wide intervals, which is honest.

## Verification

* The synthetic agent table in [evaluation and scoring](../evaluation-and-scoring.md), section 10,
  implemented as tests with exact expected signatures (M2.8).
* Property tests: macro and micro averages agree when category slot counts are equal, a model that
  fails everything gets every paired effect equal to 0, and a bootstrap with a fixed stream is repeatable.
* Hand-computed small examples for every formula.

## Revisit when

Real model data exists and reveals ceiling or floor effects (R2), unexpected weights between
categories (R3), or prompt sensitivity above the manipulated effects (R8).
