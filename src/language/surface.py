"""Deterministic surface-to-canonical translation for benchmark programs.

The translator is deliberately lexical, not a second parser. It treats every identifier as one
complete token, so names beginning with ``if`` or ``def`` cannot be split by Lark's contextual lexer.
It has no evaluator, host I/O, dynamic import, or filesystem access.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Literal

from .semantics import BUILTIN_OPERATIONS

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_DIGITS = re.compile(r"-?[0-9]+")


class SurfaceTranslationError(ValueError):
    """Raised when surface source cannot be tokenized or a profile is invalid."""


# Maximum surface profile mappings per category
MAX_MAPPINGS_PER_CATEGORY = 100
# Maximum length of mapping keys and targets
MAX_MAPPING_KEY_LENGTH = 64
MAX_MAPPING_TARGET_LENGTH = 64

# Maximum source text length in UTF-8 bytes
# 64KB is more than sufficient for any benchmark program
MAX_SOURCE_LENGTH = 65_536

# Maximum string length for surface profile mappings
MAX_STRING_LENGTH = 65_536


@dataclass(frozen=True)
class SurfaceProfile:
    """Immutable exact-token mappings for one benchmark surface."""

    keywords: Mapping[str, Literal["def", "if"]]
    operators: Mapping[str, str]
    literals: Mapping[str, Literal["true", "false"]]
    profile_schema_version: int = 1

    def validate(self) -> None:
        """Validate surface profile structure."""
        if type(self.profile_schema_version) is not int or self.profile_schema_version != 1:
            raise SurfaceTranslationError("Unsupported surface profile schema version")
        names: list[str] = []
        for category, mapping in (
            ("keywords", self.keywords),
            ("operators", self.operators),
            ("literals", self.literals),
        ):
            if len(mapping) > MAX_MAPPINGS_PER_CATEGORY:
                raise SurfaceTranslationError(
                    f"{category} exceeds maximum of {MAX_MAPPINGS_PER_CATEGORY} mappings"
                )
            for name, target in mapping.items():
                if not isinstance(name, str) or _IDENTIFIER.fullmatch(name) is None:
                    raise SurfaceTranslationError(f"Invalid {category} surface name: {name!r}")
                if name in names:
                    raise SurfaceTranslationError(f"Duplicate surface name: {name}")
                names.append(name)
                if category == "keywords" and target not in {"def", "if"}:
                    raise SurfaceTranslationError(f"Invalid keyword mapping: {target!r}")
                if category == "literals" and target not in {"true", "false"}:
                    raise SurfaceTranslationError(f"Invalid literal mapping: {target!r}")
                if category == "operators" and target not in BUILTIN_OPERATIONS - {"if"}:
                    raise SurfaceTranslationError(f"Invalid operator mapping: {target!r}")

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "SurfaceProfile":
        # Validate before constructing to catch issues early
        if type(value.get("profile_schema_version")) is not int:
            raise SurfaceTranslationError("profile_schema_version must be an integer")
        if value["profile_schema_version"] != 1:
            raise SurfaceTranslationError("Unsupported profile schema version")
        for category in ("keywords", "operators", "literals"):
            mapping = value.get(category, {})
            if not isinstance(mapping, dict):
                raise SurfaceTranslationError(f"{category} must be a dictionary")
            if len(mapping) > MAX_MAPPINGS_PER_CATEGORY:
                raise SurfaceTranslationError(
                    f"{category} exceeds maximum of {MAX_MAPPINGS_PER_CATEGORY} mappings"
                )
            for name, target in mapping.items():
                if not isinstance(name, str):
                    raise SurfaceTranslationError(f"{category} key must be a string: {name!r}")
                if len(name) > MAX_MAPPING_KEY_LENGTH:
                    raise SurfaceTranslationError(
                        f"{category} key exceeds maximum length of {MAX_MAPPING_KEY_LENGTH}: {name!r}"
                    )
                if not isinstance(target, str):
                    raise SurfaceTranslationError(f"{category} target must be a string: {target!r}")
                if len(target) > MAX_MAPPING_TARGET_LENGTH:
                    raise SurfaceTranslationError(
                        f"{category} target exceeds maximum length of {MAX_MAPPING_TARGET_LENGTH}: {target!r}"
                    )
                # Enforce MAX_STRING_LENGTH on all mapping strings (65536 bytes UTF-8)
                if len(name.encode("utf-8")) > MAX_STRING_LENGTH:
                    raise SurfaceTranslationError(
                        f"{category} key exceeds maximum UTF-8 byte length of {MAX_STRING_LENGTH}: {name!r}"
                    )
                if len(target.encode("utf-8")) > MAX_STRING_LENGTH:
                    raise SurfaceTranslationError(
                        f"{category} target exceeds maximum UTF-8 byte length of {MAX_STRING_LENGTH}: {target!r}"
                    )
        profile = cls(
            keywords=dict(value.get("keywords", {})),  # type: ignore[arg-type]
            operators=dict(value.get("operators", {})),  # type: ignore[arg-type]
            literals=dict(value.get("literals", {})),  # type: ignore[arg-type]
            profile_schema_version=value.get("profile_schema_version", 1),  # type: ignore[arg-type]
        )
        profile.validate()
        return profile


@dataclass(frozen=True)
class TranslationResult:
    """Canonical source and the source-to-generated-name mapping."""

    canonical_text: str
    name_map: dict[str, str]


# Maximum source text length in UTF-8 bytes
# 64KB is more than sufficient for any benchmark program
# This constant is referenced in MAX_SOURCE_LENGTH_BYTES (above) for consistency
MAX_SOURCE_LENGTH = 65_536  # Deprecated: use MAX_SOURCE_LENGTH_BYTES


def _tokenize(source: str) -> list[str]:
    """Tokenize surface source text into canonical tokens.

    Validates source length before processing to prevent DoS attacks.
    Uses UTF-8 byte length for accurate size limits.

    Raises:
        SurfaceTranslationError: If source exceeds maximum length in bytes
    """
    source_bytes = len(source.encode("utf-8"))
    if source_bytes > MAX_SOURCE_LENGTH:
        raise SurfaceTranslationError(
            f"Source text exceeds maximum length of {MAX_SOURCE_LENGTH} bytes "
            f"({source_bytes} bytes, {len(source)} characters)"
        )

    tokens: list[str] = []
    position = 0
    while position < len(source):
        if source[position].isspace():
            position += 1
            continue
        char = source[position]
        if char in "()":
            tokens.append(char)
            position += 1
            continue
        digit_match = _DIGITS.match(source, position)
        if digit_match is not None:
            tokens.append(digit_match.group(0))
            position = digit_match.end()
            continue
        identifier_match = _IDENTIFIER.match(source, position)
        if identifier_match is not None:
            tokens.append(identifier_match.group(0))
            position = identifier_match.end()
            continue
        raise SurfaceTranslationError(f"Unsupported surface character at offset {position}")
    return tokens


def to_canonical(source: str, profile: SurfaceProfile | Mapping[str, object]) -> TranslationResult:
    """Translate exact surface tokens to the frozen canonical Lisp grammar.

    Validates source length (UTF-8 bytes) before tokenization and profile structure before construction.

    Raises:
        SurfaceTranslationError: If source exceeds maximum length or profile is invalid
    """
    if not isinstance(source, str):
        raise SurfaceTranslationError("Surface source must be a string")
    if not isinstance(profile, SurfaceProfile):
        profile = SurfaceProfile.from_dict(profile)
    profile.validate()
    table: dict[str, str] = {}
    table.update(profile.keywords)
    table.update(profile.operators)
    table.update(profile.literals)
    tokens = _tokenize(source)
    source_identifiers = {
        token for token in tokens if _IDENTIFIER.fullmatch(token) and token not in table
    }
    name_map: dict[str, str] = {}
    used_generated = set(table) | set(table.values()) | source_identifiers
    next_number = 1
    translated: list[str] = []
    for token in tokens:
        if token in {"(", ")"} or _DIGITS.fullmatch(token):
            translated.append(token)
            continue
        if token in table:
            translated.append(table[token])
            continue
        if token not in name_map:
            while f"_u{next_number}" in used_generated:
                next_number += 1
            name_map[token] = f"_u{next_number}"
            used_generated.add(name_map[token])
            next_number += 1
        translated.append(name_map[token])
    return TranslationResult(
        " ".join(translated).replace("( ", "(").replace(" )", ")"),
        name_map,
    )
