"""Semantic operation registry for the UnknownLang MVP.

This module provides a declarative semantic registry that describes
the semantics of built-in operations without implementing execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from .seed import LanguageSeed, ValidationError


# Valid semantic dimensions and their allowed values
VALID_ARITHMETIC_MODES: Final[frozenset[str]] = frozenset(
    {"wraparound", "saturating", "error-on-overflow"}
)
VALID_SHORT_CIRCUIT_MODES: Final[frozenset[bool]] = frozenset({True, False})

# Fixed MVP semantic metadata (requirements.md Req. 6 criterion 3 requires these fields in
# the specification's semantics object; Req. 5 criterion 6 and design.md "Deferred Semantic
# Dimensions" defer them as *configurable* dimensions). They are therefore recorded, not
# configurable: each has exactly one supported value, matching the evaluators' behavior.
FIXED_EVALUATION_ORDER: Final[str] = "left-to-right"
FIXED_SCOPING: Final[str] = "lexical"
FIXED_TYPE_COERCION: Final[str] = "strict"

# Supported built-in operations (frozen set of operation names)
BUILTIN_OPERATIONS: Final[frozenset[str]] = frozenset(
    {"add", "sub", "mul", "div", "mod", "and", "or", "not", "eq", "if"}
)


@dataclass(frozen=True)
class OperationInfo:
    """Immutable metadata describing a built-in operation's semantics.

    This class provides declarative information about operations,
    including arity, type signatures, and semantic modes.
    """

    name: str
    arity: int
    arg_types: tuple[str, ...]
    return_type: str
    semantic_mode: str


@dataclass(frozen=True)
class SemanticSpec:
    """Immutable specification of a language's semantic configuration.

    This class encapsulates all semantic information derived from a
    LanguageSeed, including arithmetic mode, short-circuit behavior,
    and operation metadata.
    """

    arithmetic_mode: str
    short_circuit_mode: bool
    operations: dict[str, OperationInfo]
    # Fixed MVP metadata. Not configurable: any value other than the fixed one is rejected.
    evaluation_order: str = FIXED_EVALUATION_ORDER
    scoping: str = FIXED_SCOPING
    type_coercion: str = FIXED_TYPE_COERCION

    def __post_init__(self) -> None:
        """Validate semantic spec fields after initialization."""
        for field_name, fixed in (
            ("evaluation_order", FIXED_EVALUATION_ORDER),
            ("scoping", FIXED_SCOPING),
            ("type_coercion", FIXED_TYPE_COERCION),
        ):
            value = getattr(self, field_name)
            if value != fixed:
                raise ValidationError(
                    f"Invalid {field_name} '{value}'. "
                    f"The only supported value in the MVP is '{fixed}'"
                )
        if self.arithmetic_mode not in VALID_ARITHMETIC_MODES:
            raise ValidationError(
                f"Invalid arithmetic_mode '{self.arithmetic_mode}'. "
                f"Must be one of: {sorted(VALID_ARITHMETIC_MODES)}"
            )

        if self.short_circuit_mode not in VALID_SHORT_CIRCUIT_MODES:
            raise ValidationError(
                f"Invalid short_circuit_mode '{self.short_circuit_mode}'. "
                f"Must be one of: {sorted(VALID_SHORT_CIRCUIT_MODES)}"
            )

        # Validate all operations have valid semantic_mode values
        for op_name, op_info in self.operations.items():
            if op_info.semantic_mode not in VALID_ARITHMETIC_MODES and op_name not in {
                "and",
                "or",
                "not",
                "eq",
                "if",
            }:
                raise ValidationError(
                    f"Invalid semantic_mode '{op_info.semantic_mode}' for operation '{op_name}'. "
                    f"Must be one of: {sorted(VALID_ARITHMETIC_MODES)}"
                )


class SemanticRegistry:
    """Declarative registry of built-in operations and their semantics.

    This class provides methods to validate LanguageSeed instances
    and build SemanticSpec instances describing the semantics of
    built-in operations for a given language configuration.

    NOTE: This registry describes semantics declaratively. It does
    not execute code or evaluate expressions (that's Wave 1C).
    """

    def __init__(self) -> None:
        """Initialize the semantic registry with built-in operation metadata."""
        self._builtin_operations: Final[dict[str, OperationInfo]] = self._build_builtin_operations()

    def _build_builtin_operations(self) -> dict[str, OperationInfo]:
        """Build the built-in operation metadata dictionary.

        This method defines the semantics of all built-in operations
        according to the frozen contract.

        Returns:
            Dictionary mapping operation names to their OperationInfo.
        """
        operations: dict[str, OperationInfo] = {}

        # Arithmetic operations (int -> int)
        # Note: arithmetic_mode will be filled in dynamically based on seed
        operations["add"] = OperationInfo(
            name="add",
            arity=2,
            arg_types=("int", "int"),
            return_type="int",
            semantic_mode="wraparound",  # placeholder, replaced during spec building
        )
        operations["sub"] = OperationInfo(
            name="sub",
            arity=2,
            arg_types=("int", "int"),
            return_type="int",
            semantic_mode="wraparound",  # placeholder
        )
        operations["mul"] = OperationInfo(
            name="mul",
            arity=2,
            arg_types=("int", "int"),
            return_type="int",
            semantic_mode="wraparound",  # placeholder
        )
        operations["div"] = OperationInfo(
            name="div",
            arity=2,
            arg_types=("int", "int"),
            return_type="int",
            semantic_mode="error-on-overflow",  # division by zero is an error
        )
        operations["mod"] = OperationInfo(
            name="mod",
            arity=2,
            arg_types=("int", "int"),
            return_type="int",
            semantic_mode="error-on-overflow",  # modulo by zero is an error
        )

        # Boolean operations
        operations["and"] = OperationInfo(
            name="and",
            arity=2,
            arg_types=("bool", "bool"),
            return_type="bool",
            semantic_mode="short-circuit",  # short-circuit mode varies by seed
        )
        operations["or"] = OperationInfo(
            name="or",
            arity=2,
            arg_types=("bool", "bool"),
            return_type="bool",
            semantic_mode="short-circuit",  # short-circuit mode varies by seed
        )
        operations["not"] = OperationInfo(
            name="not",
            arity=1,
            arg_types=("bool",),
            return_type="bool",
            semantic_mode="strict",  # always evaluates argument
        )

        # Equality comparison
        operations["eq"] = OperationInfo(
            name="eq",
            arity=2,
            arg_types=("any", "any"),
            return_type="bool",
            semantic_mode="strict",
        )

        # Conditional expression
        operations["if"] = OperationInfo(
            name="if",
            arity=3,
            arg_types=("bool", "any", "any"),
            return_type="any",
            semantic_mode="short-circuit",  # only evaluates then/else based on condition
        )

        return operations

    def validate_seed(self, seed: LanguageSeed) -> None:
        """Validate that a LanguageSeed is compatible with this registry.

        This method checks that all features and semantic dimensions
        in the seed are supported by this registry.

        Args:
            seed: The LanguageSeed to validate.

        Raises:
            ValidationError: If the seed contains unsupported features
                or semantic values.
        """
        # Check that arithmetic mode is supported
        if seed.arithmetic not in VALID_ARITHMETIC_MODES:
            raise ValidationError(
                f"Unsupported arithmetic mode '{seed.arithmetic}'. "
                f"Supported modes: {sorted(VALID_ARITHMETIC_MODES)}"
            )

        # Check that short_circuit mode is supported
        if seed.short_circuit not in VALID_SHORT_CIRCUIT_MODES:
            raise ValidationError(
                f"Unsupported short_circuit mode '{seed.short_circuit}'. "
                f"Supported modes: {sorted(VALID_SHORT_CIRCUIT_MODES)}"
            )

        # Check that semantic features are supported
        # Other features are allowed for future extension
        semantic_features = frozenset({"arithmetic", "short_circuit", "recursion", "functions"})
        for feature in seed.features:
            if feature in semantic_features:
                # This is a semantic feature, which is supported
                pass
            # Other features are allowed (for future extension or custom features)

    def build_spec(self, seed: LanguageSeed) -> SemanticSpec:
        """Build a SemanticSpec from a validated LanguageSeed.

        This method creates a declarative specification of the
        language's semantics based on the seed's configuration.

        Args:
            seed: A validated LanguageSeed instance.

        Returns:
            A SemanticSpec instance describing the language's semantics.

        Raises:
            ValidationError: If the seed is not valid or compatible.
        """
        # Validate the seed first
        self.validate_seed(seed)

        # Build operation info with semantic modes based on seed
        operations: dict[str, OperationInfo] = {}

        for op_name, op_info in self._builtin_operations.items():
            # Determine the semantic mode for this operation based on seed
            if op_name in {"add", "sub", "mul"}:
                # Binary arithmetic operations use the seed's arithmetic mode
                mode = seed.arithmetic
            elif op_name in {"div", "mod"}:
                # Division and remainder operations use error-on-overflow mode
                # (handles division by zero, modulo by zero, and overflow errors)
                mode = "error-on-overflow"
            elif op_name in {"and", "or"}:
                # Boolean operations use short-circuit mode based on seed
                mode = "short-circuit" if seed.short_circuit else "eager"
            elif op_name == "if":
                # Conditional expression: always short-circuit (lazy) regardless of boolean mode.
                # It evaluates only the selected branch, independent of whether and/or are eager.
                mode = "short-circuit"
            else:
                # Other operations use strict mode
                mode = "strict"

            operations[op_name] = OperationInfo(
                name=op_info.name,
                arity=op_info.arity,
                arg_types=op_info.arg_types,
                return_type=op_info.return_type,
                semantic_mode=mode,
            )

        return SemanticSpec(
            arithmetic_mode=seed.arithmetic,
            short_circuit_mode=seed.short_circuit,
            operations=operations,
            evaluation_order=FIXED_EVALUATION_ORDER,
            scoping=FIXED_SCOPING,
            type_coercion=FIXED_TYPE_COERCION,
        )
