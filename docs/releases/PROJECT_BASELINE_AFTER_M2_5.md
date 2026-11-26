# Project Baseline After M2.5

**Baseline commit:** 35bf1e55b13a03206982672bf04f66a994d89d0e  
**Baseline tag:** v2.5.0  
**Baseline date:** 2026-11-26

---

## Current Repository Architecture

### Core Components

```
src/
├── benchmark/
│   ├── canonical.py          # Canonical JSON and SHA-256 hashing
│   ├── environments.py       # Environment derivation and management
│   ├── generators/           # Task generators (M2.5)
│   │   ├── __init__.py
│   │   ├── generator.py      # TaskGenerator, T5/T7/T8/T13 enforcement
│   │   ├── identifiability.py # T13 identifiability checking
│   │   └── registry.py       # Generator registry system
│   ├── language_reference.py # Language reference data
│   ├── manager.py            # Benchmark execution manager
│   └── prompts.py            # Prompt templates
├── challenge/
│   ├── __init__.py           # Module exports
│   ├── identity.py           # Task/task-set identity (SHA-256)
│   ├── projection.py         # Public/private projection
│   ├── types.py              # Task/TaskSet dataclasses
│   └── validation.py         # Validation rules T1-T15
└── language/                 # Language specification and generation
    ├── generator.py
    ├── semantic_spec.py
    ├── semantics.py
    └── surface.py
```

### Implemented Components

| Component | Status | Notes |
|-----------|--------|-------|
| Task schema | ✅ Implemented | `TaskRecord`, `TaskSetRecord`, `PublicTask` |
| Task identity | ✅ Implemented | SHA-256 via `compute_task_id()` |
| Validation | ✅ Implemented | T1, T2, T6, T9, T10 in generic validator |
| Generator | ✅ Implemented | T5, T7, T8, T13 in generator layer |
| Public projection | ✅ Implemented | `project_public()` filters private data |
| T5 verification | ✅ Implemented | `T5Verification.verify()` |
| T7/T8 pairs | ✅ Implemented | `validate_pair()` |
| T13 identifiability | ✅ Implemented | `T13Identifiability.check()` for INF |
| Environment derivation | ✅ Implemented | `build_environment()` |
| Prompt templates | ✅ Implemented | `Prompt` dataclass |

### Public Interfaces

| Interface | Location | Purpose |
|-----------|----------|---------|
| `TaskGenerator` | `src/benchmark/generators/generator.py` | Task generation |
| `T5Verification` | `src/benchmark/generators/generator.py` | Two-source verification |
| `T13Identifiability` | `src/benchmark/generators/identifiability.py` | INF identifiability |
| `validate_task()` | `src/challenge/validation.py` | Generic validation |
| `validate_pair()` | `src/benchmark/generators/generator.py` | Pair validation |
| `project_public()` | `src/challenge/projection.py` | Public view projection |
| `compute_task_id()` | `src/challenge/identity.py` | Task identity computation |

---

## Runtime and Environment Identity Contracts

### Environment Identity

- **Source:** Derivation from semantic configuration (arithmetic mode, short-circuit behavior)
- **Format:** `SHA256(canonical_seed + spec_version + algorithm_version)`
- **Runtime identity:** Separate from legacy `language_id` (F4 implemented)

### Task Identity

- **Algorithm:** SHA-256 of canonical JSON (excluding task_id, verification, provenance, notes)
- **Format:** `task_<64-hex-chars>`
- **Guarantee:** Deterministic, collision-resistant

---

## Challenge Schema and Task Identity

### TaskRecord Fields

- **Public (included in identity):** schema_version, template, category, protocol, environment_id, difficulty, information_condition, prompt, answer_spec, expected, evaluation, input
- **Private (excluded from identity):** task_id, verification, provenance, notes

### PublicTask Fields

- **Filtered:** expected, hidden tests, difficulty, protocol.role, verification, provenance, notes

---

## Generator Architecture

### Generation Layers

