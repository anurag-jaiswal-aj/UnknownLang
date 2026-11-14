"""Tests for canonical serialization."""

import pytest
from hypothesis import given, strategies as st

from src.language.canonical import (
    canonicalize_value,
    canonical_json,
    canonical_bytes,
)


class TestCanonicalizeValue:
    """Tests for canonicalize_value() function."""

    def test_string_preserved(self):
        """Strings should be returned as-is."""
        assert canonicalize_value("test") == "test"

    def test_integer_preserved(self):
        """Integers should be returned as-is."""
        assert canonicalize_value(42) == 42

    def test_float_preserved(self):
        """Floats should be returned as-is."""
        assert canonicalize_value(3.14) == 3.14

    def test_boolean_preserved(self):
        """Booleans should be returned as-is."""
        assert canonicalize_value(True) is True
        assert canonicalize_value(False) is False

    def test_none_preserved(self):
        """None should be returned as-is."""
        assert canonicalize_value(None) is None

    def test_list_preserves_order(self):
        """Lists preserve element order (ordered sequence)."""
        result = canonicalize_value(["z", "a", "m"])
        assert result == ["z", "a", "m"]

    def test_tuple_preserves_order(self):
        """Tuples preserve element order (ordered sequence)."""
        result = canonicalize_value(("z", "a", "m"))
        assert result == ["z", "a", "m"]

    def test_dict_keys_sorted(self):
        """Dict keys should be sorted."""
        result = canonicalize_value({"z": 1, "a": 2, "m": 3})
        # Keys should be in sorted order: a, m, z
        assert list(result.keys()) == ["a", "m", "z"]
        assert result["a"] == 2
        assert result["m"] == 3
        assert result["z"] == 1

    def test_nested_structure(self):
        """Nested structures should be recursively canonicalized."""
        data = {
            "list": ["z", "a"],
            "dict": {"y": 2, "x": 1},
            "tuple": ("d", "a", "c"),
        }
        result = canonicalize_value(data)
        # Lists preserve order
        assert result["list"] == ["z", "a"]
        # Dict keys are sorted
        assert list(result["dict"].keys()) == ["x", "y"]
        # Tuples preserve order
        assert result["tuple"] == ["d", "a", "c"]


class TestCanonicalJson:
    """Tests for canonical_json() function."""

    def test_json_sorted_keys(self):
        """JSON should have sorted keys."""
        data = {"z": 1, "a": 2, "m": 3}
        json_str = canonical_json(data)
        # Keys should appear in sorted order
        assert json_str.index('"a"') < json_str.index('"m"')
        assert json_str.index('"m"') < json_str.index('"z"')

    def test_json_no_whitespace_compact(self):
        """Compact JSON should have no extra whitespace."""
        data = {"key": "value"}
        json_str = canonical_json(data)
        assert " " not in json_str
        assert json_str == '{"key":"value"}'

    def test_json_with_indent(self):
        """JSON with indent should have proper formatting."""
        data = {"key": "value"}
        json_str = canonical_json(data, indent=2)
        assert "\n" in json_str
        assert "  " in json_str

    def test_json_deterministic(self):
        """Same data should produce identical JSON."""
        data = {"key": "value", "number": 42}
        json1 = canonical_json(data)
        json2 = canonical_json(data)
        assert json1 == json2

    def test_json_stable_across_runs(self):
        """JSON should be stable across multiple calls."""
        data = {"b": 2, "a": 1, "c": 3}
        json1 = canonical_json(data)
        json2 = canonical_json(data)
        json3 = canonical_json(data)
        assert json1 == json2 == json3


class TestCanonicalBytes:
    """Tests for canonical_bytes() function."""

    def test_bytes_utf8(self):
        """Bytes should be valid UTF-8."""
        data = {"key": "value"}
        result = canonical_bytes(data)
        # Should decode successfully
        decoded = result.decode("utf-8")
        assert isinstance(decoded, str)

    def test_bytes_deterministic(self):
        """Same data should produce identical bytes."""
        data = {"key": "value"}
        bytes1 = canonical_bytes(data)
        bytes2 = canonical_bytes(data)
        assert bytes1 == bytes2

    def test_bytes_match_json(self):
        """Bytes should match canonical_json output."""
        data = {"key": "value"}
        json_str = canonical_json(data)
        bytes_result = canonical_bytes(data)
        assert bytes_result == json_str.encode("utf-8")


