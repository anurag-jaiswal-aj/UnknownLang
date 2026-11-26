"""PromptBuilder and language reference generation for Wave 2.

This module implements the prompt generation contract from benchmark-task-schema.md section 8.
Prompts are derived, not stored. The task stores structured inputs and the builder produces text.

Key components:
- PromptBundle: Dataclass for prompt components
- PromptBuilder: Interface for versioned prompt building
- TemplateRegistry: Registry with versioning for prompt templates
- LanguageReferenceGenerator: Generates language reference from environment record
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol, TypedDict


@dataclass(frozen=True)
class PromptBundle:
    """Complete prompt bundle ready for model consumption."""
    
    system_message: str
    user_message: str
    reference_document: str
    template_id: tuple[str, int]  # (template_id, version)
    environment_id: str
    information_condition: str


class TemplateFunction(Protocol):
    """Protocol for prompt template functions."""
    
    def __call__(
        self,
        public_task: Any,
        environment: dict[str, Any],
        information_condition: str,
    ) -> PromptBundle:
        """Build a prompt from public task and environment data."""
        ...


class TemplateRegistry:
    """Registry for prompt templates with versioning."""
    
    def __init__(self) -> None:
        self._templates: dict[str, dict[int, TemplateFunction]] = {}
        self._default_version: dict[str, int] = {}
    
    def register(
        self,
        template_id: str,
        version: int,
        template_func: TemplateFunction,
        *,  # Make default keyword-only
        default: bool = False,
    ) -> None:
        """Register a prompt template.
        
        Args:
            template_id: Template identifier (e.g., "prompt.answer")
            version: Template version (incremented on any wording change)
            template_func: Function that builds the prompt
            default: If True, sets this as the default version for the template
        """
        if template_id not in self._templates:
            self._templates[template_id] = {}
        
        self._templates[template_id][version] = template_func
        
        if default or template_id not in self._default_version:
            self._default_version[template_id] = version
    
    def get(self, template_id: str, version: int | None = None) -> TemplateFunction:
        """Get a registered template function.
        
        Args:
            template_id: Template identifier
            version: Version to get (uses default if None)
            
        Returns:
            Template function for the requested version
            
        Raises:
            ValueError: If template or version not found
        """
        if template_id not in self._templates:
            raise ValueError(f"Unknown template: {template_id}")
        
        if version is None:
            version = self._default_version[template_id]
        
        if version not in self._templates[template_id]:
            available = sorted(self._templates[template_id].keys())
            raise ValueError(
                f"Template {template_id} version {version} not found. "
                f"Available versions: {available}"
            )
        
        return self._templates[template_id][version]
    
    def get_all_versions(self, template_id: str) -> list[int]:
        """Get all available versions for a template."""
        if template_id not in self._templates:
            return []
        return sorted(self._templates[template_id].keys())
    
    def get_default_version(self, template_id: str) -> int:
        """Get the default version for a template."""
        if template_id not in self._default_version:
            raise ValueError(f"No default version for template: {template_id}")
        return self._default_version[template_id]


# Global template registry
_registry = TemplateRegistry()


def get_registry() -> TemplateRegistry:
    """Get the global template registry."""
    return _registry


# Template registry initialization
def _initialize_registry() -> None:
    """Initialize the template registry with default templates.
    
    Templates are versioned. Changing any wording requires a new version.
    """
    # Register default templates
    # Version 1 templates
    _registry.register(
        "prompt.answer",
        1,
        _build_answer_prompt_v1,
        default=True,
    )
    
    _registry.register(
        "prompt.program",
        1,
        _build_program_prompt_v1,
        default=True,
    )


def _build_answer_prompt_v1(
    public_task: Any,
    environment: dict[str, Any],
    information_condition: str,
) -> PromptBundle:
    """Build answer prompt (value tasks) version 1.
    
    Args:
        public_task: PublicTask object with task data
        environment: Environment record as dict
        information_condition: FULL_DOC, SIGNATURES_ONLY, EXAMPLES_ONLY, etc.
        
    Returns:
        PromptBundle with system and user messages
    """
    # Build the prompt text based on information condition
    sections: list[str] = []
    
    # Language reference based on information condition
    ref_doc = _generate_language_reference(
        environment,
        information_condition,
        public_task.information_condition,
    )
    if ref_doc:
        sections.append("## Language Reference")
        sections.append(ref_doc)
    
    # Public examples
    if public_task.prompt.public_examples:
        sections.append("## Public Examples")
        for example in public_task.prompt.public_examples:
            sections.append(f"### Example")
            sections.append(f"```\n{example}\n```")
    
    # Query
    if public_task.prompt.query:
        sections.append("## Query")
        sections.append(f"```\n{public_task.prompt.query}\n```")
    
    # Answer spec instructions
    sections.append("## Instructions")
    
    if public_task.answer_spec.type == "value":
        if public_task.answer_spec.kind == "int":
            sections.append("Answer with a single integer.")
        elif public_task.answer_spec.kind == "bool":
            sections.append("Answer with 'true' or 'false' (lowercase).")
        elif public_task.answer_spec.kind == "error":
            sections.append("Answer with 'ERROR <error_class>' where <error_class> is one of: syntax, name, arity, type, division_by_zero, overflow, literal_range, resource")
        else:
            sections.append("Answer with the appropriate value format.")
        
        if public_task.answer_spec.chance_floor_ppm:
            # Only include if very high floor (>50000)
            if public_task.answer_spec.chance_floor_ppm > 50000:
                sections.append(f"Note: This is a guessing game with approximately 1 in {1000000 // public_task.answer_spec.chance_floor_ppm} chance of guessing correctly.")
    else:
        sections.append("Answer with a single fenced code block containing your program.")
    
    # Format the final prompt
    user_message = "\n\n".join(sections)
    
    return PromptBundle(
        system_message=_build_system_message(information_condition),
        user_message=user_message,
        reference_document=ref_doc,
        template_id=public_task.prompt.template,
        environment_id=public_task.environment_id,
        information_condition=information_condition,
    )


def _build_program_prompt_v1(
    public_task: Any,
    environment: dict[str, Any],
    information_condition: str,
) -> PromptBundle:
    """Build program prompt (program tasks) version 1.
    
    Args:
        public_task: PublicTask object with task data
        environment: Environment record as dict
        information_condition: FULL_DOC, SIGNATURES_ONLY, EXAMPLES_ONLY, etc.
        
    Returns:
        PromptBundle with system and user messages
    """
    sections: list[str] = []
    
    # Language reference
    ref_doc = _generate_language_reference(
        environment,
        information_condition,
        public_task.information_condition,
    )
    if ref_doc:
        sections.append("## Language Reference")
        sections.append(ref_doc)
    
    # Public examples
    if public_task.prompt.public_examples:
        sections.append("## Public Examples")
        for example in public_task.prompt.public_examples:
            sections.append(f"```\n{example}\n```")
    
    # Query
    if public_task.prompt.query:
        sections.append("## Query")
        sections.append(f"```\n{public_task.prompt.query}\n```")
    
    # Specification
    if public_task.prompt.spec:
        sections.append("## Specification")
        sections.append(public_task.prompt.spec)
    
    # Input definitions (if any and public)
    if public_task.input and public_task.input.visibility == "public":
        sections.append("## Task Definitions")
        sections.append("```\n" + public_task.input.source + "\n```")
    
    # Answer spec instructions
    sections.append("## Instructions")
    sections.append("Write a program that meets the specification above.")
    sections.append("Your answer must be a single fenced code block.")
    sections.append("Only include definitions (no final expression).")
    
    if public_task.answer_spec.kind:
        sections.append(f"Return type: {public_task.answer_spec.kind}")
    
    # Format the final prompt
    user_message = "\n\n".join(sections)
    
    return PromptBundle(
        system_message=_build_system_message(information_condition),
        user_message=user_message,
        reference_document=ref_doc,
        template_id=public_task.prompt.template,
        environment_id=public_task.environment_id,
        information_condition=information_condition,
    )


def _build_system_message(information_condition: str) -> str:
    """Build system message based on information condition."""
    return f"""You are a precise programming language interpreter.