| Layer | Rules | Implementation |
|-------|-------|----------------|
| Generator | T5, T7, T8, T13 | `TaskGenerator`, `T5Verification`, `validate_pair()`, `T13Identifiability` |
| Validator | T1, T2, T6, T9, T10 | `validate_task()`, `compute_task_id()` |

### Generation Paths

| Category | Generation Method | T13 Applied? |
|----------|-------------------|--------------|
| EVAL | `_generate_eval_task()` | No |
| SYN | `_generate_syn_task()` | No |
| INF | `_generate_inf_task()` | Yes (generator layer) |
| CTRL | `_generate_ctrl_task()` | No |

---

## Validation and Projection Boundaries

### Generator Layer Checks

- **T5:** Two-source expected verification (production + reference)
- **T7:** Canonical comparison (field differences per variation)
- **T8:** Discriminating pairs (expected differs for semantic changes)
- **T13:** Identifiability (INF only, approved generation paths)

### Validator Layer Checks

- **T1:** Schema validation (required fields, version, unknown fields)
- **T2:** Task ID hash consistency
- **T6:** Hidden test disjointness (substring matching)
- **T9:** Non-triviality (expected not in query/examples)
- **T10:** Chance floor limit (≤100000)

### Deferred Checks

- **T3, T4, T11, T12, T14, T15:** Deferred per specification

---

## Existing Tests and Verification Commands

### Test Suite

```bash
# Full test suite
python3 -m pytest tests/ -v --tb=short

# T5/T7/T8/T13 generator tests
python3 -m pytest tests/test_generators.py tests/test_generators_focused.py -v --tb=short

# T13 identifiability tests
python3 -m pytest tests/test_t13_identifiability.py -v --tb=short

# T6/T9/T10 validation tests
python3 -m pytest tests/test_task_validation.py -v --tb=short

# Public projection tests
python3 -m pytest tests/test_public_projection.py -v --tb=short
```

### Test Statistics

- **Total tests:** 1,463
- **Passing:** 1,463
- **Failing:** 0
- **Skipped:** 0
- **XFAIL:** 0
- **Warnings:** 6

---

## Known Placeholders and Deferred Functionality

| Component | Status | Notes |
|-----------|--------|-------|
| T3 EnvironmentManager | Deferred | Requires full implementation |
| T4 template registration | Deferred | Requires registration system |
| T11 runtime profiling | Deferred | Requires profiling infrastructure |
| T12 prompt leakage lint | Deferred | Requires prompt construction |
| T14 must_define check | Deferred | Requires reference solution |
| T15 blueprint limits | Deferred | Requires blueprint |

---

## Known Security and Execution Boundaries

| Boundary | Status | Notes |
|----------|--------|-------|
| Process sandbox | Not implemented | T11 deferred |
| Cross-process environment persistence | Not implemented | T3 deferred |
| Prompt-based leakage lint | Not implemented | T12 deferred |
| Hidden test generation | Not in M2.5 scope | Not used by generators |

---

## Existing Roadmap Decisions Relevant to M2.6

### Wave 2 Milestone Order

```
M2.5 → M2.6 (Harness) → M2.7 → M2.8 → M2.9 → M2.10 → M2.11
```

### Approved Architecture Decisions

- **D-001:** Task/pair canonical equivalence (owner-approved)
- **D-002:** Task-set identity and split hashing (owner-approved)
- **D-003:** Environment/generator/runtime identity (owner-approved)
- **D-004/D-005:** Scoring unit and bootstrap contract (owner-approved)
- **D-006/D-007:** D8 and undefined-value rules (owner-approved)
- **D-008:** Runtime status contract (owner-approved)
- **D-009:** Trusted-local vs security-compliant (owner-approved)
- **D-010:** Provider and storage amendments (owner-approved)
- **D-011:** Worked-example regeneration (owner-approved)
- **D-012:** Byte-framed derived randomness (owner-approved)

See `docs/architecture/requirements-traceability.md` for full decision register.

---

*This baseline document describes the repository state at the M2.5 release point.*
