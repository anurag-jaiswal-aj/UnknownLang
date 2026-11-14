"""Smoke test to verify test infrastructure and Hypothesis integration."""

import pytest
from hypothesis import given, strategies as st


def test_basic_addition():
    """Verify basic Python arithmetic works."""
    assert 1 + 1 == 2
    assert 2 * 3 == 6


@given(st.integers(), st.integers())
def test_commute_addition(a, b):
    """Test commutativity of addition using Hypothesis."""
    assert a + b == b + a


@given(st.text(min_size=1), st.text(min_size=1))
def test_string_concat_length(a, b):
    """Test string concatenation length property."""
    assert len(a + b) == len(a) + len(b)


@pytest.fixture
def sample_data():
    """Sample data fixture."""
    return {"key": "value", "number": 42}


def test_fixture_works(sample_data):
    """Verify fixtures are usable."""
    assert sample_data["key"] == "value"
    assert sample_data["number"] == 42
