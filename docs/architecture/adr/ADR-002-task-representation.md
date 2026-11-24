# ADR-002: Task representation

Status: **Proposed. Pending approval.**
Related: [task schema](../benchmark-task-schema.md), [evaluation and scoring](../evaluation-and-scoring.md).

## Context

Tasks must be reproducible, independently verifiable, comparable across models, and impossible to
leak by accident. They must also support controlled comparisons (the same task under one changed
factor) without a separate machinery for each comparison.

## Decision

1. **A task is an immutable, content addressed JSON record.** `task_id = "task_" + SHA-256` of the
   canonical record **excluding** `task_id`, `verification`, `provenance` and `notes`. `expected` is
   included (it is the claim). `verification` is excluded (it is evidence for the claim, and adding
   evidence must not change the claim's identity).
2. **A task set is also content addressed.** Its identity includes schema and family versions, the
   complete blueprint/version/slots, sorted `(environment_id, split)` assignments and sorted task IDs.
   Reversing dev and held-out assignments therefore creates a new set.
3. **Public and private data are separated by a type.** `project_public(task)` is the only source of
   anything a prompt may use. Hidden tests, `expected`, verification and difficulty never enter it.
3. **Prompts are derived, not stored.** A task stores structured prompt inputs and the template
   version. The text is built by a versioned builder.
4. **Seven categories and one protocol field.** Categories name what is asked
   (`SYN EVAL INF CTRL CONS REC ERR`). Controlled comparisons are expressed by a `paired` protocol
   with an explicit `varies` list, not by more categories. Adaptation and transfer are conditions,
   not categories.
5. **Two grading methods only.** `exact_match` for values, and `test_suite` for programs. There are
   no per-task Python graders.
6. **Program tasks accept definitions only.** The harness supplies the final expression.
7. **Every expected result needs production and the independent reference evaluator** within the
   oracle envelope, plus a closed form when one exists. A task outside the envelope is rejected or
   deferred, not verified by production plus a closed form alone. A disagreement invalidates the task.
8. **Validity gates are part of the schema** (T1 to T15 and TS1 to TS4), for example that an adaptation task must
   actually discriminate between its two environments and that surface-renamed queries translate to
   the same canonical program.

## Alternatives considered

| Alternative | Why it was rejected |
|---|---|
| Store the prompt text in the task | Prompt wording would be fused with task identity, hidden items could leak into it unnoticed, and changing wording would change the task |
| Tasks as database rows | Separate decision (ADR-004). A row format does not give content addressing |
| Grader functions written in Python per task | Executes arbitrary host-language code, which the brief forbids, and cannot be audited as data |
| Adaptation and transfer as categories | They are conditions applied to categories. Making them categories hides what is held constant |
| Include `verification` in the identity | Re-verifying a task, or adding a second source, would silently create a new task |
| Allow submissions that end in an expression | Exposes the definition-last difference between the evaluators (F1) and lets the submission choose what is tested |
| Partial credit inside the task schema | A scoring choice, argued in ADR-003. The schema records enough (per test results) to compute any alternative later |

## Consequences

Positive: identical tasks deduplicate, tampering with an expected answer changes the identifier,
pairs and task sets can be checked mechanically, and the public view cannot be widened by accident
because it is a separate type.

Costs: tasks are verbose records. Generators need verification machinery before producing anything,
and some tasks are rejected (for example when no discriminating query exists), which makes
generation cost higher than writing tasks by hand.

## Verification

* Rules T1 to T15 and TS1 to TS4 as automated validators, each with a negative test.
* The three worked examples were generated and verified on both evaluators, and the identifiers
  recomputed.
* A leakage test: build the prompt for every task and check that no hidden item appears in it (T12).

## Revisit when

A task type needs state that a definition-only program cannot express, or a category's tasks cannot be
verified by two sources.
