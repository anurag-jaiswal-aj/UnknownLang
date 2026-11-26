"""Task and task-set validation rules T1-T15 and TS1-TS4."""

from __future__ import annotations
import re
from typing import Any

from src.benchmark.canonical import canonical_json, sha256_hex

from .types import (
    TaskRecord,
    TaskSetRecord,
    Category,
    InformationCondition,
    ProtocolKind,
    Visibility,
    DifficultyLevel,
)
from .identity import compute_task_id
from .projection import project_public


def _extract_literals_from_query(query: str) -> set[str]:
    """Extract all integer literal strings from a query using AST-based parsing.
    
    This function uses Lark to parse the query and extract all literal values,
    ensuring robust identification of literals regardless of formatting.
    
    Args:
        query: Query string in UnknownLang syntax
        
    Returns:
        Set of string representations of integer literals found in the query
        
    Raises:
        ValidationError: If parsing fails unexpectedly (not just syntax errors).
    """
    from src.challenge.validation import ValidationError
    
    try:
        from lark import Lark
        from lark.exceptions import UnexpectedCharacters, UnexpectedToken, UnexpectedEOF
        
        # Create a minimal grammar parser for expressions
        # This grammar accepts ANY operator name, not just a fixed set
        # The goal is to parse the structure and extract NUMBER tokens
        grammar = """
            ?start: program
            program: program_element*
            ?program_element: expr
            ?expr: "(" OPERATOR expr+ ")" | NUMBER | IDENTIFIER
            OPERATOR: /\\w+/
            NUMBER: /-?[0-9]+/
            IDENTIFIER: /[a-zA-Z_][a-zA-Z0-9_]*/
            %import common.WS
            %ignore WS
        """
        
        parser = Lark(grammar, start="program")
        tree = parser.parse(query)
        
        # Extract all NUMBER tokens from the tree using scan_values
        literals = set()
        for token in tree.scan_values(lambda t: hasattr(t, 'type') and t.type == "NUMBER"):
            literals.add(token.value)
        
        return literals
    except (UnexpectedCharacters, UnexpectedToken, UnexpectedEOF):
        # Fallback to regex-based extraction if Lark parsing fails due to syntax issues
        # This handles malformed queries where the parser can't build any structure
        # Use (?<!\w) to avoid matching partial tokens like 3 in (add 3 4)
        return set(re.findall(r'(?<!\w)-?\d+(?!\w)', query))
    except Exception as e:
        # Unexpected exception - do not convert to regex success
        raise ValidationError(
            "T9", 
            f"Internal validation error in literal extraction: {type(e).__name__}: {e}",
            "query"
        )


# Validation error types
class ValidationError(ValueError):
    """Raised when task or task-set validation fails."""
    def __init__(self, rule: str, message: str, field: str | None = None):
        self.rule = rule
        self.message = message
        self.field = field
        super().__init__(f"[{rule}] {message}" + (f" ({field})" if field else ""))


class ValidationRule:
    """Represents a validation rule with its name and description."""
    def __init__(self, rule_id: str, description: str):
        self.rule_id = rule_id
        self.description = description