Your task is to answer questions about programs in an unfamiliar language.

Information available to you: {information_condition}

Answer precisely according to the instructions below. No explanations."""


def _generate_language_reference(
    environment: dict[str, Any],
    information_condition: str,
    task_information_condition: str,
) -> str:
    """Generate language reference document.
    
    Respects information_condition:
    - FULL_DOC: Full documentation with prose semantics
    - SIGNATURES_ONLY: Signatures and form rules, no prose
    - EXAMPLES_ONLY: Lexical rules and examples only
    - DELTA_DOC: Reference for control plus explicit differences
    - STALE_DOC_EXAMPLES: Control reference plus truthful examples
    """
    sections: list[str] = []
    
    # Lexical rules (always included)
    sections.append("### Lexical Rules")
    sections.append("- Programs use prefix notation: `(operator arg1 arg2 ...)`")
    sections.append("- Integers: `-?[0-9]+`")
    sections.append("- Booleans: `true` or `false`")
    sections.append("- Functions: `(def name (param1 ... paramN) body)`")
    sections.append("- Conditionals: `(if condition then-expr else-expr)`")
    
    # Keywords (always included)
    if "keywords" in environment.get("surface_profile", {}):
        keywords = environment["surface_profile"]["keywords"]
        if keywords:
            sections.append("### Keywords")
            for surface, canonical in sorted(keywords.items()):
                sections.append(f"- `{surface}` means `{canonical}`")
    
    # Operators and their meanings
    if "operators" in environment.get("surface_profile", {}):
        operators = environment["surface_profile"]["operators"]
        if operators:
            sections.append("### Operators")
            
            if information_condition in ("FULL_DOC", "SIGNATURES_ONLY"):
                # Include signatures and meanings
                for surface, canonical in sorted(operators.items()):
                    sections.append(f"- `{surface}` (canonical: `{canonical}`)")
            else:
                # Just list surface names
                sections.append("The following operators are available:")
                for surface in sorted(operators.keys()):
                    sections.append(f"- `{surface}`")
    
    # Literals (always included)
    if "literals" in environment.get("surface_profile", {}):
        literals = environment["surface_profile"]["literals"]
        if literals:
            sections.append("### Literals")
            for surface, canonical in sorted(literals.items()):
                sections.append(f"- `{surface}` means `{canonical}`")
    
    # Semantic configuration (only in FULL_DOC)
    if information_condition == "FULL_DOC":
        semantic = environment.get("semantic", {})
        if semantic:
            sections.append("### Semantic Configuration")
            if "arithmetic" in semantic:
                sections.append(f"- Arithmetic: {semantic['arithmetic']}")
            if "short_circuit" in semantic:
                sections.append(f"- Short-circuit evaluation: {semantic['short_circuit']}")
    
    return "\n".join(sections)


def build_answer_prompt(
    public_task: Any,
    environment: dict[str, Any],
    information_condition: str | None = None,
) -> PromptBundle:
    """Build an answer prompt for value tasks.
    
    Args:
        public_task: PublicTask object with task data
        environment: Environment record as dict
        information_condition: Override information condition (optional)
        
    Returns:
        PromptBundle with system and user messages
    """
    # Get template function
    template_func = _registry.get("prompt.answer")
    
    # Use task's information condition if not overridden
    if information_condition is None:
        information_condition = public_task.information_condition
    
    return template_func(public_task, environment, information_condition)


def build_program_prompt(
    public_task: Any,
    environment: dict[str, Any],
    information_condition: str | None = None,
) -> PromptBundle:
    """Build a program prompt for program tasks.
    
    Args:
        public_task: PublicTask object with task data
        environment: Environment record as dict
        information_condition: Override information condition (optional)
        
    Returns:
        PromptBundle with system and user messages
    """
    # Get template function
    template_func = _registry.get("prompt.program")
    
    # Use task's information condition if not overridden
    if information_condition is None:
        information_condition = public_task.information_condition
    
    return template_func(public_task, environment, information_condition)


# Initialize registry on module import
_initialize_registry()
