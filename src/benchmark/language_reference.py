"""Language reference generation for Wave 2 benchmark.

This module generates language reference documents from environment records
according to the information_condition contract in benchmark-task-schema.md section 8.2.

Information conditions:
- FULL_DOC: Full documentation with prose semantics
- SIGNATURES_ONLY: Signatures and form rules, no prose
- EXAMPLES_ONLY: Lexical rules and examples only
- DELTA_DOC: Reference for control plus explicit differences
- STALE_DOC_EXAMPLES: Control reference plus truthful examples
"""

from __future__ import annotations

from typing import Any


def generate_language_reference(
    environment: dict[str, Any],
    information_condition: str,
    task_info_condition: str | None = None,
) -> str:
    """Generate language reference from environment record.
    
    Args:
        environment: Environment record from environments.py or manager.py
        information_condition: FULL_DOC, SIGNATURES_ONLY, EXAMPLES_ONLY, DELTA_DOC, or STALE_DOC_EXAMPLES
        task_info_condition: Task's information condition (for DELTA_DOC comparison)
        
    Returns:
        Human-readable language reference document
        
    Raises:
        ValueError: If information_condition is invalid
    """
    valid_conditions = {
        "FULL_DOC",
        "SIGNATURES_ONLY", 
        "EXAMPLES_ONLY",
        "DELTA_DOC",
        "STALE_DOC_EXAMPLES",
    }
    
    if information_condition not in valid_conditions:
        raise ValueError(
            f"Invalid information_condition: {information_condition}. "
            f"Must be one of: {valid_conditions}"
        )
    
    sections: list[str] = []
    
    # Always include lexical rules
    _add_lexical_rules(sections, environment)
    
    # Add keywords
    _add_keywords(sections, environment)
    
    # Add operators
    _add_operators(sections, environment, information_condition)
    
    # Add literals
    _add_literals(sections, environment)
    
    # Add semantic configuration (only in FULL_DOC)
    if information_condition == "FULL_DOC":
        _add_semantic_config(sections, environment)
    
    # Add form rules
    _add_form_rules(sections)
    
    # Add limits
    _add_limits(sections)
    
    # Handle special information conditions
    if information_condition == "DELTA_DOC" and task_info_condition:
        _add_delta_documentation(sections, environment, task_info_condition)
    
    return "\n".join(sections)


def _add_lexical_rules(sections: list[str], environment: dict[str, Any]) -> None:
    """Add lexical rules section."""
    sections.append("## Lexical Rules")
    sections.append("")
    sections.append("- **Programs** use prefix notation: `(operator arg1 arg2 ...)`")
    sections.append("- **Integers**: `-?[0-9]+` (negative allowed)")
    sections.append("- **Booleans**: `true` or `false`")
    sections.append("- **Function definitions**: `(def name (param1 ... paramN) body)`")
    sections.append("- **Conditionals**: `(if condition then-expr else-expr)`")
    sections.append("- **Function calls**: `(function arg1 arg2 ...)`")
    sections.append("")


def _add_keywords(sections: list[str], environment: dict[str, Any]) -> None:
    """Add keywords section."""
    surface_profile = environment.get("surface_profile", {})
    keywords = surface_profile.get("keywords", {})
    
    if not keywords:
        return
    
    sections.append("## Keywords")
    sections.append("")
    
    # Map canonical to surface for readability
    canonical_to_surface: dict[str, list[str]] = {}
    for surface, canonical in sorted(keywords.items()):
        if canonical not in canonical_to_surface:
            canonical_to_surface[canonical] = []
        canonical_to_surface[canonical].append(surface)
    
    for canonical, surfaces in sorted(canonical_to_surface.items()):
        sections.append(f"- `{canonical}` can be written as: {', '.join(f'`{s}`' for s in sorted(surfaces))}")
    
    sections.append("")


def _add_operators(sections: list[str], environment: dict[str, Any], information_condition: str) -> None:
    """Add operators section based on information condition."""
    surface_profile = environment.get("surface_profile", {})
    operators = surface_profile.get("operators", {})
    
    if not operators:
        return
    
    sections.append("## Operators")
    sections.append("")
    
    if information_condition in ("FULL_DOC", "SIGNATURES_ONLY"):
        # Include signatures and meanings for FULL_DOC and SIGNATURES_ONLY
        sections.append("The following operators are available:")
        sections.append("")
        
        for surface, canonical in sorted(operators.items()):
            if information_condition == "FULL_DOC":
                # Include prose semantics
                semantics = _get_operator_semantics(canonical)
                sections.append(f"- `{surface}` (canonical: `{canonical}`): {semantics}")
            else:
                # SIGNATURES_ONLY: just signatures
                sections.append(f"- `{surface}` (canonical: `{canonical}`)")
    else:
        # EXAMPLES_ONLY, DELTA_DOC, STALE_DOC_EXAMPLES: just list surface names
        sections.append("The following operators are available:")
        sections.append("")
        for surface in sorted(operators.keys()):
            sections.append(f"- `{surface}`")
    
    sections.append("")


