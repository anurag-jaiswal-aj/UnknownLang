"""pytest configuration and fixtures for UnknownLang."""

import pytest


@pytest.fixture
def sample_language_seed():
    """Sample language seed for testing."""
    return {
        "name": "TestLang",
        "syntax_style": "lisp",
        "features": ["recursion", "functions"],
        "difficulty": 1
    }


@pytest.fixture
def sample_grammar():
    """Sample Lark grammar for testing."""
    return """
        start: program
        program: expr+
        expr: atom | list
        list: "(" expr* ")"
        atom: NUMBER | STRING | IDENTIFIER
        NUMBER: /[0-9]+/
        STRING: /"[^"]*"/
        IDENTIFIER: /[a-zA-Z][a-zA-Z0-9]*/
    """


@pytest.fixture
def sample_program():
    """Sample program in generated language."""
    return "(add 1 2)"


# LanguageSeed fixtures

@pytest.fixture
def language_seed_basic():
    """Basic language seed for testing."""
    from src.language.seed import LanguageSeed
    
    return LanguageSeed(
        name="BasicLang",
        syntax_style="lisp",
        features=["recursion"],
        difficulty=1,
        arithmetic="wraparound",
        short_circuit=True,
    )


@pytest.fixture
def language_seed_with_features():
    """Language seed with multiple features."""
    from src.language.seed import LanguageSeed
    
    return LanguageSeed(
        name="FeatureLang",
        syntax_style="lisp",
        features=["recursion", "functions", "types"],
        difficulty=3,
        arithmetic="saturating",
        short_circuit=False,
    )


@pytest.fixture
def language_seed_complex():
    """Complex language seed for testing."""
    from src.language.seed import LanguageSeed
    
    return LanguageSeed(
        name="ComplexLang",
        syntax_style="lisp",
        features=["recursion", "functions", "types", "macros"],
        difficulty=5,
        arithmetic="error-on-overflow",
        short_circuit=True,
    )


# GrammarSpec fixtures

@pytest.fixture
def grammar_spec_basic():
    """Basic grammar spec for testing."""
    from src.language.grammar import GrammarSpec
    
    return GrammarSpec(
        terminal_definitions={
            "NUMBER": r'"-?\d+"',
            "BOOLEAN": r'"true|false"',
            "IDENTIFIER": r'"[a-zA-Z_][a-zA-Z0-9_]*"',
            "LPAREN": r'"("',
            "RPAREN": r'")"',
        },
        production_rules={
            "program": ["program_element*"],
            "program_element": ["def_decl", "expr"],
        },
        start_symbol="program",
        grammar_version="1.0.0",
        algorithm_version="1.1.0",
    )


@pytest.fixture
def grammar_spec_with_features():
    """Grammar spec with additional features."""
    from src.language.grammar import GrammarSpec
    
    return GrammarSpec(
        terminal_definitions={
            "NUMBER": r'"-?\d+"',
            "BOOLEAN": r'"true|false"',
            "STRING": r'"[^"]*"',
            "IDENTIFIER": r'"[a-zA-Z_][a-zA-Z0-9_]*"',
        },
        production_rules={
            "program": ["statement*"],
            "statement": ["expr", "def_stmt"],
            "expr": ["atom", "call", "lambda"],
        },
        start_symbol="program",
        grammar_version="1.0.0",
        algorithm_version="1.2.0",
    )


# SemanticSpec fixtures

@pytest.fixture
def semantic_spec_basic():
    """Basic semantic spec for testing."""
    from src.language.semantics import SemanticSpec, OperationInfo
    
    return SemanticSpec(
        arithmetic_mode="wraparound",
        short_circuit_mode=True,
        operations={
            "add": OperationInfo(
                name="add",
                arity=2,
                arg_types=("int", "int"),
                return_type="int",
                semantic_mode="wraparound",
            ),
            "sub": OperationInfo(
                name="sub",
                arity=2,
                arg_types=("int", "int"),
                return_type="int",
                semantic_mode="wraparound",
            ),
        },
    )


@pytest.fixture
def semantic_spec_full():
    """Full semantic spec with all operations."""
    from src.language.semantics import SemanticSpec, OperationInfo
    
    return SemanticSpec(
        arithmetic_mode="saturating",
        short_circuit_mode=False,
        operations={
            "add": OperationInfo(
                name="add",
                arity=2,
                arg_types=("int", "int"),
                return_type="int",
                semantic_mode="saturating",
            ),
            "sub": OperationInfo(
                name="sub",
                arity=2,
                arg_types=("int", "int"),
                return_type="int",
                semantic_mode="saturating",
            ),
            "mul": OperationInfo(
                name="mul",
                arity=2,
                arg_types=("int", "int"),
                return_type="int",
                semantic_mode="saturating",
            ),
            "div": OperationInfo(
                name="div",
                arity=2,
                arg_types=("int", "int"),
                return_type="int",
                semantic_mode="error-on-overflow",
            ),
            "mod": OperationInfo(
                name="mod",
                arity=2,
                arg_types=("int", "int"),
                return_type="int",
                semantic_mode="error-on-overflow",
            ),
            "and": OperationInfo(
                name="and",
                arity=2,
                arg_types=("bool", "bool"),
                return_type="bool",
                semantic_mode="strict",
            ),
            "or": OperationInfo(
                name="or",
                arity=2,
                arg_types=("bool", "bool"),
                return_type="bool",
                semantic_mode="strict",
            ),
            "not": OperationInfo(
                name="not",
                arity=1,
                arg_types=("bool",),
                return_type="bool",
                semantic_mode="strict",
            ),
            "eq": OperationInfo(
                name="eq",
                arity=2,
                arg_types=("any", "any"),
                return_type="bool",
                semantic_mode="strict",
            ),
            "if": OperationInfo(
                name="if",
                arity=3,
                arg_types=("bool", "any", "any"),
                return_type="any",
                semantic_mode="strict",
            ),
        },
    )


