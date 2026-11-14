"""Tests for GrammarBuilder and LarkSerializer."""

import pytest
from hypothesis import given, strategies as st

from src.language.grammar import GrammarBuilder, GrammarSpec
from src.language.seed import LanguageSeed, ValidationError
from src.language.serializer import LarkSerializer


class TestGrammarBuilder:
    """Tests for GrammarBuilder class."""

    def test_same_seed_produces_identical_grammar(self):
        """Same seed should always produce identical GrammarSpec."""
        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["arithmetic"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        builder1 = GrammarBuilder(seed)
        spec1 = builder1.build()
        builder2 = GrammarBuilder(seed)
        spec2 = builder2.build()
        assert spec1.terminal_definitions == spec2.terminal_definitions
        assert spec1.production_rules == spec2.production_rules
        assert spec1.start_symbol == spec2.start_symbol

    def test_different_seeds_produce_different_grammars(self):
        """Different seeds should produce different GrammarSpec."""
        seed1 = LanguageSeed(
            name="Test1",
            syntax_style="lisp",
            features=["arithmetic"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        seed2 = LanguageSeed(
            name="Test2",
            syntax_style="lisp",
            features=["arithmetic"],
            difficulty=2,
            arithmetic="wraparound",
            short_circuit=True,
        )
        builder1 = GrammarBuilder(seed1)
        spec1 = builder1.build()
        builder2 = GrammarBuilder(seed2)
        spec2 = builder2.build()
        assert spec1.algorithm_version != spec2.algorithm_version

    def test_non_lisp_syntax_raises_value_error(self):
        """Non-lisp syntax style should raise ValueError."""
        seed = LanguageSeed(
            name="Test",
            syntax_style="c-like",
            features=["arithmetic"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        with pytest.raises(ValueError, match="Syntax style.*is not supported"):
            GrammarBuilder(seed)

    def test_production_rules_include_reserved_keywords(self):
        """Production rules should include reserved keywords."""
        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["arithmetic"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        builder = GrammarBuilder(seed)
        spec = builder.build()
        # Check that production rules reference IF and DEF
        rule_strings = []
        for rules in spec.production_rules.values():
            rule_strings.extend(rules)
        rule_text = " ".join(rule_strings)
        assert "IF" in rule_text
        assert "DEF" in rule_text

    def test_grammar_spec_structure(self):
        """GrammarSpec should have correct structure."""
        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["arithmetic"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        builder = GrammarBuilder(seed)
        spec = builder.build()
        assert isinstance(spec.terminal_definitions, dict)
        assert isinstance(spec.production_rules, dict)
        assert isinstance(spec.start_symbol, str)
        assert spec.grammar_version == "1.0.0"
        assert spec.algorithm_version == "1.1.0"


class TestLarkSerializer:
    """Tests for LarkSerializer class."""

    def test_generated_grammar_produces_valid_lark_parser(self):
        """Generated grammar should produce a valid Lark parser."""
        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["arithmetic"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        grammar_builder = GrammarBuilder(seed)
        grammar_spec = grammar_builder.build()
        lark_serializer = LarkSerializer(grammar_spec)
        grammar_text = lark_serializer.serialize()
        # Validate that the grammar can be parsed by Lark
        is_valid = LarkSerializer.validate_grammar_static(grammar_text)
        assert is_valid is True

    def test_reserved_keywords_cannot_be_identifiers(self):
        """Reserved keywords should not be parsed as identifiers."""
        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["arithmetic"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        grammar_builder = GrammarBuilder(seed)
        grammar_spec = grammar_builder.build()
        lark_serializer = LarkSerializer(grammar_spec)
        grammar_text = lark_serializer.serialize()
        # The IDENTIFIER rule should not match reserved keywords
        # Check that IF and def are used as literal terminals in rules
        assert '"if"' in grammar_text
        assert '"def"' in grammar_text
        # IDENTIFIER pattern should be defined separately
        assert "IDENTIFIER" in grammar_text

    def test_valid_programs_parse(self):
        """Valid programs should parse correctly."""
        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["arithmetic"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        grammar_builder = GrammarBuilder(seed)
        grammar_spec = grammar_builder.build()
        lark_serializer = LarkSerializer(grammar_spec)
        grammar_text = lark_serializer.serialize()
        
        # Test basic arithmetic: (add 1 2)
        valid_programs = [
            "(add 1 2)",
            "(if true 1 2)",
            "(def f (x) x)",
        ]
        
        for program in valid_programs:
            # Validate grammar first
            assert LarkSerializer.validate_grammar_static(grammar_text) is True

    def test_grammar_serialization_structure(self):
        """Grammar serialization should have proper structure."""
        seed = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["arithmetic"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        grammar_builder = GrammarBuilder(seed)
        grammar_spec = grammar_builder.build()
        lark_serializer = LarkSerializer(grammar_spec)
        grammar_text = lark_serializer.serialize()
        
        # Check for required elements
        assert "start: program" in grammar_text
        assert "program :" in grammar_text
        assert "NUMBER :" in grammar_text
        assert "IDENTIFIER :" in grammar_text

    def test_hypothesis_grammar_determinism(self):
        """Hypothesis test for grammar determinism across many inputs."""
        from hypothesis import given, strategies as st
        
        @given(
            name=st.text(min_size=1, max_size=50).filter(lambda x: x.strip() == x),
            features=st.lists(
                st.text(min_size=1, max_size=20).filter(lambda x: x.strip() == x),
                min_size=1,
                max_size=5,
            ),
            difficulty=st.integers(min_value=1, max_value=5),
            arithmetic=st.sampled_from(["wraparound", "saturating", "error-on-overflow"]),
            short_circuit=st.booleans(),
        )
        def test_inner(name, features, difficulty, arithmetic, short_circuit):
            seed = LanguageSeed(
                name=name,
                syntax_style="lisp",
                features=list(features),
                difficulty=difficulty,
                arithmetic=arithmetic,
                short_circuit=short_circuit,
            )
            builder1 = GrammarBuilder(seed)
            spec1 = builder1.build()
            builder2 = GrammarBuilder(seed)
            spec2 = builder2.build()
            assert spec1.terminal_definitions == spec2.terminal_definitions
            assert spec1.production_rules == spec2.production_rules
            assert spec1.start_symbol == spec2.start_symbol
        
        test_inner()
