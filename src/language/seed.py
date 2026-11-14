"""Language generation seed model with validation and canonical serialization."""

import json
from dataclasses import dataclass
from typing import Any


# Valid syntax styles for language generation
VALID_SYNTAX_STYLES = frozenset({"lisp", "c-like", "pythonic", "ruby-like", "javascript-like"})

# Valid semantic dimension configurations
VALID_SEMANTICS = {
    "arithmetic": frozenset({"wraparound", "saturating", "error-on-overflow"}),
    "short_circuit": frozenset({True, False}),
}

# Minimum and maximum difficulty values
MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 5


class ValidationError(Exception):
    """Raised when seed validation fails."""
    pass


@dataclass(frozen=True)
class LanguageSeed:
    """
    Immutable, validated representation of a language generation seed.
    
    All fields are validated at construction time. Invalid inputs raise
    ValidationError with descriptive messages.
    
    Features are normalized to an immutable tuple during construction,
    ensuring internal immutability regardless of input type.
    """
    name: str
    syntax_style: str
    features: tuple[str, ...]
    difficulty: int
    arithmetic: str
    short_circuit: bool
    
    def __post_init__(self) -> None:
        """Normalize and validate seed fields after initialization."""
        # Validate first, then normalize
        # Validate name
        if not self.name or not isinstance(self.name, str):
            raise ValidationError("name must be a non-empty string")
        if len(self.name.strip()) == 0:
            raise ValidationError("name cannot be whitespace-only")
        
        # Validate syntax_style
        if self.syntax_style not in VALID_SYNTAX_STYLES:
            raise ValidationError(
                f"Invalid syntax_style '{self.syntax_style}'. "
                f"Must be one of: {sorted(VALID_SYNTAX_STYLES)}"
            )
        
        # Validate features
        if not isinstance(self.features, (list, tuple)):
            raise ValidationError("features must be a list or tuple")
        if len(self.features) == 0:
            raise ValidationError("features must contain at least one feature")
        for feature in self.features:
            if not isinstance(feature, str) or len(feature.strip()) == 0:
                raise ValidationError("Each feature must be a non-empty string")
        
        # Validate difficulty
        if not isinstance(self.difficulty, int):
            raise ValidationError("difficulty must be an integer")
        if not (MIN_DIFFICULTY <= self.difficulty <= MAX_DIFFICULTY):
            raise ValidationError(
                f"difficulty must be between {MIN_DIFFICULTY} and {MAX_DIFFICULTY} (got {self.difficulty})"
            )
        
        # Validate arithmetic
        if self.arithmetic not in VALID_SEMANTICS["arithmetic"]:
            raise ValidationError(
                f"Invalid arithmetic '{self.arithmetic}'. "
                f"Must be one of: {sorted(VALID_SEMANTICS['arithmetic'])}"
            )
        
        # Validate short_circuit
        if self.short_circuit not in VALID_SEMANTICS["short_circuit"]:
            raise ValidationError(
                f"Invalid short_circuit '{self.short_circuit}'. "
                f"Must be one of: {sorted(VALID_SEMANTICS['short_circuit'])}"
            )
        
        # Normalize features to sorted tuple for determinism (after validation)
        object.__setattr__(self, 'features', tuple(sorted(self.features)))
    
    def to_dict(self) -> dict[str, Any]:
        """Return seed as a dictionary with sorted keys for canonical serialization."""
        # Features are unordered semantically, so sort for determinism
        return {
            "name": self.name,
            "syntax_style": self.syntax_style,
            "features": sorted(self.features),  # Sort for determinism (unordered set)
            "difficulty": self.difficulty,
            "arithmetic": self.arithmetic,
            "short_circuit": self.short_circuit,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LanguageSeed":
        """Create a LanguageSeed from a dictionary, validating all fields."""
        required_fields = {"name", "syntax_style", "features", "difficulty", "arithmetic", "short_circuit"}
        missing = required_fields - set(data.keys())
        if missing:
            raise ValidationError(f"Missing required fields: {missing}")
        
        # Validate first, then normalize
        validate_seed(data)
        
        # Normalize features to sorted tuple for determinism
        features = tuple(sorted(data["features"]))
        
        return cls(
            name=data["name"],
            syntax_style=data["syntax_style"],
            features=features,
            difficulty=data["difficulty"],
            arithmetic=data["arithmetic"],
            short_circuit=data["short_circuit"],
        )
    
    def to_canonical_bytes(self, spec_version: str = "1.0.0", algorithm_version: str = "1.0.0") -> bytes:
        """
        Generate canonical bytes for identity calculation.
        
        Rules:
        1. JSON serialization with sorted keys
        2. No timestamps or runtime-specific values
        3. Stable ordering for all collections
        4. Include spec_version and algorithm_version for version-aware identity
        """
        seed_dict = self.to_dict()
        # Exclude generated_at if present (should not be in valid seeds)
        seed_dict.pop("generated_at", None)
        
        payload = {
            "seed": seed_dict,
            "spec_version": spec_version,
            "algorithm_version": algorithm_version,
        }
        
        # Use sorted keys and consistent formatting for determinism
        json_str = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return json_str.encode("utf-8")


def validate_seed(data: dict[str, Any]) -> None:
    """
    Validate a seed dictionary without creating a LanguageSeed instance.
    
    Raises ValidationError if validation fails. Does not raise if valid.
    
    This is useful for validating raw input before constructing the dataclass.
    """
    required_fields = {"name", "syntax_style", "features", "difficulty", "arithmetic", "short_circuit"}
    missing = required_fields - set(data.keys())
    if missing:
        raise ValidationError(f"Missing required fields: {missing}")
    
    # Validate name
    if not data["name"] or not isinstance(data["name"], str):
        raise ValidationError("name must be a non-empty string")
    if len(data["name"].strip()) == 0:
        raise ValidationError("name cannot be whitespace-only")
    
    # Validate syntax_style
    if data["syntax_style"] not in VALID_SYNTAX_STYLES:
        raise ValidationError(
            f"Invalid syntax_style '{data['syntax_style']}'. "
            f"Must be one of: {sorted(VALID_SYNTAX_STYLES)}"
        )
    
    # Validate features
    if not isinstance(data["features"], (list, tuple)):
        raise ValidationError("features must be a list or tuple")
    if len(data["features"]) == 0:
        raise ValidationError("features must contain at least one feature")
    for feature in data["features"]:
        if not isinstance(feature, str) or len(feature.strip()) == 0:
            raise ValidationError("Each feature must be a non-empty string")
    
    # Validate difficulty
    if not isinstance(data["difficulty"], int):
        raise ValidationError("difficulty must be an integer")
    if not (MIN_DIFFICULTY <= data["difficulty"] <= MAX_DIFFICULTY):
        raise ValidationError(
            f"difficulty must be between {MIN_DIFFICULTY} and {MAX_DIFFICULTY} (got {data['difficulty']})"
        )
    
    # Validate arithmetic
    if data["arithmetic"] not in VALID_SEMANTICS["arithmetic"]:
        raise ValidationError(
            f"Invalid arithmetic '{data['arithmetic']}'. "
            f"Must be one of: {sorted(VALID_SEMANTICS['arithmetic'])}"
        )
    
    # Validate short_circuit
    if data["short_circuit"] not in VALID_SEMANTICS["short_circuit"]:
        raise ValidationError(
            f"Invalid short_circuit '{data['short_circuit']}'. "
            f"Must be one of: {sorted(VALID_SEMANTICS['short_circuit'])}"
        )