# Task validation rules T1-T15
def validate_task(task: TaskRecord | dict[str, Any]) -> list[ValidationRule]:
    """
    Validate a task record against rules T1-T15.
    
    T1: schema_version is known. No unknown fields. No missing required fields.
    T2: task_id equals the recomputed hash. [IMPLEMENTED]
    T3: environment_id resolves to a frozen environment. (Deferred - requires EnvironmentManager)
    T4: category is allowed for template.id. (Deferred - requires template registration)
    T5: expected is confirmed by production and the independent reference evaluator.
        (Deferred - requires evaluation harness)
    T6: Hidden tests are disjoint from public examples and from the query. [IMPLEMENTED]
    T7: Paired tasks pass the canonical comparison projection. (Deferred - requires pair validation)
    T8: Pairs are checked by running both environments. (Deferred - requires evaluation)
    T9: Non-triviality: for value answers, expected is not equal to any literal in the query. [IMPLEMENTED]
    T10: chance_floor_ppm is at most 100000. [IMPLEMENTED]
    T11: Oracle envelope: every expected result and reference solution stays at call depth 40 or less.
         (Deferred - requires runtime profiling)
    T12: Leakage lint: no hidden test call, hidden definition source or reference solution text
         appears anywhere in the prompt built from the public view. (Deferred - requires prompt construction)
    T13: Identifiability (INF): for every surface operator used by the query,
         the public examples leave exactly one consistent canonical meaning within its type class.
         (Deferred - requires surface profile)
    T14: Every must_define name and arity in the answer spec is consistent with the reference solution.
         (Deferred - requires reference solution)
    T15: limits do not exceed the global caps recorded in the blueprint. (Deferred - requires blueprint)
    
    Args:
        task: TaskRecord or dict with all required fields
        
    Returns:
        List of validation rules that passed
        
    Raises:
        ValidationError: If any rule fails
    """
    rules_passed = []
    
    # T1: schema_version is known. No unknown fields. No missing required fields.
    if isinstance(task, TaskRecord):
        data = task.to_canonical_dict()
    else:
        data = task.copy()
    
    required_fields = {
        "schema_version", "template", "category", "protocol", "environment_id",
        "difficulty", "information_condition", "prompt", "answer_spec",
        "expected", "evaluation"
    }
    optional_fields = {"input", "verification", "provenance", "notes", "task_id"}
    
    actual_fields = set(data.keys())
    missing = required_fields - actual_fields
    if missing:
        raise ValidationError("T1", f"Missing required fields: {missing}")
    
    unknown = actual_fields - required_fields - optional_fields
    if unknown:
        raise ValidationError("T1", f"Unknown fields: {unknown}")
    
    if data.get("schema_version") != 1:
        raise ValidationError("T1", "schema_version must be 1")
    
    rules_passed.append(ValidationRule("T1", "Schema version and required fields"))
    
    # T2: task_id equals the recomputed hash [IMPLEMENTED]
    # Compute expected ID (excluding task_id, verification, provenance, notes)
    expected_task_id = compute_task_id(task)
    
    # Validate task_id for all inputs - no exceptions for placeholders
    is_dict_task = isinstance(task, dict)
    task_id_value = data.get("task_id", "") if is_dict_task else task.task_id
    
    if task_id_value != expected_task_id:
        raise ValidationError("T2", f"task_id mismatch: expected {expected_task_id}, got {task_id_value}")
    rules_passed.append(ValidationRule("T2", "Task ID hash verification"))
    
    # T6: Hidden tests are disjoint from public examples and from the query [IMPLEMENTED]
    if isinstance(task, TaskRecord):
        prompt = task.prompt
        evaluation = task.evaluation
        
        # Check that no hidden test call matches public examples or query
        query_text = prompt.query or ""
        public_examples = set(prompt.public_examples)
        
        for test in evaluation.tests:
            if test.visibility == "hidden":
                if test.call in public_examples:
                    raise ValidationError("T6", f"Hidden test call matches public example: {test.call}")
                if test.call in query_text:
                    raise ValidationError("T6", f"Hidden test call matches query: {test.call}")
    else:
        # For dict input
        evaluation = data.get("evaluation", {})
        tests = evaluation.get("tests", [])
        prompt = data.get("prompt", {})
        query_text = prompt.get("query", "")
        public_examples = set(prompt.get("public_examples", []))
        
        for test in tests:
            if test.get("visibility") == "hidden":
                test_call = test.get("call", "")
                if test_call in public_examples:
                    raise ValidationError("T6", f"Hidden test call matches public example: {test_call}")
                if test_call in query_text:
                    raise ValidationError("T6", f"Hidden test call matches query: {test_call}")
    rules_passed.append(ValidationRule("T6", "Hidden tests disjoint from public"))
    
    # T7: Paired tasks pass canonical comparison projection
    # (Deferred - requires pair validation)
    rules_passed.append(ValidationRule("T7", "Paired tasks canonical projection (deferred)"))
    
    # T8: Pairs are discriminating (expected differs for semantic changes)
    # (Deferred - requires evaluation)
    rules_passed.append(ValidationRule("T8", "Pairs are discriminating (deferred)"))
    
    # T9: Non-triviality [IMPLEMENTED]
    # Expected value should not appear as a literal in the query or public examples
    # Using AST-based literal extraction for robustness
    if isinstance(task, TaskRecord):
        if task.answer_spec.type == "value" and task.answer_spec.kind in ("int", "bool"):
            expected_value = task.expected.value
            
            # Extract expected value for comparison
            expected_str = None
            if isinstance(expected_value, dict):
                if expected_value.get("kind") == "int":
                    expected_str = str(expected_value.get("value"))
                elif expected_value.get("kind") == "bool":
                    expected_str = str(expected_value.get("value")).lower()
            
            if expected_str:
                # Extract all literals from query using Lark parser
                query_text = task.prompt.query or ""
                query_literals = _extract_literals_from_query(query_text)
                if expected_str in query_literals:
                    raise ValidationError("T9", f"Expected value {expected_str} appears as literal in query: {query_text}")
                
                # Check against public examples - extract literals from each
                for example in task.prompt.public_examples:
                    example_literals = _extract_literals_from_query(example)
                    if expected_str in example_literals:
                        raise ValidationError("T9", f"Expected value {expected_str} appears as literal in public example: {example}")
    else:
        # For dict input
        answer_spec = data.get("answer_spec", {})
        if answer_spec.get("type") == "value" and answer_spec.get("kind") in ("int", "bool"):
            expected_value = data.get("expected", {})
            expected_str = None
            if isinstance(expected_value, dict):
                if expected_value.get("kind") == "int":
                    expected_str = str(expected_value.get("value"))
                elif expected_value.get("kind") == "bool":
                    expected_str = str(expected_value.get("value")).lower()
            
            if expected_str:
                prompt = data.get("prompt", {})
                # Extract all literals from query using Lark parser
                query_text = prompt.get("query", "")
                query_literals = _extract_literals_from_query(query_text)
                if expected_str in query_literals:
                    raise ValidationError("T9", f"Expected value {expected_str} appears as literal in query: {query_text}")
                
                # Check against public examples - extract literals from each
                for example in prompt.get("public_examples", []):
                    example_literals = _extract_literals_from_query(example)
                    if expected_str in example_literals:
                        raise ValidationError("T9", f"Expected value {expected_str} appears as literal in public example: {example}")
    
    rules_passed.append(ValidationRule("T9", "Non-triviality check"))
    
    # T10: chance_floor_ppm is at most 100000 [IMPLEMENTED]
    # Must be a non-negative integer <= 100000, or None
    def _validate_chance_floor(value: Any) -> None:
        """Validate chance_floor_ppm value."""
        # None is allowed
        if value is None:
            return
        # Reject booleans (bool is subclass of int in Python)
        if type(value) is bool:
            raise ValidationError("T10", f"chance_floor_ppm must be integer, got bool")
        # Must be an int (not float, not bool subclass)
        if type(value) is not int:
            raise ValidationError("T10", f"chance_floor_ppm must be integer, got {type(value).__name__}")
        # Must be non-negative
        if value < 0:
            raise ValidationError("T10", f"chance_floor_ppm must be >= 0, got {value}")
        # Must be <= 100000
        if value > 100000:
            raise ValidationError("T10", f"chance_floor_ppm must be <= 100000, got {value}")
    
    if isinstance(task, TaskRecord):
        _validate_chance_floor(task.answer_spec.chance_floor_ppm)
    else:
        answer_spec = data.get("answer_spec", {})
        _validate_chance_floor(answer_spec.get("chance_floor_ppm"))
    
    rules_passed.append(ValidationRule("T10", "Chance floor limit"))
    
    # T11: Oracle envelope (call depth <= 40)
    # (Deferred - requires runtime profiling)
    rules_passed.append(ValidationRule("T11", "Oracle envelope (deferred)"))
    
    # T12: Leakage lint
    # (Deferred - requires prompt construction)
    rules_passed.append(ValidationRule("T12", "Leakage lint (deferred)"))
    
    # T13: Identifiability (INF)
    # (Deferred - requires surface profile)
    rules_passed.append(ValidationRule("T13", "Identifiability (deferred)"))
    
    # T14: must_define consistency
    # (Deferred - requires reference solution)
    rules_passed.append(ValidationRule("T14", "must_define consistency (deferred)"))
    
    # T15: limits within blueprint caps
    # (Deferred - requires blueprint)
    rules_passed.append(ValidationRule("T15", "Limits within bounds (deferred)"))
    
    return rules_passed


