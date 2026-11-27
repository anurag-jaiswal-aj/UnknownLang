"""Deterministic evaluation harness for M2.6.

The harness is a pure function that:
1. Receives a task, resolved environment, and raw response text
2. Extracts the submission (code block or value answer)
3. Validates the submission format
4. Translates surface syntax to canonical syntax
5. Executes through the production runtime with limits
6. Classifies execution and submission failures
7. Compares actual and expected results
8. Returns a structured outcome

This is a pure function: same inputs always produce identical outputs.
"""

from __future__ import annotations

import re
from typing import Any

from src.benchmark.harness.types import AttemptOutcome, FailureCategory
from src.benchmark.harness.watchdog import execute_with_watchdog, classify_watchdog_result
from src.benchmark.canonical import canonical_json, sha256_hex
from src.benchmark.environments import EnvironmentRecord, get_language_spec
from src.language.surface import SurfaceProfile, to_canonical, TranslationResult
from src.challenge.types import TaskRecord, Prompt, AnswerSpec, Evaluation, Test
from src.execution.engine import ExecutionEngine
from src.execution.types import ExecutionResult


# Constants per AM-08 decision register
_MAX_SUBMISSION_BYTES = 4096


def _validate_submission_bytes(answer_text: str) -> bool:
    """Validate submission size in UTF-8 bytes per AM-08.
    
    AM-08 specifies submission size in bytes, not Unicode codepoints.
    Uses len(answer_text.encode('utf-8')) for accurate byte counting.
    """
    return len(answer_text.encode('utf-8')) <= _MAX_SUBMISSION_BYTES


def evaluate(
    task: TaskRecord,
    env: EnvironmentRecord,
    response_text: str,
) -> AttemptOutcome:
    """Evaluate a task with the given environment and model response.
    
    This is a pure function. Given the same task, environment, and response_text,
    it always produces identical outcomes.
    
    M2.6 supports only EVAL, SYN, INF, CTRL (value-answer tasks).
    Program tasks (REC, CONS, ERR) are explicitly rejected.
    
    Args:
        task: Validated task record with expected results
        env: Resolved environment record with valid environment_id
        response_text: Raw model response text
        
    Returns:
        AttemptOutcome with outcome, score, failure_category, detail, diagnostics
        
    Raises:
        ValueError: If task or environment are invalid (not caught at boundary)
    """
    # M2.6 scope check: only value-answer tasks (EVAL, SYN, INF, CTRL)
    if task.answer_spec.type == "program":
        return AttemptOutcome.void(
            failure_category="invalid_submission",
            detail="program_task_unsupported",
            diagnostics={
                "answer_spec_type": task.answer_spec.type,
                "answer_spec_form": getattr(task.answer_spec, "form", None),
            },
        )
    
    # Step S2: Extract answer from response
    extraction_result = _extract_answer(task, response_text)
    if extraction_result is None:
        return AttemptOutcome.void(
            failure_category="extraction_failed",
            detail="no_answer_line",
            diagnostics={"response_length": len(response_text)},
        )
    
    answer_text, answer_spec = extraction_result
    
    # Step S3: Validate submission
    validation_result = _validate_submission(task, answer_text, answer_spec)
    if validation_result is not None:
        return AttemptOutcome.fail(
            failure_category=validation_result["category"],
            detail=validation_result["detail"],
            diagnostics={"submission_length": len(answer_text)},
        )
    
    # Step S4: Translate to canonical
    try:
        canonical_text, name_map = _translate_to_canonical(
            answer_text, env.surface_profile
        )
    except Exception as e:
        return AttemptOutcome.fail(
            failure_category="invalid_submission",
            detail="tokenization",
            diagnostics={"error": str(e)},
        )
    
    # Step S5: Execute through production runtime with watchdog protection
    execution_result = _execute_with_watchdog(
        canonical_text, task, env, name_map
    )
    
    # Step S6: Compare with expected
    return _compare_result(task, execution_result, name_map, env)


def _extract_answer(
    task: TaskRecord, response_text: str
) -> tuple[str, AnswerSpec] | None:
    """Extract answer from response text per AM-08.
    
    For program tasks: last fenced code block, or entire response if no fence.
    For value tasks: last line matching ^ANSWER:[ ]*(.+?)[ ]*$.
    
    Returns None if no answer line found for value tasks.
    """
    answer_spec = task.answer_spec
    
    if answer_spec.type == "program":
        return _extract_program_answer(response_text), answer_spec
    elif answer_spec.type == "value":
        answer_text = _extract_value_answer(response_text)
        # For value tasks, empty extraction means no ANSWER: line was found
        if not answer_text and not re.findall(r'^ANSWER:[ ]', response_text, re.MULTILINE):
            return None
        return answer_text, answer_spec
    
    return None


