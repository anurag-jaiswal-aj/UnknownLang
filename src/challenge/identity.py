"""Task and task-set identity calculation using SHA-256."""

from __future__ import annotations

from typing import Any

from src.benchmark.canonical import canonical_json, sha256_hex

from .types import TaskRecord, TaskSetRecord, TASK_SCHEMA_VERSION, TASK_SET_SCHEMA_VERSION


def _convert_tuples(obj: Any) -> Any:
    """Recursively convert tuples to lists for canonical JSON."""
    if isinstance(obj, tuple):
        return [_convert_tuples(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: _convert_tuples(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_tuples(item) for item in obj]
    else:
        return obj


def compute_task_id(task: TaskRecord | dict[str, Any]) -> str:
    """
    Compute deterministic task identity from task record.
    
    The task_id is computed as SHA256 of the canonical task record
    EXCLUDING: task_id, verification, provenance, notes
    
    The same task data always produces the same identity.
    Changing any included field changes the identity.
    Excluded metadata fields do not affect the identity.
    
    Args:
        task: TaskRecord or dict with all required fields
        
    Returns:
        69-character hexadecimal task identifier prefixed with "task_"
        (task_ + 64 hex chars = full SHA-256 digest for cryptographic certainty)
        
    Raises:
        ValueError: If task is not valid or canonical serialization fails
    """
    if isinstance(task, TaskRecord):
        data = task.to_canonical_dict()
    else:
        # Convert tuples to lists for canonical JSON
        # Exclude task_id, verification, provenance, notes from identity calculation
        data = _convert_tuples(task.copy())
        data.pop("task_id", None)
        data.pop("verification", None)
        data.pop("provenance", None)
        data.pop("notes", None)
    
    # Compute hash of canonical JSON
    canonical_bytes = canonical_json(data)
    hash_digest = sha256_hex(canonical_bytes)
    
    return f"task_{hash_digest}"


def verify_task_id_determinism(task: TaskRecord, iterations: int = 10) -> bool:
    """
    Verify that the same task produces identical IDs across multiple calls.
    
    Used for testing and validation purposes.
    
    Args:
        task: TaskRecord instance
        iterations: Number of times to verify (default: 10)
        
    Returns:
        True if all iterations produce identical identity
    """
    identity = compute_task_id(task)
    for _ in range(iterations - 1):
        if compute_task_id(task) != identity:
            return False
    return True


def compute_task_set_id(task_set: TaskSetRecord | dict[str, Any]) -> str:
    """
    Compute deterministic task-set identity from task-set record.
    
    The task_set_id is computed as SHA256 of the canonical task-set record
    including: schema_version, family_version, blueprint, sorted assignments,
    sorted task_ids, sorted pair_groups
    
    The same task-set data always produces the same identity.
    Changing any included field changes the identity.
    
    Args:
        task_set: TaskSetRecord or dict with all required fields
        
    Returns:
        69-character hexadecimal task-set identifier prefixed with "tset_"
        
    Raises:
        ValueError: If task_set is not valid or canonical serialization fails
    """
    if isinstance(task_set, TaskSetRecord):
        data = task_set.to_canonical_dict()
    else:
        # Convert tuples to lists for canonical JSON
        data = _convert_tuples(task_set.copy())
    
    # Compute hash of canonical JSON
    canonical_bytes = canonical_json(data)
    hash_digest = sha256_hex(canonical_bytes)
    
    return f"tset_{hash_digest}"


def verify_task_set_id_determinism(task_set: TaskSetRecord, iterations: int = 10) -> bool:
    """
    Verify that the same task-set produces identical IDs across multiple calls.
    
    Used for testing and validation purposes.
    
    Args:
        task_set: TaskSetRecord instance
        iterations: Number of times to verify (default: 10)
        
    Returns:
        True if all iterations produce identical identity
    """
    identity = compute_task_set_id(task_set)
    for _ in range(iterations - 1):
        if compute_task_set_id(task_set) != identity:
            return False
    return True


def verify_identity_excludes_fields(task: TaskRecord) -> bool:
    """
    Verify that excluded fields do not affect task identity.
    
    The following fields must be excluded from task_id computation:
    - task_id (self-reference)
    - verification
    - provenance
    - notes
    
    Args:
        task: TaskRecord instance
        
    Returns:
        True if modifying excluded fields produces identical identity
    """
    original_id = compute_task_id(task)
    
    # Create modified copies with different excluded field values
    if isinstance(task, TaskRecord):
        # Test with different verification
        modified = task.__class__(
            **{
                **task.__dict__,
                "verification": None,  # Was not None
            }
        )
        if compute_task_id(modified) != original_id:
            return False
        
        # Test with different provenance
        modified = task.__class__(
            **{
                **task.__dict__,
                "provenance": None,  # Was not None
            }
        )
        if compute_task_id(modified) != original_id:
            return False
            
        # Test with different notes
        modified = task.__class__(
            **{
                **task.__dict__,
                "notes": None,  # Was not None
            }
        )
        if compute_task_id(modified) != original_id:
            return False
    
    return True
