# Task schema for UnknownLang Wave 2
"""
Task schema implementation for UnknownLang Wave 2 benchmark.

This module provides:
- TaskRecord dataclass for canonical task identity
- TaskSetRecord dataclass for task-set identity
- Validation functions for rules T1-T15
- Public/private projection function (project_public)
- Prompt construction functions

Identity Functions:
- compute_task_id(task): SHA256 of canonical task record
- compute_task_set_id(task_set): SHA256 of canonical task-set record

Validation Gates:
- validate_task(task): T1-T15 validation
- validate_task_set(task_set): TS1-TS4 validation

Projection:
- project_public(task): Returns public view only (excludes expected, hidden tests, etc.)
"""

from .types import (
    TaskRecord,
    TaskSetRecord,
    PublicTask,
    Protocol,
    Evaluation,
    AnswerSpec,
    Prompt,
    InputDefinitions,
    Visibility,
    InformationCondition,
    Difficulty,
)

from .identity import compute_task_id, compute_task_set_id

from .validation import validate_task, validate_task_set

from .projection import project_public

__all__ = [
    # Types
    "TaskRecord",
    "TaskSetRecord",
    "PublicTask",
    "Protocol",
    "Evaluation",
    "AnswerSpec",
    "Prompt",
    "InputDefinitions",
    "Visibility",
    "InformationCondition",
    "Difficulty",
    # Identity
    "compute_task_id",
    "compute_task_set_id",
    # Validation
    "validate_task",
    "validate_task_set",
    # Projection
    "project_public",
]