# Task-set validation rules TS1-TS4
def validate_task_set(task_set: TaskSetRecord | dict[str, Any]) -> list[ValidationRule]:
    """
    Validate a task-set record against rules TS1-TS4.
    
    TS1: Every environment instantiates every blueprint slot.
    TS2: Every task's environment belongs to the set.
    TS3: Held-out environments share no environment_id with the dev split.
    TS4: Every pair has a control and at least one treatment, all in the set.
    
    Args:
        task_set: TaskSetRecord or dict with all required fields
        
    Returns:
        List of validation rules that passed
        
    Raises:
        ValidationError: If any rule fails
    """
    rules_passed = []
    
    # TS1: Every environment instantiates every blueprint slot
    # (Deferred - requires blueprint validation)
    rules_passed.append(ValidationRule("TS1", "Environment slot instantiation (deferred)"))
    
    # TS2: Every task's environment belongs to the set
    if isinstance(task_set, TaskSetRecord):
        task_set_env_ids = {e.environment_id for e in task_set.environment_assignments}
        
        for assignment in task_set.task_assignments:
            if assignment.environment_id not in task_set_env_ids:
                raise ValidationError("TS2", f"Task environment {assignment.environment_id} not in set")
    
    rules_passed.append(ValidationRule("TS2", "Task environments in set"))
    
    # TS3: Held-out environments share no environment_id with dev split
    if isinstance(task_set, TaskSetRecord):
        dev_envs = {e.environment_id for e in task_set.environment_assignments if e.split == "dev"}
        heldout_envs = {e.environment_id for e in task_set.environment_assignments if e.split == "heldout"}
        
        overlap = dev_envs & heldout_envs
        if overlap:
            raise ValidationError("TS3", f"Environment IDs in both dev and heldout: {overlap}")
    
    rules_passed.append(ValidationRule("TS3", "Dev/heldout separation"))
    
    # TS4: Every pair has a control and at least one treatment
    # (Deferred - requires pair validation)
    rules_passed.append(ValidationRule("TS4", "Pair control/treatment (deferred)"))
    
    return rules_passed
