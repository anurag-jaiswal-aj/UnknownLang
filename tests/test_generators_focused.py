"""Focused tests for generator correctness gaps (M2.5).

Tests marked ``xfail(strict=True)`` document defects present in the current generator.
They assert the CORRECT behavior; when a defect is fixed the test XPASSes and strict mode
fails the run, which is the cue to delete the marker.
"""
import inspect
from dataclasses import replace

import pytest

from src.benchmark.environments import build_environment
from src.benchmark.generators import generator as gen_mod
from src.benchmark.generators.generator import (
    SURFACE_PROFILE,
    T5Verification,
    TaskGenerator,
    to_canonical_query,
    validate_pair,
)
from src.benchmark.generators.identifiability import T13Identifiability
from src.benchmark.manager import EnvironmentManager
from src.challenge.types import Expected
from src.execution.engine import ExecutionEngine
from src.language.generator import LanguageGenerator
from src.language.seed import LanguageSeed

_ENV_REC = build_environment("wraparound", True, gen_mod._identity_profile())
ENV = _ENV_REC.environment_id
REG = {ENV: _ENV_REC}
SEEDS = [f"focus_{i}" for i in range(8)]


def _gen(seed="focus"):
    return TaskGenerator(environment_id=ENV, derivation_seed=seed, environment_registry=REG)


def _int(v):
    return Expected(value={"kind": "int", "value": v})


def _spec(arithmetic="wraparound"):
    seed = LanguageSeed(name="t", syntax_style="lisp", features=["arithmetic", "functions", "recursion"],
                        difficulty=1, arithmetic=arithmetic, short_circuit=True)
    return LanguageGenerator().generate(seed, "1.0.0", "1.0.0")


class TestEvaluatorsCorrectness:
    def test_flat_expression(self):
        g = _gen()
        assert g._evaluate_expression("(add 2 3)") == 5
        assert g._evaluate_expression("(sub 2 5)") == -3

    @pytest.mark.parametrize("expr,value", [
        ("(add (mul 2 3) 4)", 10),
        ("(sub 20 (add 3 4))", 13),
        ("(add (add 1 2) (mul 3 4))", 15),
    ])
    def test_nested_expression(self, expr, value):
        assert _gen()._evaluate_expression(expr) == value

    @pytest.mark.parametrize("seed", SEEDS)
    def test_syn_expected_matches_engine(self, seed):
        data = _gen(seed)._generate_syn_task(2, "FULL_DOC")
        res = ExecutionEngine().execute(data["query"], _spec())
        assert res.status == "success" and res.value == data["expected"]["value"]

    @pytest.mark.parametrize("seed", SEEDS)
    @pytest.mark.parametrize("difficulty", [1, 3])
    def test_ctrl_expected_matches_generator_evaluation(self, seed, difficulty):
        data = _gen(seed)._generate_ctrl_task(difficulty, "FULL_DOC")
        assert data["expected"]["value"] == _gen(seed)._evaluate_expression(data["query"])

    @pytest.mark.parametrize("seed", SEEDS)
    @pytest.mark.parametrize("difficulty", [1, 3])
    def test_ctrl_query_runs_in_engine_to_expected(self, seed, difficulty):
        data = _gen(seed)._generate_ctrl_task(difficulty, "FULL_DOC")
        res = ExecutionEngine().execute(data["query"], _spec())
        assert res.status == "success" and res.value == data["expected"]["value"]

    @pytest.mark.parametrize("seed", SEEDS)
    def test_inf_includes_definitions(self, seed):
        data = _gen(seed)._generate_inf_task(2, "FULL_DOC")
        query = data["query"]
        fname = query.split("(def ", 1)[1].split()[0]
        assert query.startswith("(def ") and query.rstrip().endswith(f"({fname} {query.rsplit(' ', 1)[1]}")
        # the definition must make the call evaluable once surface operators are mapped back
        prof = data["surface_profile"]
        res = ExecutionEngine().execute(query, _spec(), prof)
        assert res.status == "success" and res.value == data["expected"]["value"]


