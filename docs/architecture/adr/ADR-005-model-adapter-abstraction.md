# ADR-005: Model adapter abstraction

Status: **Proposed. Pending approval.**
Related: [experiment model](../experiment-model.md) section 5. Specification delta SD2.

## Context

The benchmark must run end to end with no network, no key and no cost, and later accept local models
without any change to evaluation. An adapter must not be able to influence scoring other than through
the text of its answer. requirements.md (Requirement 11) names a provider interface with
`list_models`, `generate` and `estimate_tokens`, and an OpenAI compatible API as the first provider.

## Decision

1. **The adapter port is text in, text out.** `generate(PromptBundle, GenerationConfig) -> RawResponse`.
   The bundle is built from the **public view** of a task. An adapter never receives a task, an
   environment object, an expected answer or a score.
2. **Failure is data.** `RawResponse` carries an optional adapter error. The runner turns a raised
   exception into `adapter_unavailable`. It does not become a score.
3. **Only the runner writes records.** Extraction, validation, translation, execution and comparison
   are harness code that the adapter cannot call.
4. **`list_models` and `estimate_tokens` stay in the interface**, as required, and the mock implements
   them trivially.
5. **Adapters import only the standard library and `src.benchmark.ports`.** An import boundary test
   enforces this.
6. **Adapters declare `privileged`.** Test agents that need ground truth (an oracle, a prior-semantics
   agent) are privileged. The runner refuses them in official runs and records the flag.
7. **Mocks come first.** A scripted replay adapter and deterministic strategy agents (constant,
   seeded random, small integer guesser, garbage, resource bomber, syntax-only, hedger, hard-coder) make the whole benchmark
   testable without any model.
8. **No secret is read, stored or logged** by the benchmark in this wave. A local HTTP adapter is a
   later milestone and needs separate approval.

## Alternatives considered

| Alternative | Why it was rejected |
|---|---|
| Adapter receives the `Task` | Opens the expected answer and hidden tests to the component that must not see them |
| Adapter returns a parsed, structured answer | Moves extraction into untrusted code, makes parsing differ per provider, and lets an adapter claim a result |
| An OpenAI compatible API first (Requirement 11, criterion 2) | Paid, needs a key, and external availability cannot be assumed. A local server may later offer a compatible wire format |
| One SDK per provider as the interface | Ties the benchmark to vendor libraries and violates the minimal dependency rule |
| A plugin system with entry points | A mechanism with no second implementation to justify it yet |
| An asynchronous interface | The workload is sequential, bound by model speed. Adds complexity without a benefit |

## Consequences

Positive: the benchmark is fully testable offline. Adding a provider cannot affect scoring. The
leak surface is one type (`PromptBundle`).

Costs: the port hides provider features such as multi turn state and tool use, which an interactive
protocol (R13) would need. That would be a new port, not a change to this one. Token accounting
depends on what an adapter reports and can be absent.

## Verification

* An import boundary test over every module under `src.models`.
* A test that builds prompts for a full task set and scans them for hidden items (T12).
* The strategy agents of the evaluation document, section 10, run through the real runner and produce
  their expected signatures.
* A test that a privileged adapter is refused in official mode.

## Revisit when

An interactive protocol is designed (R13), or a provider requires state that text in and text out
cannot carry.
