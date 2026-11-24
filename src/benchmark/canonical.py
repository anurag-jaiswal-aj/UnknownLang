"""Strict canonical JSON and SHA-256 helpers for Wave 2 identities."""
from __future__ import annotations

import hashlib
import json
from typing import Any

JsonValue = None | bool | int | str | list["JsonValue"] | dict[str, "JsonValue"]


def _validate(value: Any, path: str = "$", *, object_key: bool = False) -> JsonValue:
    if value is None or type(value) is bool or type(value) is int or type(value) is str:
        return value
    if isinstance(value, float):
        raise TypeError(f"Floats are not permitted in canonical identity data at {path}")
    if isinstance(value, (list, tuple)):
        if isinstance(value, tuple):
            raise TypeError(f"Tuples are not permitted in canonical identity data at {path}")
        return [_validate(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if isinstance(value, dict):
        result: dict[str, JsonValue] = {}
        for key, item in value.items():
            if type(key) is not str:
                raise TypeError(f"Object keys must be strings at {path}")
            result[key] = _validate(item, f"{path}.{key}")
        return result
    raise TypeError(f"Unsupported canonical identity value at {path}: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    """Serialize only the strict Wave 2 JSON value domain."""
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
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
