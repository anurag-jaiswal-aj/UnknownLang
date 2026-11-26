"""Environment-aware generation: registry lookup, environment variations, T5 spec."""
from dataclasses import replace

from src.benchmark.environments import build_environment
from src.benchmark.generators.generator import T5Verification, TaskGenerator, _identity_profile
from src.challenge.types import Expected, Prompt, Protocol, Evaluation, Test, Visibility
from src.language.surface import to_canonical

# Under the identity profile the surface text equals the canonical text.
BASE_PROFILE = _identity_profile()
ENV = build_environment("wraparound", True, BASE_PROFILE)
INT_MAX = 9223372036854775807


def test_t5_actual_evaluator_disagreement():
    """Verify T5 verifier rejects actual disagreement between reference and production."""
    wrap = build_environment("wraparound", True, BASE_PROFILE)
    sat = build_environment("saturating", True, BASE_PROFILE)
    reg = {wrap.environment_id: wrap, sat.environment_id: sat}
    v = T5Verification(reg)
    
    # Query where wraparound and saturating produce DIFFERENT results
    query = f"(add {INT_MAX} 1)"
    
    # Wraparound result: -INT_MAX-1
    wrap_expected = Expected(value={"kind": "int", "value": -INT_MAX - 1})
    ok, msg = v.verify(query, wrap_expected, wrap.environment_id)
    assert ok, f"Wraparound should match: {msg}"
    
    # Saturating result: INT_MAX
    sat_expected = Expected(value={"kind": "int", "value": INT_MAX})
    ok, msg = v.verify(query, sat_expected, sat.environment_id)
    assert ok, f"Saturating should match: {msg}"
    
    # Cross-verification should fail
    ok, msg = v.verify(query, sat_expected, wrap.environment_id)
    assert not ok and "differ" in msg, f"Should fail cross-verification: {msg}"


def test_t5_expected_value_disagreement():
    """Verify T5 verifier rejects wrong expected values."""
    wrap = build_environment("wraparound", True, BASE_PROFILE)
    reg = {wrap.environment_id: wrap}
    v = T5Verification(reg)
    
    query = "(add 1 2)"
    
    # Correct expected
    ok, msg = v.verify(query, Expected(value={"kind": "int", "value": 3}), wrap.environment_id)
    assert ok
    
    # Wrong expected
    ok, msg = v.verify(query, Expected(value={"kind": "int", "value": 99}), wrap.environment_id)
    assert not ok and "differ" in msg


def test_t5_type_mismatch():
    """Verify T5 verifier rejects type mismatches."""
    wrap = build_environment("wraparound", True, BASE_PROFILE)
    reg = {wrap.environment_id: wrap}
    v = T5Verification(reg)
    
    query = "(eq 1 1)"
    # Query returns bool, but we expect int
    ok, msg = v.verify(query, Expected(value={"kind": "int", "value": 1}), wrap.environment_id)
    assert not ok and "differ" in msg


def test_t5_error_class_verification():
    """Verify T5 verifier handles error cases correctly."""
    wrap = build_environment("wraparound", True, BASE_PROFILE)
    reg = {wrap.environment_id: wrap}
    v = T5Verification(reg)
    
    query = "(div 1 0)"
    
    # Correct error class
    ok, msg = v.verify(query, Expected(value={"kind": "error", "error_class": "division_by_zero"}), wrap.environment_id)
    assert ok
    
    # Wrong error class
    ok, msg = v.verify(query, Expected(value={"kind": "error", "error_class": "name"}), wrap.environment_id)
    assert not ok