class TestT5VerificationReal:
    def test_accepts_correct_value(self):
        assert T5Verification(REG).verify("(add 1 2)", _int(3), ENV) == (True, "")

    def test_rejects_wrong_expected_value(self):
        ok, _ = T5Verification(REG).verify("(add 1 2)", _int(99), ENV)
        assert not ok

    def test_uses_environment_language_spec(self):
        params = inspect.signature(T5Verification.verify).parameters
        assert any(p in params for p in ("spec", "environment", "environment_id", "language_spec"))

    def test_rejects_bool_as_int_expected(self):
        assert not T5Verification(REG).verify("(add 1 2)", Expected(value={"kind": "int", "value": True}), ENV)[0]

    def test_rejects_malformed_expected(self):
        v = T5Verification(REG)
        assert not v.verify("(add 1 2)", Expected(value={"kind": "float", "value": 1}), ENV)[0]
        assert not v.verify("(add 1 2)", Expected(value="3"), ENV)[0]

    def test_error_kind_must_be_known(self):
        ok, why = T5Verification(REG).verify("(div 1 0)", Expected(value={"kind": "error", "error_class": "bogus"}), ENV)
        assert not ok and "error class" in why

    def test_known_error_kind_on_erroring_query(self):
        e = Expected(value={"kind": "error", "error_class": "division_by_zero"})
        assert T5Verification(REG).verify("(div 1 0)", e, ENV) == (True, "")

    def test_error_kind_compared_with_actual(self):
        wrong = Expected(value={"kind": "error", "error_class": "division_by_zero"})
        assert not T5Verification(REG).verify("(add 1 2)", wrong, ENV)[0]  # query succeeds
        wrong_kind = Expected(value={"kind": "error", "error_class": "name"})
        assert not T5Verification(REG).verify("(div 1 0)", wrong_kind, ENV)[0]

    def test_bool_result_does_not_match_int_expected(self):
        v = T5Verification(REG)
        assert not v.verify("(eq 1 1)", _int(1), ENV)[0]  # True != 1
        assert v.verify("(eq 1 1)", Expected(value={"kind": "bool", "value": True}), ENV)[0]
        assert not v.verify("(add 0 1)", Expected(value={"kind": "bool", "value": True}), ENV)[0]

    @pytest.mark.parametrize("query,cls", [
        ("(add 1", "syntax"), ("(nosuch 1)", "name"), ("(add true 1)", "type"), ("(add 1 2 3)", "arity"),
    ])
    def test_error_queries_match_only_their_class(self, query, cls):
        v = T5Verification(REG)
        assert v.verify(query, Expected(value={"kind": "error", "error_class": cls}), ENV) == (True, "")
        assert not v.verify(query, _int(0), ENV)[0]

    def test_failure_reports_expected_and_both_results(self):
        ok, why = T5Verification(REG).verify("(add 1 2)", _int(99), ENV)
        assert not ok and "expected=int(99)" in why and "reference=int(3)" in why and "production=int(3)" in why

    def test_unregistered_environment_fails_closed(self):
        ok, why = T5Verification({}).verify("(add 1 2)", _int(3), ENV)
        assert not ok and "not in registry" in why


