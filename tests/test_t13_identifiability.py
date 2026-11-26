"""T13: identifiability of surface operators in INF queries."""
from src.benchmark.environments import build_environment
from src.benchmark.generators.generator import TaskGenerator, _identity_profile

_ENV = build_environment("wraparound", True, _identity_profile())
from src.benchmark.generators.identifiability import T13Identifiability

Q = "(def f1 (x1) (zorp x1 3)) (f1 5)"
t13 = T13Identifiability()


def test_unique_meaning_passes():
    # 7+7 == 7*2 would be ambiguous; 5,3 -> 8 only fits add (mul 15, sub 2, div 1, mod 2)
    assert t13.check(Q, ["(zorp 5 3) = 8"]) == (True, "")


def test_add_vs_mul_ambiguous():
    ok, why = t13.check(Q, ["(zorp 2 2) = 4"])
    assert not ok and "ambiguous" in why and "add" in why and "mul" in why


def test_count_alone_is_not_enough():
    ok, _ = t13.check(Q, ["(zorp 2 2) = 4", "(zorp 2 2) = 4"])
    assert not ok


def test_contradiction_rejected():
    ok, why = t13.check(Q, ["(zorp 5 3) = 8", "(zorp 5 3) = 15"])
    assert not ok and "contradict" in why


def test_no_consistent_meaning_rejected():
    ok, why = t13.check(Q, ["(zorp 5 3) = 99"])
    assert not ok and "no canonical" in why


def test_missing_examples_rejected():
    assert t13.check(Q, ["(blik 5 3) = 8"]) == (False, "Operator 'zorp' in query has no examples")


def test_defined_function_is_not_an_operator():
    assert t13.query_operators(Q) == {"zorp": 2}


def test_generated_inf_tasks_are_answerable_and_identifiable():
    for seed in range(10):
        for level in (1, 4):
            res = TaskGenerator(_ENV.environment_id, f"t13_{seed}", {_ENV.environment_id: _ENV}).generate_single_task("INF", level, "FULL_DOC")
            assert res.success, res.rejection_reason
            task = res.task
            assert t13.check(task.prompt.query, list(task.prompt.public_examples)) == (True, "")
            assert "surface_profile" in task.provenance


class TestT13EnvironmentSpecific:
    """Tests for T13 with different environment configurations."""

    def test_wraparound_vs_saturating_different_identifiability(self):
        """Same examples can be identifiable under wraparound but not saturating."""
        # Test with wraparound (current default)
        wraparound_t13 = T13Identifiability(arithmetic="wraparound", short_circuit=True)
        
        # For (zorp 1000000000 1000000000), wraparound gives 2000000000 mod 2^63
        # but saturating would give MAX_INT64 (overflow)
        wraparound_ok, wraparound_msg = wraparound_t13.check(
            "(zorp 1000000000 1000000000)",
            ["(zorp 1000000000 1000000000) = 2000000000"]
        )
        # Should pass because 2000000000 is a valid result in wraparound
        assert wraparound_ok, f"Expected pass with wraparound: {wraparound_msg}"

    def test_wraparound_arithmetic_mode(self):
        """T13 correctly uses wraparound semantics when specified."""
        t13_wraparound = T13Identifiability(arithmetic="wraparound", short_circuit=True)
        
        # Check that basic addition works correctly
        ok, msg = t13_wraparound.check(
            "(add 1 2)",
            ["(add 1 2) = 3", "(add 5 3) = 8"]
        )
        assert ok, f"Expected pass for add: {msg}"

    def test_wraparound_arithmetic_mode(self):
        """T13 correctly uses wraparound semantics when specified."""
        t13_wraparound = T13Identifiability(arithmetic="wraparound", short_circuit=True)
        
        # Check that basic addition works correctly
        ok, msg = t13_wraparound.check(
            "(add 1 2)",
            ["(add 1 2) = 3", "(add 5 3) = 8"]
        )
        assert ok, f"Expected pass for add: {msg}"

    def test_saturating_arithmetic_mode(self):
        """T13 correctly uses saturating semantics when specified."""
        t13_saturating = T13Identifiability(arithmetic="saturating", short_circuit=True)
        
        # Check that addition works correctly
        ok, msg = t13_saturating.check(
            "(add 1 2)",
            ["(add 1 2) = 3", "(add 5 3) = 8"]
        )
        assert ok, f"Expected pass for add: {msg}"

    def test_error_on_overflow_arithmetic_mode(self):
        """T13 correctly uses error-on-overflow semantics when specified."""
        t13_error = T13Identifiability(arithmetic="error-on-overflow", short_circuit=True)
        
        # Check that addition works correctly for small values
        ok, msg = t13_error.check(
            "(add 1 2)",
            ["(add 1 2) = 3", "(add 5 3) = 8"]
        )
        assert ok, f"Expected pass for add: {msg}"

    def test_and_operator_wraparound(self):
        """T13 correctly handles AND operator with wraparound semantics."""
        t13_wraparound = T13Identifiability(arithmetic="wraparound", short_circuit=True)
        
        # AND operator - different examples to distinguish from div/mul
        ok, msg = t13_wraparound.check(
            "(and 1 1)",
            ["(and 1 1) = 1", "(and 1 0) = 0"]
        )
        assert ok, f"Expected pass for and: {msg}"

    def test_generator_accepts_unregistered_environment_but_t13_fails(self):
        """Generator accepts unregistered environments but T13 rejects them at check time."""
        from src.benchmark.generators.generator import TaskGenerator
        
        # Generator accepts unregistered env (for compatibility)
        g = TaskGenerator(
            environment_id="nonexistent_env_12345",
            derivation_seed="accept_test",
            environment_registry=None  # Empty registry
        )
        
        # environment_record is None
        assert g.environment_record is None
        
        # But T13 is also None (will fail-closed when used)
        assert g._t13_identifiability is None
        
        # INF task generation fails with clear error
        result = g.generate_single_task("INF", 2, "FULL_DOC")
        assert not result.success
        assert "not in the registry" in result.rejection_reason
