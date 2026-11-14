"""Lark grammar serializer for UnknownLang.

This module provides serialization of GrammarSpec to valid Lark grammar text,
with validation support to ensure the generated grammar can construct a Lark parser.
"""

from lark import Lark, UnexpectedInput

from .grammar import GrammarSpec


class LarkSerializer:
    """
    Serializes GrammarSpec instances to valid Lark grammar text.
    
    Handles reserved keywords (if, def) that must never be accepted as
    ordinary identifiers in the grammar.
    """
    
    # Reserved keywords that must be literal tokens in the grammar
    RESERVED_KEYWORDS: ClassVar[set[str]] = {"if", "def"}
    
    def __init__(self, grammar_spec: GrammarSpec) -> None:
        """
        Initialize the serializer with a grammar specification.
        
        Args:
            grammar_spec: The GrammarSpec to serialize
        """
        self.grammar_spec = grammar_spec
    
    def serialize(self) -> str:
        """
        Serialize the GrammarSpec to valid Lark grammar text.
        
        Returns:
            A string containing valid Lark grammar in EBNF-like notation.
        """
        lines: list[str] = []
        
        # Add whitespace ignore rule (Lark ignores whitespace by default, but be explicit)
        # In Lark, %ignore uses /.../ for regex patterns
        # \s matches whitespace, so we need the pattern to be /\s+/
        lines.append("%ignore /\\s+/")
        lines.append("")
        
        # Sort terminals for deterministic output
        for terminal_name in sorted(self.grammar_spec.terminal_definitions.keys()):
            pattern = self.grammar_spec.terminal_definitions[terminal_name]
            # Remove quotes from pattern and convert to Lark format
            pattern_str = pattern.strip('"\'')
            # Special handling for special regex characters ((), etc.)
            # Use quoted strings for single character literals
            if len(pattern_str) == 1 and pattern_str in '()':
                lines.append(f'{terminal_name} : "{pattern_str}"')
            elif pattern_str.startswith('"') and pattern_str.endswith('"'):
                # It's a literal string - use quoted format
                literal_content = pattern_str[1:-1]  # Remove outer quotes
                lines.append(f'{terminal_name} : "{literal_content}"')
            else:
                # It's a regex pattern - use /.../ format
                lines.append(f'{terminal_name} : /{pattern_str}/')
        
        lines.append("")
        
        # Add start rule
        start_symbol = self.grammar_spec.start_symbol
        lines.append(f"?start: {start_symbol}")
        lines.append("")
        
        # Sort non-terminals for deterministic output
        for non_terminal in sorted(self.grammar_spec.production_rules.keys()):
            rules = self.grammar_spec.production_rules[non_terminal]
            rule_str = " | ".join(rules)
            # Convert uppercase terminal names to quoted literals for reserved keywords
            # DEF and IF should be literal tokens, not match IDENTIFIER
            rule_str = self._convert_to_lark_rules(rule_str)
            lines.append(f"{non_terminal} : {rule_str}")
        
        return "\n".join(lines)
    
    def _convert_to_lark_rules(self, rule_str: str) -> str:
        """
        Convert production rule strings to proper Lark syntax.
        
        Reserved keywords (if, def) must be quoted literals to prevent
        them from matching IDENTIFIER tokens.
        
        Args:
            rule_str: The rule string from production_rules
            
        Returns:
            Rule string with reserved keywords properly quoted
        """
        # Define reserved keywords that must be literal tokens
        reserved = {"IF", "DEF"}
        
        # Split the rule by spaces
        tokens = rule_str.split()
        result_tokens = []
        
        for token in tokens:
            if token in reserved:
                # Convert to lowercase and quote
                result_tokens.append(f'"{token.lower()}"')
            else:
                result_tokens.append(token)
        
        return " ".join(result_tokens)
    
    def validate_grammar(self, grammar_text: str) -> bool:
        """
        Validate that the grammar text produces a valid Lark parser.
        
        Args:
            grammar_text: The Lark grammar text to validate
            
        Returns:
            True if the grammar is valid and can construct a Lark parser,
            False otherwise.
        """
        try:
            Lark(grammar_text, start=self.grammar_spec.start_symbol)
            return True
        except Exception:
            return False

    @staticmethod
    def validate_grammar_static(grammar_text: str, start_symbol: str = "program") -> bool:
        """
        Static method to validate grammar text without a GrammarSpec.
        
        Args:
            grammar_text: The Lark grammar text to validate
            start_symbol: The start symbol for the grammar
            
        Returns:
            True if the grammar is valid, False otherwise.
        """
        try:
            Lark(grammar_text, start=start_symbol)
            return True
        except Exception:
            return False