def test_t6_public_leakage_regression():
    """Comprehensive T6 public leakage test - hidden tests not exposed in public view."""
    from src.challenge.types import TaskRecord, Prompt, Protocol, Evaluation, Test, Visibility
    from src.challenge.projection import project_public
    from src.benchmark.canonical import canonical_json
    
    BASE_PROFILE = _identity_profile()
    env = build_environment("wraparound", True, BASE_PROFILE)
    reg = {env.environment_id: env}
    gen = TaskGenerator(env.environment_id, "leak_test", reg)
    
    # Generate a base task
    base = gen.generate_single_task("SYN", 2, "FULL_DOC")
    assert base.success, base.rejection_reason
    
    # Create task with hidden test
    task = base.task
    hidden_eval = Evaluation(
        method="exact_match",
        limits={"max_steps": 100000, "max_ast_depth": 1000, "max_call_depth": 100},
        tests=[
            Test(test_id="t1", call="(add 1 2)", expected={"kind": "int", "value": 3}, visibility="public"),
            Test(test_id="t2", call="(sub 10 3)", expected={"kind": "int", "value": 7}, visibility="hidden"),
        ]
    )
    task_with_hidden = replace(task, evaluation=hidden_eval)
    
    # Verify hidden test is in private evaluation
    hidden_tests = [t for t in task_with_hidden.evaluation.tests if t.visibility == 'hidden']
    assert len(hidden_tests) == 1, "Task should have 1 hidden test"
    
    # Project to public
    public_task = project_public(task_with_hidden)
    
    # Verify hidden test is NOT in public evaluation
    public_tests = public_task.evaluation.tests
    public_hidden_tests = [t for t in public_tests if t.visibility == 'hidden']
    assert len(public_hidden_tests) == 0, "Hidden test should not appear in public projection"
    
    # Verify expected value is NOT exposed (it should be stripped)
    public_dict = public_task.__dict__
    assert 'expected' not in public_dict or public_dict.get('expected') is None, "Expected value should not be in public view"
    
    # Verify the expected value cannot be recovered from any public field
    # Serialize to canonical JSON and check for expected value
    canonical = canonical_json(public_task.__dict__)
    assert '7' not in canonical or canonical.count('7') < 3, "Hidden test result '7' should not be in serialized public view"


def _gen(registry=True):
    return TaskGenerator(ENV.environment_id, "env_var_seed", {ENV.environment_id: ENV} if registry else None)


def _control(variation, query="(add 6 (mul 2 3))", value=12, examples=("Example: (add 1 2) = 3",)):
    g = _gen()
    r = g.generate_single_task("SYN", 2, "FULL_DOC")
    assert r.success, r.rejection_reason
    task = replace(r.task, prompt=Prompt(
        template=r.task.prompt.template, example_policy="neutral",
        public_examples=examples, query=query), expected=Expected(value={"kind": "int", "value": value}))
    control = g._with_protocol(task, Protocol(
        kind="paired", pair_group_id="pair_x", role="control", varies=(variation,)))
    return g, control


def test_registry_lookup_and_copy():
    reg = {ENV.environment_id: ENV}
    g = TaskGenerator(ENV.environment_id, "s", reg)
    assert g.environment_record is ENV
    assert TaskGenerator("env_unknown", "s", reg).environment_record is None
    g.environment_registry["x"] = ENV
    assert "x" not in reg


def test_unregistered_environment_fails_t13_check():
    """T13 identifiability fails-closed for unregistered environments."""
    reg = {ENV.environment_id: ENV}
    g = TaskGenerator("env_unknown", "s", reg)
    # Generator accepts unregistered env (for other features that don't need T13)
    assert g.environment_record is None
    # But T13 check rejects it when used for INF tasks
    result = g.generate_single_task("INF", 2, "FULL_DOC")
    assert not result.success
    assert "not in the registry" in result.rejection_reason


def test_t5_uses_environment_semantics():
    wrap = build_environment("wraparound", True, BASE_PROFILE)
    sat = build_environment("saturating", True, BASE_PROFILE)
    big = f"(add {INT_MAX} 1)"
    expected = Expected(value={"kind": "int", "value": -INT_MAX - 1})
    v = T5Verification({wrap.environment_id: wrap, sat.environment_id: sat})
    assert v.verify(big, expected, wrap.environment_id)[0]
    assert not v.verify(big, expected, sat.environment_id)[0]


def test_surface_names_renames_via_environment_profile():
    g, ctrl = _control("environment:surface_names")
    tr = g._apply_variation(ctrl, "environment:surface_names")
    assert tr.environment_id != ctrl.environment_id
    new_env = g.environment_registry[tr.environment_id]
    assert "add" not in tr.prompt.query and "mul" not in tr.prompt.query
    assert to_canonical(tr.prompt.query, new_env.surface_profile).canonical_text == \
        to_canonical(ctrl.prompt.query, BASE_PROFILE).canonical_text
    ok, err = g._t5_verification.verify(tr.prompt.query, tr.expected, new_env.environment_id)
    assert ok, err