def _get_operator_semantics(canonical: str) -> str:
    """Get prose semantics for canonical operator."""
    semantics = {
        "add": "Adds two integers. Example: `(add 2 3)` returns `5`.",
        "sub": "Subtracts second argument from first. Example: `(sub 5 3)` returns `2`.",
        "mul": "Multiplies two integers. Example: `(mul 3 4)` returns `12`.",
        "div": "Integer division (truncates toward zero). Example: `(div 7 3)` returns `2`.",
        "mod": "Modulo (remainder with sign of dividend). Example: `(mod 7 3)` returns `1`.",
        "and": "Short-circuit AND (returns false if first arg is false, else evaluates second).",
        "or": "Short-circuit OR (returns true if first arg is true, else evaluates second).",
        "not": "Boolean negation. Example: `(not true)` returns `false`.",
        "eq": "Equality comparison. Returns true if arguments are equal, false otherwise.",
    }
    
    return semantics.get(canonical, f"Operator `{canonical}`.")


def _add_literals(sections: list[str], environment: dict[str, Any]) -> None:
    """Add literals section."""
    surface_profile = environment.get("surface_profile", {})
    literals = surface_profile.get("literals", {})
    
    if not literals:
        return
    
    sections.append("## Literals")
    sections.append("")
    
    canonical_to_surface: dict[str, list[str]] = {}
    for surface, canonical in sorted(literals.items()):
        if canonical not in canonical_to_surface:
            canonical_to_surface[canonical] = []
        canonical_to_surface[canonical].append(surface)
    
    for canonical, surfaces in sorted(canonical_to_surface.items()):
        sections.append(f"- `{canonical}` can be written as: {', '.join(f'`{s}`' for s in sorted(surfaces))}")
    
    sections.append("")


def _add_semantic_config(sections: list[str], environment: dict[str, Any]) -> None:
    """Add semantic configuration section."""
    semantic = environment.get("semantic", {})
    
    if not semantic:
        return
    
    sections.append("## Semantic Configuration")
    sections.append("")
    
    if "arithmetic" in semantic:
        arithmetic_mode = semantic["arithmetic"]
        sections.append(f"- **Arithmetic mode**: `{arithmetic_mode}`")
        
        if arithmetic_mode == "wraparound":
            sections.append("  - Integer arithmetic wraps around on overflow")
        elif arithmetic_mode == "saturating":
            sections.append("  - Integer arithmetic saturates at boundaries")
        elif arithmetic_mode == "error-on-overflow":
            sections.append("  - Integer arithmetic raises overflow error")
    
    if "short_circuit" in semantic:
        short_circuit = semantic["short_circuit"]
        sections.append(f"- **Short-circuit evaluation**: `{short_circuit}`")
    
    sections.append("")


def _add_form_rules(sections: list[str]) -> None:
    """Add form rules section."""
    sections.append("## Form Rules")
    sections.append("")
    sections.append("- All expressions use parentheses: `( ... )`")
    sections.append("- Function arguments are space-separated within parentheses")
    sections.append("- Nested expressions are formed by nesting parentheses")
    sections.append("- Function definitions must use `def` keyword")
    sections.append("- Conditional expressions must use `if` keyword")
    sections.append("")


def _add_limits(sections: list[str]) -> None:
    """Add execution limits section."""
    sections.append("## Execution Limits")
    sections.append("")
    sections.append("- Maximum AST depth: 1000")
    sections.append("- Maximum call depth: 100")
    sections.append("- Maximum evaluation steps: 100000")
    sections.append("- Maximum submission size: 4096 bytes")
    sections.append("")


def _add_delta_documentation(
    sections: list[str],
    environment: dict[str, Any],
    task_info_condition: str,
) -> None:
    """Add delta documentation for DELTA_DOC information condition."""
    sections.append("## Differences from Control Environment")
    sections.append("")
    sections.append("The following differences exist between this environment and the control:")
    
    # Determine differences based on information condition
    if task_info_condition == "FULL_DOC":
        sections.append("- This environment has different semantics from the control")
    elif task_info_condition == "EXAMPLES_ONLY":
        sections.append("- This environment provides only examples (no prose)")
    elif task_info_condition == "SIGNATURES_ONLY":
        sections.append("- This environment provides only signatures (no prose)")
    else:
        sections.append("- Information condition differs from control")
    
    sections.append("")


def get_supported_information_conditions() -> set[str]:
    """Get set of supported information conditions."""
    return {
        "FULL_DOC",
        "SIGNATURES_ONLY",
        "EXAMPLES_ONLY",
        "DELTA_DOC",
        "STALE_DOC_EXAMPLES",
    }