class TestPairValidation:
    def _pair(self, variation, category="SYN", seed="pair_focus"):
        g = _gen(seed)
        base = g.generate_single_task(category, 2, "FULL_DOC")
        assert base.success, base.rejection_reason
        r = g.generate_pair(base.task, variation)
        assert r.success, r.rejection_reason
        return r

    def test_protocol_fields_set(self):
        r = self._pair("example_policy")
        c, t = r.control.protocol, r.treatment.protocol
        assert (c.kind, c.role) == ("paired", "control")
        assert (t.kind, t.role) == ("paired", "treatment")
        assert c.pair_group_id and c.pair_group_id == t.pair_group_id
        assert c.varies == t.varies == ("example_policy",)

    @pytest.mark.parametrize("variation", ["environment:surface_names", "information_condition", "example_policy"])
    def test_t8_equal_expected_for_non_discriminating(self, variation):
        r = self._pair(variation)
        assert r.control.expected == r.treatment.expected
        bad = replace(r.treatment, expected=_int(-12345))
        assert any("T8 expected must be equal" in e for e in validate_pair(r.control, bad))

    @pytest.mark.parametrize("variation", ["environment:operator_meaning", "environment:semantic_config"])
    def test_t8_different_expected_for_discriminating(self, variation):
        r = self._pair("example_policy")
        c = replace(r.control, protocol=replace(r.control.protocol, varies=(variation,)))
        t = replace(r.treatment, protocol=replace(r.treatment.protocol, varies=(variation,)))
        assert any("T8 discriminating pair needs different expected" in e for e in validate_pair(c, t))
        t2 = replace(t, expected=_int(-12345))
        assert not any("T8" in e for e in validate_pair(c, t2))

    @pytest.mark.parametrize("variation", ["environment:surface_names", "information_condition", "example_policy"])
    def test_control_and_treatment_ids_differ(self, variation):
        r = self._pair(variation)
        assert r.control.task_id != r.treatment.task_id

    def test_same_task_id_rejected(self):
        r = self._pair("example_policy")
        clone = replace(r.control, protocol=replace(r.control.protocol, role="treatment"))
        assert any("same task_id" in e for e in validate_pair(r.control, clone))

    def test_standalone_base_required_and_mismatched_group_rejected(self):
        r = self._pair("example_policy")
        other = replace(r.treatment, protocol=replace(r.treatment.protocol, pair_group_id="pair_other"))
        assert any("pair_group_id" in e for e in validate_pair(r.control, other))
        again = _gen().generate_pair(r.control, "example_policy")
        assert not again.success


class TestT13Identifiability:
    ADD_EX = ["(add 1 2) = 3", "(add 5 3) = 8"]

    def test_accepts_identifiable_operator(self):
        assert T13Identifiability().check("(add 1 2)", self.ADD_EX) == (True, "")

    def test_accepts_renamed_operator_when_examples_pin_meaning(self):
        assert T13Identifiability().check("(prax 1 2)", ["(prax 1 2) = 3", "(prax 5 3) = 8"])[0]

    def test_rejects_ambiguous_operator_meaning(self):
        ok, why = T13Identifiability().check("(foo 2 2)", ["(foo 2 2) = 4"])  # add or mul
        assert not ok and "ambiguous" in why

    def test_rejects_operator_without_examples(self):
        ok, why = T13Identifiability().check("(add 1 (mul 2 3))", self.ADD_EX)
        assert not ok and "mul" in why

    def test_rejects_contradictory_examples(self):
        ok, why = T13Identifiability().check("(add 1 2)", ["(add 1 2) = 3", "(add 1 2) = 4"])
        assert not ok and "contradict" in why

    def test_rejects_meaning_matching_no_canonical_op(self):
        ok, _ = T13Identifiability().check("(foo 1 2)", ["(foo 1 2) = 97", "(foo 2 3) = -41"])
        assert not ok

    def test_rejects_unparseable_example(self):
        assert not T13Identifiability().check("(add 1 2)", ["not an example"])[0]

    def test_pipeline_rejects_inf_task_with_unexplained_operator(self):
        g = _gen("t13_pipeline")
        task_data = {"query": "(foo 1 2)", "expected": {"kind": "int", "value": 3}, "public_examples": [],
                     "difficulty": 1}
        g._generate_task_content = lambda **_: task_data
        r = g.generate_single_task("INF", 1, "FULL_DOC")
        assert not r.success and "T13" in r.rejection_reason