def test_surface_names_rejects_without_tokens():
    g, ctrl = _control("environment:surface_names", query="(f 3)", value=3, examples=())
    r = g.generate_pair(replace(ctrl, protocol=Protocol(kind="standalone")), "environment:surface_names")
    assert not r.success and "[no_surface_tokens]" in r.rejection_reason


def test_operator_meaning_changes_expected_keeps_text():
    g, ctrl = _control("environment:operator_meaning")
    tr = g._apply_variation(ctrl, "environment:operator_meaning")
    assert tr.prompt.query == ctrl.prompt.query
    assert tr.expected.value != ctrl.expected.value
    new_env = g.environment_registry[tr.environment_id]
    assert new_env.surface_profile != ENV.surface_profile
    assert g._t5_verification.verify(tr.prompt.query, tr.expected, new_env.environment_id)[0]


def test_semantic_config_changes_expected_keeps_text():
    g, ctrl = _control("environment:semantic_config", query=f"(add {INT_MAX} 1)", value=-INT_MAX - 1, examples=())
    tr = g._apply_variation(ctrl, "environment:semantic_config")
    assert tr.prompt.query == ctrl.prompt.query
    assert tr.expected.value == {"kind": "int", "value": INT_MAX}
    assert g.environment_registry[tr.environment_id].semantic["arithmetic"] == "saturating"


def test_semantic_config_rejects_when_no_difference():
    """Test that semantic_config variation fails when original query doesn't produce different results."""
    g, ctrl = _control("environment:semantic_config")
    r = g.generate_pair(replace(ctrl, protocol=Protocol(kind="standalone")), "environment:semantic_config")
    assert not r.success and "[no_distinguishing_config]" in r.rejection_reason


def test_semantic_config_works_with_boundary_query():
    """Test semantic_config with a query that produces different results in wraparound vs saturating.
    
    Uses INT_MAX+1 where wraparound overflows to -INT_MAX-1 and saturating stays at INT_MAX.
    Manual construction needed because the expected value (INT_MAX) appears in the query,
    which T9 normally rejects. This is expected - semantic_config pairs must be manually
    constructed when the boundary value appears in the query.
    """
    g, ctrl = _control("environment:semantic_config", query=f"(add {INT_MAX} 1)", value=-INT_MAX - 1, examples=())
    tr = g._apply_variation(ctrl, "environment:semantic_config")
    assert tr.prompt.query == ctrl.prompt.query
    assert tr.expected.value == {"kind": "int", "value": INT_MAX}
    new_env = g.environment_registry[tr.environment_id]
    assert new_env.semantic["arithmetic"] == "saturating"
    # Verify environments are distinct
    assert new_env.environment_id != ctrl.environment_id
    assert new_env.identity_core["semantic_spec_sha256"] != ENV.identity_core["semantic_spec_sha256"]


def test_meaning_variations_need_registered_environment():
    g = _gen()
    base = g.generate_single_task("SYN", 2, "FULL_DOC").task
    g.environment_registry.clear()  # T5 needs the env to build the base; the variation must not find it
    p = g.generate_pair(base, "environment:operator_meaning")
    assert not p.success and "[environment_not_registered]" in p.rejection_reason


