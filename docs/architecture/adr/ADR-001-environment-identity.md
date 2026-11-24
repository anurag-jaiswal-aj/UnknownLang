# ADR-001: Environment identity and the surface layer

Status: **Proposed. Pending approval.**
Related: [task schema](../benchmark-task-schema.md) sections 3 and 4, [runtime findings](../runtime-findings.md) F2, F4, F6.

## Context

A benchmark result is only meaningful if it names the exact environment it came from, and only
comparable if the same name always means the same behavior. The existing `LanguageSpec.language_id`
does not provide that:

* It hashes the seed and two caller supplied version strings. Name, features and difficulty do not
  change the language, so 36 seeds gave 36 identifiers for 6 different languages (F6).
* It does not change when runtime behavior changes. Waves 1C.15 and 1C.16 altered behavior and left
  every `language_id` the same (F4).

The audit also showed that only 6 distinct languages exist, all with the same grammar and the same
familiar operator names (overview, section 2). A benchmark of unfamiliar languages cannot be built on
that alone, and the grammar and evaluator semantics are frozen.

## Decision

1. **Identity has two levels.** `observable_fingerprint` is the hash of canonical grammar, semantic
   specification and surface profile. `environment_id` is `env_` plus the SHA-256 of canonical JSON
   containing `env_schema_version`, `generator_family_version`, `generator_algorithm_version`,
   `observable_fingerprint` and `runtime_semantics_version`. The seed, derivation path, inert seed
   fields, Python/Lark versions and timestamps are descriptive metadata. The legacy `language_id`
   remains a compatibility cross-reference, not the Wave 2 environment identity.
2. **Variation beyond the six configurations comes from a surface layer**: a surface profile
   (keyword, operator and literal names, with an optional permutation of meaning inside a type
   class) and a deterministic translator that maps surface text to canonical text before the
   unmodified runtime runs it. Every user identifier is mangled to `_u<N>`.
3. **Derivation is hash based**: each random decision is `H(master_seed | purpose | index)`. The
   `random` module is not used.
4. **Runtime behavior is versioned** by an integer `runtime_semantics_version` that enters the
   identity. It is a new constant (proposed in M2.1, needing approval).
5. **The inert seed fields are pinned** to constants by the environment manager.
6. Environments are immutable once `frozen` and are never deleted.

## Alternatives considered

| Alternative | Why it was rejected |
|---|---|
| Reuse `language_id` | It splits identical languages and merges different behaviors (F4, F6) |
| Include the seed in the identity | Two derivations that produce the same environment would get different identities, and inert fields would create false variety |
| Include generator family and algorithm versions in the environment identity | A changed derivation recipe must not silently reuse a scientific identity. Keep `observable_fingerprint` separate for byte-identical output detection |
| Include Python and Lark versions in the identity | A result that depends on them is a defect to detect, not a new environment. They are attested in the run manifest instead, with a conformance digest |
| Change the grammar to create syntactic variety | The grammar is frozen, and a change would restart the foundation of Wave 1 |
| Add new operator semantics to the evaluators | The semantics are frozen. This is the natural content of a **future language family**, and is noted as the only real answer to family-level contamination (R4) |
| Use Python's `random` for derivation | The algorithms of `shuffle`, `sample` and `choice` have changed between Python versions, so the same seed could give different environments |

## Consequences

Positive:

* The same observable environment always has the same identifier, and a changed behavior always
  changes it.
* Operator names are unfamiliar by construction, and a familiar name can carry a misleading meaning,
  which the controlled comparisons need.
* Variety grows from 6 configurations to 6 times the number of meaning assignments, times unlimited
  name draws, without touching the frozen grammar.
* It removes the keyword-prefix misparse (F2) from the benchmark path.

Costs and risks:

* The translator is a new component, and **a bug in it affects both evaluators equally**, so
  the evaluators' independence does not protect against it. It needs its own property tests, against
  both evaluators, and a second independently written tokenizer inside the test suite.
* The surface profile widens the specification (delta SD6).
* The language family is still small (overview, section 2). The surface layer makes names unfamiliar.
  It does not make semantics richer.
* Identity includes the runtime version, so any intentional behavior change makes older results
  non-comparable. This is the intended effect.

## Verification

* Gates E1 to E8 ([task schema](../benchmark-task-schema.md), 3.7), including a differential test of
  surface-form programs against canonical programs on both evaluators.
* The worked examples in the task schema were recomputed from these rules. Their identifiers are
  reproducible.
* A conformance corpus whose result digest is part of every run manifest.

## Revisit when

* A second language family is introduced, or the grammar is unfrozen.
* The `runtime_semantics_version` rule proves too coarse or too fine in practice.