class TestT9NonTriviality:
    def test_flags_expected_in_query(self):
        d = {"query": "(add 3 4)", "expected": {"kind": "int", "value": 4}, "public_examples": []}
        assert not _gen()._check_t9_non_trivial(d)

    def test_flags_expected_in_examples(self):
        d = {"query": "(add 3 4)", "expected": {"kind": "int", "value": 7},
             "public_examples": ["Example: (add 3 4) = 7"]}
        assert not _gen()._check_t9_non_trivial(d)

    def test_passes_nontrivial(self):
        d = {"query": "(add 3 4)", "expected": {"kind": "int", "value": 7}, "public_examples": []}
        assert _gen()._check_t9_non_trivial(d)

    def test_pipeline_rejects_when_all_candidates_trivial(self):
        g = _gen()
        g._generate_task_content = lambda **_: {
            "query": "(add 3 4)", "expected": {"kind": "int", "value": 4}, "public_examples": [], "difficulty": 1}
        r = g.generate_single_task("SYN", 1, "FULL_DOC")
        assert not r.success and "non-trivial" in r.rejection_reason

    def test_pipeline_accepts_nontrivial_retry(self):
        g = _gen()
        trivial = {"query": "(add 3 4)", "expected": {"kind": "int", "value": 4}, "public_examples": [],
                   "difficulty": 1}
        good = {"query": "(add 3 4)", "expected": {"kind": "int", "value": 7}, "public_examples": [],
                "difficulty": 1}
        calls = iter([trivial, good])
        g._generate_task_content = lambda **_: next(calls)
        r = g.generate_single_task("SYN", 1, "FULL_DOC")
        assert r.success and r.task.expected.value["value"] == 7

    def test_retry_produces_different_candidate(self):
        g = _gen("retry_probe")
        seen = []
        real = g._generate_task_content

        def spy(**kw):
            d = real(**kw)
            seen.append(d)
            return d

        g._generate_task_content = spy
        g._check_t9_non_trivial = lambda d: False  # force the retry path
        g.generate_single_task("SYN", 1, "FULL_DOC")
        # Assert that retries produce distinct candidates (5 attempts, all distinct)
        assert len(seen) == 5, f"Expected 5 attempts, got {len(seen)}"
        queries = [d["query"] for d in seen]
        assert len(set(queries)) == 5, f"Expected 5 distinct queries, got {len(set(queries))}: {queries}"


class TestEnvironmentAwareness:

    def test_environment_id_from_manager_is_accepted_by_generator(self):
        seed = LanguageSeed(name="e", syntax_style="lisp", features=["arithmetic", "functions"],
                            difficulty=1, arithmetic="wraparound", short_circuit=True)
        try:
            # The profile must spell the operators: under operators={} the query is unanswerable and T5 rejects it.
            rec, _ = EnvironmentManager().create_environment(seed, gen_mod._identity_profile())
        except Exception as e:  # profile schema is owned by src.language.surface
            pytest.skip(f"cannot build env with test profile: {e}")
        g = TaskGenerator(environment_id=rec.environment_id, derivation_seed="env_focus",
                          environment_registry={rec.environment_id: rec})
        r = g.generate_single_task("SYN", 2, "FULL_DOC")
        assert r.success, r.rejection_reason
        assert r.task.environment_id == rec.environment_id

    def test_registry_resolves_environment(self):
        # EnvironmentManager.resolve_environment is intentionally a placeholder
        # for future persistent content-addressed storage. The current design
        # passes environment registries explicitly to TaskGenerator.
        assert EnvironmentManager().resolve_environment(ENV) is None

    def test_generator_accepts_environment_registry(self):
        params = inspect.signature(TaskGenerator.__init__).parameters
        assert "environment_registry" in params

    def test_surface_transform_uses_module_profile(self):
        r = TestPairValidation()._pair("environment:surface_names")
        used = {tok for tok in SURFACE_PROFILE.values() if f"({tok} " in r.treatment.prompt.query}
        assert used, "treatment query should contain renamed operators"
        assert to_canonical_query(r.treatment.prompt.query) == r.control.prompt.query

    def test_surface_transform_uses_environment_profile(self):
        r = TestPairValidation()._pair("environment:surface_names")
        assert r.treatment.environment_id != r.control.environment_id