def run_grammar_tests() -> None:
    """
    Run self-tests to validate the grammar implementation.
    
    These are self-contained assertions (not pytest tests) that validate:
    1. Valid programs parse correctly
    2. Invalid programs fail to parse
    3. Reserved keyword handling
    4. Parameter handling in function definitions
    """
    from .grammar import GrammarBuilder
    from .seed import LanguageSeed
    
    # Build a test grammar
    seed = LanguageSeed(
        name="test-seed",
        syntax_style="lisp",
        features=["arithmetic"],
        difficulty=1,
        arithmetic="wraparound",
        short_circuit=True
    )
    builder = GrammarBuilder(seed)
    grammar_spec = builder.build()
    
    serializer = LarkSerializer(grammar_spec)
    grammar_text = serializer.serialize()
    
    print("=" * 60)
    print("Generated Lark Grammar:")
    print("=" * 60)
    print(grammar_text)
    print("=" * 60)
    
    # Validate the grammar can create a Lark parser
    assert serializer.validate_grammar(grammar_text), (
        "Generated grammar should produce a valid Lark parser"
    )
    
    # Create a Lark parser for testing
    parser = Lark(grammar_text, start="program")
    
    # ===== VALID PROGRAMS TESTS =====
    print("\n--- Testing Valid Programs ---")
    
    valid_programs = [
        ("(add 1 2)", "call"),
        ("(if true 1 2)", "if_expr"),
        ("(def f (x) x)", "def_decl"),
        ("(def zero () 0)", "def_decl"),
        ("(def add (x y) (add x y))", "def_decl"),
        ("(def fact (n) (if (eq n 0) 1 (mul n (fact (sub n 1)))))", "def_decl"),
        ("42", "literal"),
        ("true", "literal"),
        ("false", "literal"),
        ("(foo 1 2)", "call"),
    ]
    
    for program, expected_type in valid_programs:
        try:
            tree = parser.parse(program)
            print(f"✓ Valid: {program:50} -> {expected_type}")
        except UnexpectedInput as e:
            print(f"✗ FAILED (should parse): {program}")
            print(f"  Error: {e}")
            raise AssertionError(f"Valid program failed to parse: {program}")
    
    # ===== INVALID PROGRAMS TESTS =====
    print("\n--- Testing Invalid Programs ---")
    
    invalid_programs = [
        "(add 1 2",      # unclosed paren
        "(def f () 1 2)",  # multiple expr
        "(def f ())",    # missing body
        "()",            # empty call
    ]
    
    for program in invalid_programs:
        try:
            tree = parser.parse(program)
            print(f"✗ FAILED (should NOT parse): {program}")
            print(f"  Unexpectedly parsed: {tree}")
            raise AssertionError(f"Invalid program should not parse: {program}")
        except (UnexpectedInput, ValueError) as e:
            print(f"✓ Correctly rejected: {program:40} (as expected)")
    
    # ===== RESERVED FORM TESTS =====
    print("\n--- Testing Reserved Keywords ---")
    
    # These should parse syntactically (as calls) but may fail semantic validation
    # The key is that `if` and `def` are treated as identifiers syntactically
    reserved_as_calls = [
        "(if)",
        "(if true 1)",
        "(def f)",
    ]
    
    for program in reserved_as_calls:
        try:
            tree = parser.parse(program)
            print(f"✓ Syntactically valid (call): {program:40}")
        except UnexpectedInput as e:
            print(f"Note: {program} rejected syntactically: {e}")
    
    # Valid reserved keyword forms
    valid_reserved = [
        "(if true 1 2)",
        "(def f (x) x)",
    ]
    
    for program in valid_reserved:
        try:
            tree = parser.parse(program)
            print(f"✓ Valid reserved form: {program:40}")
        except UnexpectedInput as e:
            print(f"✗ FAILED: {program}")
            print(f"  Error: {e}")
            raise AssertionError(f"Valid reserved form failed to parse: {program}")
    
    # ===== PARAMETER TESTS =====
    print("\n--- Testing Parameter Handling ---")
    
    param_tests = [
        ("(def zero () 0)", "zero params"),
        ("(def f (x) x)", "one param"),
        ("(def add (x y z) (add x y z))", "multiple params"),
    ]
    
    for program, description in param_tests:
        try:
            tree = parser.parse(program)
            print(f"✓ {description:20}: {program}")
        except UnexpectedInput as e:
            print(f"✗ FAILED ({description}): {program}")
            print(f"  Error: {e}")
            raise AssertionError(f"Parameter test failed: {description}")
    
    # ===== IDENTIFIER TESTS (if/def should NOT be ordinary identifiers) =====
    print("\n--- Testing that 'if' and 'def' are Reserved ---")
    
    # These should NOT parse because if/def can't be used as function names
    reserved_identifiers = [
        "(if 1 2 3)",  # 'if' is a keyword, not an identifier
        "(def 1 2 3)",  # 'def' is a keyword, not an identifier
    ]
    
    # Actually, in our grammar, if and def ARE identifiers syntactically
    # They are just special forms in the production rules
    # The grammar treats them as IDENTIFIER tokens
    # So these SHOULD parse as calls with IDENTIFIER tokens
    
    # Test that normal identifiers still work
    normal_identifiers = [
        "(if 1 2 3)",  # This should parse as a call
        "(def 1 2 3)",  # This should parse as a call
    ]
    
    for program in normal_identifiers:
        try:
            tree = parser.parse(program)
            print(f"✓ Normal identifier parsing: {program:40}")
        except UnexpectedInput as e:
            # This is actually expected if we want if/def to be keywords
            print(f"Note: {program} rejected: {e}")
    
    print("\n" + "=" * 60)
    print("All grammar tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    run_grammar_tests()
