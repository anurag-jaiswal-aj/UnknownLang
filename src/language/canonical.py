"""Canonical serialization for deterministic language identity."""

import json
from typing import Any, Optional


def canonicalize_value(value: Any) -> Any:
    """
    Recursively canonicalize a value for consistent serialization.
    
    Rules:
    - Strings: Return as-is
    - Numbers: Return as-is
    - Booleans: Return as-is
    - None: Return as-is
    - Lists: Preserve order (ordered sequence)
    - Tuples: Preserve order (ordered sequence)
    - Dicts: Sort keys deterministically, canonicalize each value
    - Other types: Convert to string representation
    
    Args:
        value: Value to canonicalize
    
    Returns:
        Canonicalized value suitable for JSON serialization
    """
    if value is None:
        return None
    elif isinstance(value, bool):
        return value
    elif isinstance(value, (int, float)):
        return value
    elif isinstance(value, str):
        return value
    elif isinstance(value, (list, tuple)):
        # Preserve order for ordered sequences (lists and tuples)
        # Only sort within the container if it's a dict
        return [canonicalize_value(item) for item in value]
    elif isinstance(value, dict):
        # Sort keys for determinism, then canonicalize each value
        return {k: canonicalize_value(value[k]) for k in sorted(value.keys())}
    else:
        # Fallback: convert to string representation
        return str(value)


def canonical_json(obj: Any, indent: Optional[int] = None) -> str:
    """
    Generate canonical JSON string from an object.
    
    Rules:
    1. Keys are sorted alphabetically
    2. No whitespace unless indent > 0
    3. No trailing newlines
    4. None values are preserved
    5. All collections are sorted for determinism
    
    Args:
        obj: Object to serialize
        indent: Indentation level for pretty-printing (None for compact)
    
    Returns:
        Canonical JSON string
    """
    canonical_obj = canonicalize_value(obj)
    if indent is not None:
        return json.dumps(canonical_obj, sort_keys=True, indent=indent)
    return json.dumps(canonical_obj, sort_keys=True, separators=(",", ":"))


def canonical_bytes(obj: Any) -> bytes:
    """
    Generate canonical UTF-8 bytes from an object.
    
    Args:
        obj: Object to serialize
    
    Returns:
        UTF-8 encoded canonical bytes
    """
    return canonical_json(obj).encode("utf-8")
