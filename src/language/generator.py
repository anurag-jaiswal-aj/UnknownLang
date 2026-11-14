"""Language generator facade coordinating all language generation components."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .grammar import GrammarBuilder, GrammarSpec
from .identity import compute_language_id
from .semantics import SemanticRegistry, SemanticSpec, OperationInfo
from .serializer import LarkSerializer
from .seed import LanguageSeed, ValidationError


@dataclass(frozen=True)
class LanguageSpec:
    """
    Declarative specification of a generated language.

    This dataclass represents the complete output of the language generation
    process, including grammar, semantics, and metadata.
    """

    version: str
    spec_version: str
    algorithm_version: str
    language_id: str
    seed: LanguageSeed
    grammar: str
    semantics: SemanticSpec
    builtins: dict[str, OperationInfo]


class LanguageGenerator:
    """
    Coordinates all language generation components.

    The generator produces deterministic language specifications from
    validated LanguageSeed inputs. The same seed always produces identical
    artifacts, preserving the full SHA-256 language identity.

    Components used:
    - GrammarBuilder: Builds GrammarSpec from seed
    - LarkSerializer: Serializes GrammarSpec to Lark grammar text
    - SemanticRegistry: Builds SemanticSpec from seed
    """

    def __init__(self) -> None:
        """Initialize the generator with its components."""
        self._semantic_registry = SemanticRegistry()

    def generate(
        self,
        seed: LanguageSeed,
        spec_version: str = "1.0.0",
        algorithm_version: str = "1.0.0",
    ) -> LanguageSpec:
        """
        Generate a complete language specification from a validated seed.

        This method coordinates all generation components to produce a
        deterministic LanguageSpec. The same seed and versions always
        produce identical artifacts.

        Args:
            seed: A validated LanguageSeed instance
            spec_version: Specification version string (default: "1.0.0")
            algorithm_version: Generator algorithm version string (default: "1.0.0")

        Returns:
            A LanguageSpec containing all language artifacts

        Raises:
            ValidationError: If the seed is not valid
            ValueError: If seed.syntax_style is not supported
        """
        # Validate seed compatibility with semantic registry
        self._semantic_registry.validate_seed(seed)

        # Compute language identity (Wave 1A)
        language_id = compute_language_id(seed, spec_version, algorithm_version)

        # Build grammar specification (Wave 1B - GrammarBuilder)
        grammar_builder = GrammarBuilder(seed)
        grammar_spec = grammar_builder.build()

        # Serialize grammar to Lark format (Wave 1B - LarkSerializer)
        lark_serializer = LarkSerializer(grammar_spec)
        grammar_text = lark_serializer.serialize()

        # Build semantic specification (Wave 1B - SemanticRegistry)
        semantic_spec = self._semantic_registry.build_spec(seed)

        # Build builtins dictionary (sorted for determinism)
        builtins = dict(sorted(semantic_spec.operations.items()))

        return LanguageSpec(
            version="1.0.0",
            spec_version=spec_version,
            algorithm_version=algorithm_version,
            language_id=language_id,
            seed=seed,
            grammar=grammar_text,
            semantics=semantic_spec,
            builtins=builtins,
        )

    def validate_grammar(self, grammar_text: str) -> bool:
        """
        Validate that grammar text produces a valid Lark parser.

        Args:
            grammar_text: The Lark grammar text to validate

        Returns:
            True if the grammar is valid and can construct a Lark parser,
            False otherwise.
        """
        return LarkSerializer.validate_grammar_static(grammar_text)

    def detect_conflicts(
        self, spec: LanguageSpec, registry: SemanticRegistry
    ) -> list[str]:
        """
        Detect semantic conflicts between a language spec and a registry.

        This is a stub for future use - currently returns an empty list.

        Args:
            spec: The language specification to check
            registry: The semantic registry to check against

        Returns:
            List of conflict descriptions (empty for now)
        """
        # TODO: Implement conflict detection logic when needed
        return []
