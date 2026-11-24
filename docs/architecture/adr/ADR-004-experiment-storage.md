# ADR-004: Experiment storage

Status: **Proposed. Pending approval.**
Related: [experiment model](../experiment-model.md) sections 4, 7, 8. Specification delta SD4.

## Context

The benchmark must persist environments, tasks, prompts, responses, evaluation records and reports,
support resuming an interrupted run, allow independent checking, and cost nothing. requirements.md
(Requirement 12) calls for SQLite, with database work deferred past the MVP.

The expected volume is small. A run of `E x B x k` attempts, for example 20 x 14 x 1 = 280 per model,
is a few hundred records, and even 100 environments and 20 models stays in the tens of thousands.

## Decision

1. **Plain files are the source of truth.** Immutable content addressed JSON for environments, tasks
   and task sets, a content addressed artifact directory for texts, and one append only
   `attempts.jsonl` per run.
2. **Each attempt record is hash chained** to the previous one, starting from the manifest digest.
   Edits, deletions and reordering are detectable. Records are not signed, so this is tamper evidence
   and not tamper proofing.
3. **One writer per run**, an `fsync` per record, and resume by attempt key. A partial last line is
   moved aside and reported, never silently deleted.
4. **No database, no server, no queue in Wave 2.** If a query interface is needed later, a
   **derived and disposable** SQLite index is built from the files.
5. Held-out tasks, their private data and sealed seed lists live in the data root, **outside the
   repository**. The repository contains the generators and the dev split only.
6. Reports are a pure function of the records and can always be regenerated.

## Alternatives considered

| Alternative | Why it was rejected |
|---|---|
| SQLite now (the specification's choice) | It adds a schema, migrations and a second representation of the same facts, and offers no scientific benefit at this volume. It does not give content addressing or an independent integrity check. Kept as the future derived index |
| PostgreSQL or any server database | Cost, operations, and no requirement that justifies them |
| One large JSON file | Not append safe. A crash loses the run. No resume |
| Parquet or a columnar format | Adds a dependency and is unnecessary at this size |
| Committing results to git | Held-out data must not be public before the reveal. Large artifacts bloat history. The hash chain gives integrity without git |
| A message queue and workers | The workload is a loop over attempts, bounded by model speed |

## Consequences

Positive: zero infrastructure, human readable evidence, easy replay, results can be archived
as a directory and checked by anyone, and the format does not depend on a particular library.

Costs: ad hoc queries need code or a derived index. There is no concurrent writer support. File
level locking must be correct on every platform used. Large artifact directories need housekeeping
(artifacts are shared by digest and are never deleted automatically).

## Verification

* A corrupted line, a deleted line and a swapped pair of lines must each be detected by the chain check.
* A run interrupted at every attempt boundary must resume to the same final records.
* Replay modes RP1 to RP3 ([experiment model](../experiment-model.md), 8.1) pass on a stored run.
* Writing an existing content addressed file with different content must raise.

## Revisit when

There are more than about a million attempts, several processes must write at once, or an interface
needs ad hoc queries. Then add the derived SQLite index.