# LanguageSpec fixtures

@pytest.fixture
def language_spec_basic():
    """Basic language spec for testing."""
    from src.language.generator import LanguageSpec
    from src.language.semantics import SemanticSpec, OperationInfo
    from src.language.seed import LanguageSeed
    
    seed = LanguageSeed(
        name="BasicLang",
        syntax_style="lisp",
        features=["recursion"],
        difficulty=1,
        arithmetic="wraparound",
        short_circuit=True,
    )
    
    grammar = """
        start: program
        program: expr+
        expr: literal | call
        literal: NUMBER
        call: "(" IDENTIFIER expr* ")"
        NUMBER: /[0-9]+/
        IDENTIFIER: /[a-zA-Z_][a-zA-Z0-9_]*/
    """
    
    semantic_spec = SemanticSpec(
        arithmetic_mode="wraparound",
        short_circuit_mode=True,
        operations={
            "add": OperationInfo(
                name="add",
                arity=2,
                arg_types=("int", "int"),
                return_type="int",
                semantic_mode="wraparound",
            ),
        },
    )
    
    builtins = {
        "add": OperationInfo(
            name="add",
            arity=2,
            arg_types=("int", "int"),
            return_type="int",
            semantic_mode="wraparound",
        ),
    }
    
    return LanguageSpec(
        version="1.0.0",
        spec_version="1.0.0",
        algorithm_version="1.1.0",
        language_id="lang_" + "a" * 64,  # Fake ID
        seed=seed,
        grammar=grammar,
        semantics=semantic_spec,
        builtins=builtins,
    )


@pytest.fixture
def language_spec_full():
    """Full language spec for testing."""
    from src.language.generator import LanguageSpec
    from src.language.semantics import SemanticSpec, OperationInfo
    from src.language.seed import LanguageSeed
    
    seed = LanguageSeed(
        name="FullLang",
        syntax_style="lisp",
        features=["recursion", "functions"],
        difficulty=3,
        arithmetic="saturating",
        short_circuit=False,
    )
    
    grammar = """
        start: program
        program: program_element*
        program_element: def_decl | expr
        def_decl: "(" DEF IDENTIFIER "(" param_list ")" expr ")"
        expr: literal | if_expr | call
        literal: NUMBER | BOOLEAN | IDENTIFIER
        if_expr: "(" IF expr expr expr ")"
        call: "(" IDENTIFIER expr* ")"
        param_list: IDENTIFIER*
        NUMBER: /[0-9]+/
        BOOLEAN: /true|false/
        IDENTIFIER: /[a-zA-Z_][a-zA-Z0-9_]*/
        DEF: "def"
        IF: "if"
    """
    
    semantic_spec = SemanticSpec(
        arithmetic_mode="saturating",
        short_circuit_mode=False,
        operations={
            "add": OperationInfo(
                name="add",
                arity=2,
                arg_types=("int", "int"),
                return_type="int",
                semantic_mode="saturating",
            ),
            "sub": OperationInfo(
                name="sub",
                arity=2,
                arg_types=("int", "int"),
                return_type="int",
                semantic_mode="saturating",
            ),
            "mul": OperationInfo(
                name="mul",
                arity=2,
                arg_types=("int", "int"),
                return_type="int",
                semantic_mode="saturating",
            ),
            "div": OperationInfo(
                name="div",
                arity=2,
                arg_types=("int", "int"),
                return_type="int",
                semantic_mode="error-on-overflow",
            ),
            "mod": OperationInfo(
                name="mod",
                arity=2,
                arg_types=("int", "int"),
                return_type="int",
                semantic_mode="error-on-overflow",
            ),
            "and": OperationInfo(
                name="and",
                arity=2,
                arg_types=("bool", "bool"),
                return_type="bool",
                semantic_mode="strict",
            ),
            "or": OperationInfo(
                name="or",
                arity=2,
                arg_types=("bool", "bool"),
                return_type="bool",
                semantic_mode="strict",
            ),
            "not": OperationInfo(
                name="not",
                arity=1,
                arg_types=("bool",),
                return_type="bool",
                semantic_mode="strict",
            ),
            "eq": OperationInfo(
                name="eq",
                arity=2,
                arg_types=("any", "any"),
                return_type="bool",
                semantic_mode="strict",
            ),
            "if": OperationInfo(
                name="if",
                arity=3,
                arg_types=("bool", "any", "any"),
                return_type="any",
                semantic_mode="strict",
            ),
        },
    )
    
    builtins = dict(sorted(semantic_spec.operations.items()))
    
    return LanguageSpec(
        version="1.0.0",
        spec_version="1.0.0",
        algorithm_version="1.3.0",
        language_id="lang_" + "b" * 64,  # Fake ID
        seed=seed,
        grammar=grammar,
        semantics=semantic_spec,
        builtins=builtins,
    )