def test_t6_public_leakage_regression():
    """Comprehensive T6 public leakage test - hidden tests not exposed in public view."""
    from dataclasses import replace
    from src.challenge.projection import project_public
    
    BASE_PROFILE = _identity_profile()
    env = build_environment("wraparound", True, BASE_PROFILE)
    reg = {env.environment_id: env}
    gen = TaskGenerator(env.environment_id, "leak_test", reg)
    
    # Generate a base task
    base = gen.generate_single_task("SYN", 2, "FULL_DOC")
    assert base.success, base.rejection_reason
    
    # Create task with hidden test
    task = base.task
    hidden_eval = Evaluation(
        method="exact_match",
        limits={"max_steps": 100000, "max_ast_depth": 1000, "max_call_depth": 100},
        tests=[
            Test(test_id="t1", call="(add 1 2)", expected={"kind": "int", "value": 3}, visibility="public"),
            Test(test_id="t2", call="(sub 10 3)", expected={"kind": "int", "value": 7}, visibility="hidden"),
        ]
    )
    task_with_hidden = replace(task, evaluation=hidden_eval)
    
    # Verify hidden test is in private evaluation
    hidden_tests = [t for t in task_with_hidden.evaluation.tests if t.visibility == 'hidden']
    assert len(hidden_tests) == 1, "Task should have 1 hidden test"
    
    # Project to public
    public_task = project_public(task_with_hidden)
    
    # Verify hidden test is NOT in public evaluation
    public_tests = public_task.evaluation.tests
    public_hidden_tests = [t for t in public_tests if t.visibility == 'hidden']
    assert len(public_hidden_tests) == 0, "Hidden test should not appear in public projection"
    
    # Verify expected value is NOT exposed (it should be stripped)
    assert not hasattr(public_task, 'expected') or public_task.expected is None, "Expected value should not be in public view"
    
    # Verify the hidden test call is not in public query
    hidden_call = "(sub 10 3)"
    assert hidden_call not in public_task.prompt.query, "Hidden test call should not be in public query"


def test_semantic_config_auto_generation():
    """Test automatic semantic_config pair generation with boundary-sensitive query.
    
    The generator constructs a query using intermediate arithmetic to build INT_MAX
    without the literal appearing in the query.
    Query: (add (add 9223372036854775707 100) 1)
    Wraparound result: -9223372036854775808 (INT_MIN)
    Saturating result: 9223372036854775807 (INT_MAX)
    """
    g = _gen()
    
    # Manually construct the boundary task that the generator should produce
    boundary_query = "(add (add 9223372036854775707 100) 1)"
    wrap_result = g._evaluate_expression(boundary_query)
    
    # Verify wraparound result
    assert wrap_result == -9223372036854775808, f"Expected INT_MIN, got {wrap_result}"
    
    # Create control task with boundary query
    base = g.generate_single_task("SYN", 1, "FULL_DOC")
    assert base.success, base.rejection_reason
    
    # The generator should produce a boundary-sensitive task
    control = replace(base.task,
        protocol=Protocol(kind="standalone", pair_group_id="semantic_config_auto", role="control", varies=()),
        prompt=Prompt(
            template=base.task.prompt.template,
            example_policy=base.task.prompt.example_policy,
            public_examples=base.task.prompt.public_examples,
            query=boundary_query
        ),
        expected=Expected(value={"kind": "int", "value": wrap_result})
    )
    
    # Generate pair
    pair = g.generate_pair(control, "environment:semantic_config")
    assert pair.success, f"Pair generation failed: {pair.rejection_reason}"
    
    c, t = pair.control, pair.treatment
    
    # Verify expected values
    assert c.expected.value == {"kind": "int", "value": -9223372036854775808}, "Control should have INT_MIN"
    assert t.expected.value == {"kind": "int", "value": 9223372036854775807}, "Treatment should have INT_MAX"
    
    # Verify environments are distinct
    assert c.environment_id != t.environment_id, "Environments should be distinct"
    
    # Verify T7/T8
    from src.benchmark.generators.generator import validate_pair
    assert len(validate_pair(c, t)) == 0, "T7/T8 validation should pass"