class TestDeterminism:
    """Tests for serialization determinism."""

    def test_serialization_stable(self):
        """Serialization should be stable across many runs."""
        data = {"features": ["z", "a", "m"], "name": "test"}
        results = [canonical_bytes(data) for _ in range(100)]
        assert len(set(results)) == 1

    def test_serialization_ignores_dict_order(self):
        """Same data in different dict order should produce same output."""
        data1 = {"z": 1, "a": 2, "m": 3}
        data2 = {"a": 2, "m": 3, "z": 1}
        data3 = {"m": 3, "a": 2, "z": 1}
        assert canonical_bytes(data1) == canonical_bytes(data2)
        assert canonical_bytes(data2) == canonical_bytes(data3)

    def test_serialization_ignores_dict_order(self):
        """Same data in different dict order should produce same output."""
        data1 = {"z": 1, "a": 2, "m": 3}
        data2 = {"a": 2, "m": 3, "z": 1}
        data3 = {"m": 3, "a": 2, "z": 1}
        assert canonical_bytes(data1) == canonical_bytes(data2)
        assert canonical_bytes(data2) == canonical_bytes(data3)

    def test_serialization_preserves_list_order(self):
        """Ordered lists with different element orders should serialize differently."""
        data1 = {"features": ["z", "a", "m"]}
        data2 = {"features": ["a", "m", "z"]}
        assert canonical_bytes(data1) != canonical_bytes(data2)

    def test_serialization_preserves_tuple_order(self):
        """Ordered tuples with different element orders should serialize differently."""
        data1 = {"features": ("z", "a", "m")}
        data2 = {"features": ("a", "m", "z")}
        assert canonical_bytes(data1) != canonical_bytes(data2)

    def test_serialization_ignores_dict_key_order(self):
        """Dict keys in different orders should produce identical output."""
        data1 = {"z": 1, "a": 2, "m": 3}
        data2 = {"a": 2, "m": 3, "z": 1}
        data3 = {"m": 3, "a": 2, "z": 1}
        assert canonical_bytes(data1) == canonical_bytes(data2)
        assert canonical_bytes(data2) == canonical_bytes(data3)


class TestUnorderedFeatureCollections:
    """Tests for unordered feature collection handling."""

    def test_equivalent_features_produce_identical_identity(self):
        """Different order of features should produce identical canonical bytes."""
        from src.language.seed import LanguageSeed
        
        seed1 = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["z-feature", "a-feature", "m-feature"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        seed2 = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["a-feature", "m-feature", "z-feature"],
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        
        # to_dict normalizes features to sorted list
        bytes1 = seed1.to_canonical_bytes()
        bytes2 = seed2.to_canonical_bytes()
        assert bytes1 == bytes2

    def test_features_in_tuple_and_list_produce_identical_identity(self):
        """Features as list vs tuple should produce identical identity."""
        from src.language.seed import LanguageSeed
        
        seed1 = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["a", "z", "m"],  # list input
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        seed2 = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=("a", "z", "m"),  # tuple input
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        
        # Both should normalize features to sorted tuple internally
        bytes1 = seed1.to_canonical_bytes()
        bytes2 = seed2.to_canonical_bytes()
        assert bytes1 == bytes2

    def test_from_dict_and_direct_construction_equivalent(self):
        """from_dict and direct construction with same data should produce identical identity."""
        from src.language.seed import LanguageSeed
        
        data = {
            "name": "Test",
            "syntax_style": "lisp",
            "features": ["z", "a", "m"],
            "difficulty": 1,
            "arithmetic": "wraparound",
            "short_circuit": True,
        }
        
        seed1 = LanguageSeed.from_dict(data)
        seed2 = LanguageSeed(
            name="Test",
            syntax_style="lisp",
            features=["a", "m", "z"],  # Already sorted in from_dict
            difficulty=1,
            arithmetic="wraparound",
            short_circuit=True,
        )
        
        bytes1 = seed1.to_canonical_bytes()
        bytes2 = seed2.to_canonical_bytes()
        assert bytes1 == bytes2


@given(
    st.dictionaries(
        keys=st.text(min_size=1, max_size=10),
        values=st.one_of(
            st.text(),
            st.integers(),
            st.booleans(),
            st.none(),
            st.dictionaries(
                keys=st.text(min_size=1, max_size=5),
                values=st.integers()
            )
        ),
        min_size=1,
        max_size=10,
    )
)
def test_hypothesis_json_determinism(data):
    """Hypothesis test for JSON determinism across many inputs."""
    json1 = canonical_json(data)
    json2 = canonical_json(data)
    assert json1 == json2

    bytes1 = canonical_bytes(data)
    bytes2 = canonical_bytes(data)
    assert bytes1 == bytes2
