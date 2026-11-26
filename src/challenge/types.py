"""Task data types for UnknownLang Wave 2 benchmark."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence


# Version constants
TASK_SCHEMA_VERSION = 1
TASK_SET_SCHEMA_VERSION = 1
FAMILY_VERSION = "f1"

# Category enum
Category = Literal["SYN", "EVAL", "INF", "CTRL", "CONS", "REC", "ERR"]

# Template identifier format: <category>.<name>
TemplateId = str
TemplateVersion = int

# Protocol types
ProtocolKind = Literal["standalone", "paired"]
Variation = Literal[
    "environment:surface_names",
    "environment:operator_meaning",
    "environment:semantic_config",
    "information_condition",
    "example_policy",
]

Role = Literal["control", "treatment"]


@dataclass(frozen=True)
class Protocol:
    """Task protocol: standalone or paired with variations."""

    kind: ProtocolKind
    pair_group_id: str | None = None
    role: Role | None = None
    varies: tuple[Variation, ...] = ()


# Difficulty dimensions
DifficultyLevel = Literal[1, 2, 3, 4, 5]


@dataclass(frozen=True)
class Difficulty:
    """Challenge difficulty computed from dimensions, not asserted by author."""

    level: DifficultyLevel
    reasoning_steps: int
    nesting_depth: int
    control_flow: Literal["none", "conditional", "short_circuit", "recursion"]
    state: Literal["none", "simple", "multiple"]


# Information condition enum
InformationCondition = Literal[
    "FULL_DOC",
    "SIGNATURES_ONLY",
    "EXAMPLES_ONLY",
    "DELTA_DOC",
    "STALE_DOC_EXAMPLES",
]

# Visibility enum for definitions and tests
Visibility = Literal["public", "hidden"]

# Template structure
TemplateRef = tuple[str, int]  # (template_id, version)


@dataclass(frozen=True)
class Prompt:
    """Structured prompt inputs for the model."""

    template: TemplateRef
    example_policy: Literal["neutral", "misleading"]
    public_examples: Sequence[str]
    query: str | None = None
    spec: str | None = None  # Alternative to query


@dataclass(frozen=True)
class InputDefinitions:
    """Task-specific function definitions."""

    source: str
    visibility: Visibility
    must_define: Sequence[tuple[str, int]] | None = None  # (name, arity)


@dataclass(frozen=True)
class AnswerSpec:
    """Answer specification and format instructions."""

    type: Literal["value", "program"]
    kind: Literal["int", "bool", "error"] | None = None  # For value tasks
    form: Literal["definitions_only", "expression"] | None = None  # For program tasks
    chance_floor_ppm: int | None = None  # Probability in parts per million


@dataclass(frozen=True)
class Test:
    """Test case for program tasks."""

    test_id: str
    call: str
    expected: dict[str, Any]  # {kind: str, value: Any} or {kind: "error", error_class: str}
    visibility: Visibility


@dataclass(frozen=True)
class Evaluation:
    """Evaluation metadata."""

    method: Literal["exact_match", "test_suite"]
    limits: Mapping[str, int]
    tests: Sequence[Test]  # Empty for value tasks


@dataclass(frozen=True)
class Expected:
    """Expected result (PRIVATE - excluded from task_id hash)."""

    value: dict[str, Any]  # {kind: str, value: Any} or {kind: "error", error_class: str}


@dataclass(frozen=True)
class Verification:
    """Verification evidence (PRIVATE - excluded from task_id hash)."""

    sources: Sequence[Literal["closed_form", "production", "reference"]]
    agreement: bool


@dataclass(frozen=True)
class Provenance:
    """Provenance metadata (PRIVATE - excluded from task_id hash)."""

    generator: str
    version: str
    derivation_seed: str | None = None


# Task record fields
@dataclass(frozen=True)
class TaskRecord:
    """Canonical task record with identity and metadata."""

    schema_version: int
    task_id: str  # Computed from canonical record
    template: TemplateRef
    category: Category
    protocol: Protocol
    environment_id: str
    difficulty: Difficulty
    information_condition: InformationCondition
    prompt: Prompt
    answer_spec: AnswerSpec
    expected: Expected  # PRIVATE - excluded from identity
    evaluation: Evaluation
    input: InputDefinitions | None = None  # Optional: definitions with visibility
    verification: Verification | None = None  # PRIVATE - excluded from identity
    provenance: Provenance | None = None  # PRIVATE - excluded from identity
    notes: str | None = None  # PRIVATE - excluded from identity

    def to_canonical_dict(self) -> dict[str, Any]:
        """Return canonical dict for hashing (excludes task_id, verification, provenance, notes)."""
        data = {
            "schema_version": self.schema_version,
            "template": list(self.template),
            "category": self.category,
            "protocol": {
                "kind": self.protocol.kind,
                "pair_group_id": self.protocol.pair_group_id,
                "role": self.protocol.role,
                "varies": list(self.protocol.varies),
            },
            "environment_id": self.environment_id,
            "difficulty": {
                "level": self.difficulty.level,
                "reasoning_steps": self.difficulty.reasoning_steps,
                "nesting_depth": self.difficulty.nesting_depth,
                "control_flow": self.difficulty.control_flow,
                "state": self.difficulty.state,
            },
            "information_condition": self.information_condition,
            "prompt": {
                "template": list(self.prompt.template),
                "example_policy": self.prompt.example_policy,
                "public_examples": list(self.prompt.public_examples),
                "query": self.prompt.query,
                "spec": self.prompt.spec,
            },
            "answer_spec": {
                "type": self.answer_spec.type,
                "kind": self.answer_spec.kind,
                "form": self.answer_spec.form,
                "chance_floor_ppm": self.answer_spec.chance_floor_ppm,
            },
            "expected": self.expected.value,
            "evaluation": {
                "method": self.evaluation.method,
                "limits": dict(self.evaluation.limits),
                "tests": [
                    {
                        "test_id": t.test_id,
                        "call": t.call,
                        "expected": t.expected,
                        "visibility": t.visibility,
                    }
                    for t in self.evaluation.tests
                ],
            },
        }
        if self.input is not None:
            data["input"] = {
                "source": self.input.source,
                "visibility": self.input.visibility,
                "must_define": (
                    [list(md) for md in self.input.must_define] if self.input.must_define else None
                ),
            }
        return data


@dataclass(frozen=True)
class PublicTask:
    """Public view of a task (excludes expected, hidden tests, difficulty, etc.)."""

    schema_version: int
    task_id: str
    template: TemplateRef
    category: Category
    protocol: Protocol
    environment_id: str
    information_condition: InformationCondition
    prompt: Prompt
    answer_spec: AnswerSpec
    evaluation: Evaluation  # Only public tests
    input: InputDefinitions | None = None  # Optional: definitions with visibility


# Task set record fields
@dataclass(frozen=True)
class BlueprintSlot:
    """Blueprint slot specification."""

    category: Category
    count: int


@dataclass(frozen=True)
class Blueprint:
    """Task set blueprint."""

    id: str
    version: int
    slots: Sequence[BlueprintSlot]


@dataclass(frozen=True)
class EnvironmentAssignment:
    """Environment assignment to a split."""

    environment_id: str
    split: Literal["dev", "heldout"]


@dataclass(frozen=True)
class TaskAssignment:
    """Task assignment to an environment slot."""

    environment_id: str
    slot_index: int
    task_id: str


@dataclass(frozen=True)
class TaskSetRecord:
    """Canonical task-set record with identity."""

    schema_version: int
    family_version: str
    task_set_id: str  # Computed from canonical record
    blueprint: Blueprint
    environment_assignments: Sequence[EnvironmentAssignment]
    task_assignments: Sequence[TaskAssignment]
    pair_groups: Sequence[str]
    task_ids: Sequence[str]

    def to_canonical_dict(self) -> dict[str, Any]:
        """Return canonical dict for hashing. All fields are sorted for determinism."""
        return {
            "task_set_schema_version": self.schema_version,
            "family_version": self.family_version,
            "blueprint": {
                "id": self.blueprint.id,
                "version": self.blueprint.version,
                "slots": [
                    {"category": s.category, "count": s.count}
                    for s in sorted(self.blueprint.slots, key=lambda x: x.category)
                ],
            },
            "environment_assignments": sorted(
                [
                    {"environment_id": e.environment_id, "split": e.split}
                    for e in self.environment_assignments
                ],
                key=lambda x: (x["environment_id"], x["split"])
            ),
            "task_assignments": sorted(
                [
                    {
                        "environment_id": t.environment_id,
                        "slot_index": t.slot_index,
                        "task_id": t.task_id,
                    }
                    for t in self.task_assignments
                ],
                key=lambda x: (x["environment_id"], x["slot_index"], x["task_id"])
            ),
            "pair_groups": sorted(self.pair_groups),
            "task_ids": sorted(self.task_ids),
        }