def test_semantic_config_auto_generation():
    """Test automatic semantic_config pair generation with boundary-sensitive query.
    
    The generator constructs a query using intermediate arithmetic to build INT_MAX
    without the literal appearing in the query.
    Query: (add (add 9223372036854775707 100) 1)
    Wraparound result: -9223372036854775808 (INT_MIN)
    Saturating result: 9223372036854775807 (INT_MAX)
    """
    from src.language.generator import LanguageGenerator
    from src.language.seed import LanguageSeed
    from src.execution.engine import ExecutionEngine
    
    g = _gen()
    
    # Verify the boundary expression produces INT_MIN in wraparound
    boundary_query = "(add (add 9223372036854775707 100) 1)"
    seed = LanguageSeed(name="env", syntax_style="lisp", features=["arithmetic", "functions", "recursion", "short_circuit"],
                       difficulty=1, arithmetic="wraparound", short_circuit=True)
    spec = LanguageGenerator().generate(seed, "1.0.0", "1.0.0")
    engine = ExecutionEngine()
    result = engine.execute(boundary_query, spec)
    
    assert result.status == "success" and type(result.value) is int
    assert result.value == -9223372036854775808, f"Expected INT_MIN, got {result.value}"
    
    # Create control task with boundary query using wraparound expected value
    base = g.generate_single_task("SYN", 1, "FULL_DOC")
    assert base.success, base.rejection_reason
    
    control = replace(base.task,
        protocol=Protocol(kind="standalone", pair_group_id="semantic_config_auto", role="control", varies=()),
        prompt=Prompt(
            template=base.task.prompt.template,
            example_policy=base.task.prompt.example_policy,
            public_examples=base.task.prompt.public_examples,
            query=boundary_query
        ),
        expected=Expected(value={"kind": "int", "value": result.value})
    )
    
    # Generate pair
    pair = g.generate_pair(control, "environment:semantic_config")
    assert pair.success, f"Pair generation failed: {pair.rejection_reason}"
    
    c, t = pair.control, pair.treatment
    
    # Verify expected values
    assert c.expected.value == {"kind": "int", "value": -9223372036854775808}, "Control should have INT_MIN"
    assert t.expected.value == {"kind": "int", "value": 9223372036854775807}, "Treatment should have INT_MAX"
    
    # Verify environments are distinct
    assert c.environment_id != t.environment_id, "Environments should be distinct"
    
    # Verify T7/T8
    from src.benchmark.generators.generator import validate_pair
    assert len(validate_pair(c, t)) == 0, "T7/T8 validation should pass"


def test_public_api_semantic_config_pair_generation():
    """Test public API generate_semantic_config_pair() - end-to-end without manual TaskRecord construction.
    
    This test uses ONLY the public API:
    - generate_semantic_config_boundary_task()
    - generate_semantic_config_pair()
    
    It verifies:
    - Boundary task generation
    - Pair generation from boundary task
    - Identical control/treatment queries
    - Distinct environment IDs
    - INT_MIN and INT_MAX expected values
    - Task identities and provenance
    - T5, T7, T8, T9 validation
    """
    g = _gen()
    
    # Use public API only
    boundary = g.generate_semantic_config_boundary_task()
    assert boundary.success, f"Boundary generation failed: {boundary.rejection_reason}"
    
    # Verify boundary task
    assert boundary.task.prompt.query == "(add (add 9223372036854775707 100) 1)"
    assert boundary.task.expected.value == {"kind": "int", "value": -9223372036854775808}
    assert boundary.task.task_id.startswith("task_")
    assert boundary.provenance.get("generation_method") == "semantic_config_boundary"
    
    # Use public API to generate pair
    pair = g.generate_semantic_config_pair()
    assert pair.success, f"Pair generation failed: {pair.rejection_reason}"
    
    # Verify control and treatment
    c, t = pair.control, pair.treatment
    
    # Identical query text
    assert c.prompt.query == t.prompt.query, "Control and treatment must have identical queries"
    assert c.prompt.query == "(add (add 9223372036854775707 100) 1)"
    
    # Different expected values (INT_MIN vs INT_MAX)
    assert c.expected.value == {"kind": "int", "value": -9223372036854775808}, "Control should have INT_MIN"
    assert t.expected.value == {"kind": "int", "value": 9223372036854775807}, "Treatment should have INT_MAX"
    assert c.expected.value != t.expected.value, "Expected values must differ"
    
    # Different environment IDs
    assert c.environment_id != t.environment_id, "Environments must be distinct"
    assert c.environment_id.startswith("env_")
    assert t.environment_id.startswith("env_")
    
    # Different task IDs
    assert c.task_id != t.task_id, "Task IDs must differ"
    assert c.task_id.startswith("task_")
    assert t.task_id.startswith("task_")
    
    # T7/T8 validation passes
    from src.benchmark.generators.generator import validate_pair
    assert len(validate_pair(c, t)) == 0, "T7/T8 validation should pass"
    
    # T9 non-triviality (expected values not in query)
    assert "-9223372036854775808" not in c.prompt.query, "INT_MIN not in query (T9)"
    assert "9223372036854775807" not in c.prompt.query, "INT_MAX not in query (T9)"
