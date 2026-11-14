"""Grammar specification and builder for UnknownLang."""

from dataclasses import dataclass
from typing import ClassVar

from .seed import LanguageSeed


@dataclass(frozen=True)
class GrammarSpec:
    """
    Declarative grammar specification for UnknownLang.
    
    This dataclass represents a context-free grammar using BNF-like notation.
    It is used as an intermediate representation before parser generation.
    """
    terminal_definitions: dict[str, str]
    production_rules: dict[str, list[str]]
    start_symbol: str
    grammar_version: str
    algorithm_version: str


class GrammarBuilder:
    """
    Builds GrammarSpec instances from validated LanguageSeed inputs.
    
    The builder follows a deterministic, configuration-driven approach to
    grammar generation. For the MVP, only Lisp syntax is supported.
    """
    
    GRAMMAR_VERSION: ClassVar[str] = "1.0.0"
    
    # Terminal definitions for the grammar
    TERMINAL_DEFINITIONS: ClassVar[dict[str, str]] = {
        "NUMBER": r'"-?\d+"',
        "BOOLEAN": r'"true|false"',
        "IDENTIFIER": r'"[a-zA-Z_][a-zA-Z0-9_]*"',
        "LPAREN": r'"("',
        "RPAREN": r'")"',
    }
    
    def __init__(self, seed: LanguageSeed) -> None:
        """
        Initialize the builder with a validated LanguageSeed.
        
        Args:
            seed: A validated LanguageSeed instance
            
        Raises:
            ValueError: If seed.syntax_style is not supported (must be "lisp" for MVP)
        """
        if seed.syntax_style != "lisp":
            raise ValueError(
                f"Syntax style '{seed.syntax_style}' is not supported. "
                f"Only 'lisp' is supported for the MVP."
            )
        
        self._seed = seed
    
    def build(self) -> GrammarSpec:
        """
        Build a GrammarSpec from the seed.
        
        Returns:
            A GrammarSpec instance with terminal definitions, production rules,
            and metadata.
        """
        # Determine algorithm version based on seed difficulty
        algorithm_version = f"1.{self._seed.difficulty}.0"
        
        # Build production rules based on seed features
        production_rules = self._build_production_rules()
        
        return GrammarSpec(
            terminal_definitions=self.TERMINAL_DEFINITIONS,
            production_rules=production_rules,
            start_symbol="program",
            grammar_version=self.GRAMMAR_VERSION,
            algorithm_version=algorithm_version,
        )
    
    def _build_production_rules(self) -> dict[str, list[str]]:
        """
        Build production rules based on the seed configuration.
        
        Returns:
            A dictionary mapping non-terminal names to their production rules.
        """
        # Base MVP grammar (required for all seeds)
        rules: dict[str, list[str]] = {
            "program": ["program_element*"],
            "program_element": ["def_decl", "expr"],
            "def_decl": ["LPAREN DEF IDENTIFIER LPAREN param_list RPAREN expr RPAREN"],
            "expr": ["literal", "if_expr", "call"],
            "literal": ["NUMBER", "BOOLEAN", "IDENTIFIER"],
            "if_expr": ["LPAREN IF expr expr expr RPAREN"],
            "call": ["LPAREN IDENTIFIER expr* RPAREN"],
            "param_list": ["IDENTIFIER*"],
        }
        
        return rules