def _extract_program_answer(response_text: str) -> str:
    """Extract last fenced code block or entire response for program tasks."""
    # Try to find fenced code blocks
    code_block_pattern = r"```(?:\w+)?\n(.*?)\n```"
    matches = re.findall(code_block_pattern, response_text, re.DOTALL)
    
    if matches:
        return matches[-1].strip()
    
    # No fenced block - use entire response
    return response_text.strip()


def _extract_value_answer(response_text: str) -> str:
    """Extract last ANSWER: line for value tasks."""
    answer_pattern = r'^ANSWER:[ ]*(.+?)[ ]*$'
    matches = re.findall(answer_pattern, response_text, re.MULTILINE)
    
    if matches:
        return matches[-1]
    
    return ""


def _validate_submission(
    task: TaskRecord, answer_text: str, answer_spec: AnswerSpec
) -> dict[str, Any] | None:
    """Validate submission format. Returns None if valid, error dict otherwise."""
    # Check submission size in UTF-8 bytes (AM-08)
    if not _validate_submission_bytes(answer_text):
        return {"category": "invalid_submission", "detail": "oversize"}
    
    # Empty submission is invalid
    if not answer_text.strip():
        # For value tasks, empty ANSWER: is invalid_answer; for programs, invalid_submission
        if answer_spec.type == "value":
            return {"category": "invalid_answer", "detail": "empty"}
        else:
            return {"category": "invalid_submission", "detail": "empty"}
    
    # Program-specific validation
    if answer_spec.type == "program":
        # Check for required form elements
        if answer_spec.form == "definitions_only":
            # Validate definitions-only form
            if not _is_definitions_only(answer_text):
                return {"category": "invalid_submission", "detail": "bad_form"}
    
    # Value-specific validation
    elif answer_spec.type == "value":
        # Validate answer format
        if answer_spec.kind == "int":
            try:
                int(answer_text)
            except ValueError:
                return {"category": "invalid_answer", "detail": "unparseable"}
        elif answer_spec.kind == "bool":
            if answer_text.lower() not in ("true", "false"):
                return {"category": "invalid_answer", "detail": "unparseable"}
    
    return None


def _is_definitions_only(text: str) -> bool:
    """Check if text contains only definitions (for definitions_only form)."""
    # For now, this is a simple check
    # A more sophisticated implementation would parse and check
    return True


def _translate_to_canonical(
    surface_text: str, surface_profile: dict[str, Any]
) -> tuple[str, dict[str, str]]:
    """Translate surface text to canonical text with name mapping."""
    # Use the surface profile to create a SurfaceProfile object
    # and perform translation
    profile = SurfaceProfile.from_dict(surface_profile)
    
    # The translator returns TranslationResult with canonical_text and name_map
    result = to_canonical(surface_text, profile)
    
    return result.canonical_text, result.name_map


def _execute_with_watchdog(
    canonical_text: str,
    task: TaskRecord,
    env: EnvironmentRecord,
    name_map: dict[str, str],
) -> ExecutionResult:
    """Execute canonical program through production runtime with watchdog protection.
    
    Uses the trusted-local watchdog for wall-clock timeout enforcement.
    Falls back to direct execution if watchdog is unavailable.
    """
    # Get the LanguageSpec from the environment
    spec = get_language_spec(env)
    
    # Get resource limits from task
    limits = task.evaluation.limits
    max_steps = limits.get("max_steps")
    max_ast_depth = limits.get("max_ast_depth")
    max_call_depth = limits.get("max_call_depth")
    
    # Execute through watchdog
    watchdog_result = execute_with_watchdog(
        canonical_text=canonical_text,
        spec=spec,
        surface_profile=env.surface_profile,
        max_steps=max_steps,
        max_ast_depth=max_ast_depth,
        max_call_depth=max_call_depth,
        timeout_seconds=30.0,  # Default 30-second wall-clock timeout
    )
    
    # Classify watchdog result
    category, detail = classify_watchdog_result(watchdog_result)
    
    if category == "ok":
        # Use the watchdog's execution result
        if watchdog_result.execution_result is not None:
            return watchdog_result.execution_result
        # Fallback to direct execution (shouldn't happen on success)
        engine = ExecutionEngine(
            max_steps=max_steps,
            max_ast_depth=max_ast_depth,
            max_call_depth=max_call_depth,
        )
        return engine.execute(canonical_text, spec, surface_profile=env.surface_profile)
    
    # Watchdog detected a resource limit - return appropriate result
    return ExecutionResult(
        status="step_limit_exceeded" if detail in ("wall_clock", "steps") else "error",
        value=None,
        error_kind="resource" if category == "resource_limit" else None,
        error_message=watchdog_result.error_message or detail,
        error_detail=detail,
    )


