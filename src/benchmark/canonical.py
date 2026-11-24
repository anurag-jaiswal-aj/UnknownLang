"""Strict canonical JSON and SHA-256 helpers for Wave 2 identities."""
from __future__ import annotations

import hashlib
import json
from typing import Any

JsonValue = None | bool | int | str | list["JsonValue"] | dict[str, "JsonValue"]


# Maximum nesting depth for canonical structures
MAX_NESTING_DEPTH = 10
# Maximum collection size
MAX_COLLECTION_SIZE = 1000
# Maximum string length
MAX_STRING_LENGTH = 65_536


def _validate(value: Any, path: str = "$", *, object_key: bool = False, depth: int = 0) -> JsonValue:
    if depth > MAX_NESTING_DEPTH:
        raise TypeError(
            f"Exceeds maximum nesting depth of {MAX_NESTING_DEPTH} at {path}"
        )
    if value is None or type(value) is bool or type(value) is int or type(value) is str:
        return value
    if isinstance(value, float):
        raise TypeError(f"Floats are not permitted in canonical identity data at {path}")
    if isinstance(value, (list, tuple)):
        if isinstance(value, tuple):
            raise TypeError(f"Tuples are not permitted in canonical identity data at {path}")
        if len(value) > MAX_COLLECTION_SIZE:
            raise TypeError(
                f"List exceeds maximum size of {MAX_COLLECTION_SIZE} at {path}"
            )
        # Check string length of each item before recursive validation
        for index, item in enumerate(value):
            if isinstance(item, str) and len(item) > MAX_STRING_LENGTH:
                raise TypeError(
                    f"String at {path}[{index}] exceeds maximum length of {MAX_STRING_LENGTH}"
                )
        return [
            _validate(item, f"{path}[{index}]", depth=depth + 1)
            for index, item in enumerate(value)
        ]
    if isinstance(value, dict):
        if len(value) > MAX_COLLECTION_SIZE:
            raise TypeError(
                f"Object exceeds maximum size of {MAX_COLLECTION_SIZE} at {path}"
            )
        result: dict[str, JsonValue] = {}
        for key, item in value.items():
            if type(key) is not str:
                raise TypeError(f"Object keys must be strings at {path}")
            if len(key) > MAX_STRING_LENGTH:
                raise TypeError(f"Object key exceeds maximum length of {MAX_STRING_LENGTH} at {path}")
            if isinstance(item, str) and len(item) > MAX_STRING_LENGTH:
                raise TypeError(f"String value at {path}.{key} exceeds maximum length of {MAX_STRING_LENGTH}")
            result[key] = _validate(item, f"{path}.{key}", depth=depth + 1)
        return result
    raise TypeError(f"Unsupported canonical identity value at {path}: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    """Serialize only the strict Wave 2 JSON value domain.

    Enforces:
    - Maximum nesting depth of {MAX_NESTING_DEPTH}
    - Maximum collection size of {MAX_COLLECTION_SIZE}
    - Maximum string length of {MAX_STRING_LENGTH}
    - Strict types (no floats, no tuples)
    """
    validated = _validate(value)
    return json.dumps(
        validated,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def canonical_bytes(value: Any) -> bytes:
    return canonical_json(value).encode("utf-8")


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_text(text: str) -> str:
    if type(text) is not str:
        raise TypeError("sha256_text requires a string")
    if len(text) > MAX_STRING_LENGTH:
        raise TypeError(f"String exceeds maximum length of {MAX_STRING_LENGTH}")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