def _execute_canonical_program(
    canonical_text: str,
    task: TaskRecord,
    env: EnvironmentRecord,
    name_map: dict[str, str],
) -> ExecutionResult:
    """Execute canonical program through production runtime.
    
    DEPRECATED: Use _execute_with_watchdog instead.
    Kept for backward compatibility during migration.
    """
    # Get the LanguageSpec from the environment
    spec = get_language_spec(env)
    
    # Get resource limits from task
    limits = task.evaluation.limits
    max_steps = limits.get("max_steps")
    max_ast_depth = limits.get("max_ast_depth")
    max_call_depth = limits.get("max_call_depth")
    
    # Get the production engine
    engine = ExecutionEngine(
        max_steps=max_steps,
        max_ast_depth=max_ast_depth,
        max_call_depth=max_call_depth,
    )
    
    # Execute the program
    result = engine.execute(canonical_text, spec, surface_profile=env.surface_profile)
    
    return result


def _compare_result(
    task: TaskRecord, result: ExecutionResult, name_map: dict[str, str], env: EnvironmentRecord
) -> AttemptOutcome:
    """Compare execution result with expected value.
    
    M2.6 only handles value-answer tasks (EVAL, SYN, INF, CTRL).
    Program task support is explicitly unsupported.
    """
    # Type check: should be unreachable since we reject program tasks in evaluate()
    if task.answer_spec.type == "program":
        return AttemptOutcome.void(
            failure_category="harness_fault",
            detail="program_task_not_reachable",
            diagnostics={"answer_spec_type": task.answer_spec.type},
        )
    
    expected = task.expected
    return _compare_value_result(task, result, expected, env)


def _classify_runtime_result(
    result: ExecutionResult,
) -> tuple[FailureCategory, str | None]:
    """Classify runtime result into failure category."""
    status = result.status
    
    if status == "success":
        return "ok", None
    
    # Resource limits
    if status == "step_limit_exceeded":
        return "resource_limit", "steps"
    if status == "recursion_limit_exceeded":
        return "resource_limit", "call_depth"
    if status == "ast_depth_exceeded":
        return "resource_limit", "ast_depth"
    if status == "output_limit_exceeded":
        return "resource_limit", "output"
    
    # Runtime errors
    if status == "error":
        kind = result.error_kind or "syntax"
        detail = result.error_detail or "unclassified"
        
        if kind == "syntax":
            return "syntax_error", detail
        if kind == "name":
            return "name_error", detail
        if kind == "arity":
            return "arity_error", detail
        if kind == "type":
            return "type_error", detail
        if kind == "division_by_zero":
            return "arithmetic_error", detail
        if kind == "overflow":
            return "arithmetic_error", detail
        if kind == "literal_range":
            return "literal_range_error", detail
        if kind == "resource":
            return "resource_limit", detail
        
        return "harness_fault", f"unclassified_result: {detail}"
    
    return "harness_fault", f"unrecognized_status: {status}"


def _compare_value_result(
    task: TaskRecord, result: ExecutionResult, expected: Any, env: EnvironmentRecord
) -> AttemptOutcome:
    """Compare value task result with expected value."""
    category, detail = _classify_runtime_result(result)
    
    if category != "ok":
        # resource_limit and harness_fault are void (no score contribution)
        return AttemptOutcome.void(category, detail) if category in ("resource_limit", "harness_fault") else AttemptOutcome.fail(category, detail)
    
    # Compare values
    result_value = _extract_value(result.value)
    expected_value = _extract_expected_value(expected)
    
    if result_value == expected_value:
        return AttemptOutcome.ok()
    
    return AttemptOutcome.fail(
        failure_category="wrong_answer",
        detail="wrong_value",
        diagnostics={"expected": expected_value, "actual": result_value},
    )


def _extract_value(value: Any) -> dict[str, Any]:
    """Extract value in standard format."""
    if value is None:
        return {"kind": "null"}
    if isinstance(value, bool):
        return {"kind": "bool", "value": value}
    if isinstance(value, int):
        return {"kind": "int", "value": value}
    return {"kind": "other", "value": str(value)}


def _extract_expected_value(expected: Any) -> dict[str, Any]:
    """Extract expected value in standard format.
    
    Handles both the Expected dataclass and serialized dict representations.
    
    Args:
        expected: Either Expected dataclass or serialized dict {kind: str, value: Any}
        
    Returns:
        dict with 'kind' and 'value' keys
        
    Raises:
        ValueError: If expected format is invalid
    """
    # Handle Expected dataclass
    if hasattr(expected, 'value') and isinstance(getattr(expected, 'value', None), dict):
        return expected.value
    
    # Handle serialized dict
    if isinstance(expected, dict):
        # Validate expected format
        if 'kind' not in expected:
            raise ValueError(f"Expected value must have 'kind' field: {expected}")
        return expected
    
    # Invalid format
    raise ValueError(f"Invalid expected value format: {type(expected)} - {expected}")


# NOTE: Program task support (test_suite, program execution) is out of scope for M2.6.
# M2.6 supports only value-answer tasks (EVAL, SYN, INF, CTRL).
# Program task handling functions have been removed to enforce scope boundaries.
