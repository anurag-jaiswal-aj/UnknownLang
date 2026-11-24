"""Independence of the reference evaluator, and differential tests against production
(Wave 1C.14, stage 6).

``src.oracle.reference_evaluator.ReferenceEvaluator`` is the project's test oracle. It is only
worth anything if it shares no evaluation logic with the production path, so independence is
enforced three ways: statically (its imports), dynamically (what importing it loads) and by
behavior (breaking one implementation does not affect the other).

The differential tests then compare ``ExecutionEngine`` (the iterative-backed facade) with the
oracle on hand-written and seeded-random programs across every arithmetic mode and both
boolean modes. They compare status, value and value type, NOT step counts: the oracle's legacy
counters are not the canonical resource-limit contract.
"""

import ast
import random
import subprocess
import sys
from pathlib import Path

import pytest

import src.oracle.reference_evaluator as reference_mod
from src.execution.engine import ExecutionEngine
from src.execution.iterative_evaluator import IterativeEvaluator
from src.execution.types import ExecutionResult
from src.language.generator import LanguageGenerator
from src.language.seed import LanguageSeed
from src.oracle.reference_evaluator import ReferenceEvaluator

REPO_ROOT = Path(__file__).resolve().parents[1]
INT64_MIN, INT64_MAX = -(2 ** 63), 2 ** 63 - 1
MODES = ["wraparound", "saturating", "error-on-overflow"]
CONFIGS = [(m, sc) for m in MODES for sc in (True, False)]


def make_lang(mode="wraparound", short_circuit=True):
    return LanguageGenerator().generate(LanguageSeed(
        name="OracleLang", syntax_style="lisp", features=["recursion", "functions"],
        difficulty=2, arithmetic=mode, short_circuit=short_circuit))


# ============================================================================
# STATIC INDEPENDENCE: what the reference module imports
# ============================================================================

ALLOWED_IMPORTS = {
    "__future__", "math", "dataclasses", "typing", "lark",
    "src.language.generator", "src.language.semantics",   # language definitions / parser inputs
    "src.execution.types",                                # shared DATA types only
}
FORBIDDEN_FRAGMENTS = ("src.execution.engine", "src.execution.iterative_evaluator")


def imported_modules(path: str) -> set:
    tree = ast.parse(Path(path).read_text())
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "relative imports are not allowed in the oracle"
            found.add(node.module)
    return found


class TestStaticIndependence:
    def test_reference_imports_only_allowed_modules(self):
        modules = imported_modules(reference_mod.__file__)
        assert modules <= ALLOWED_IMPORTS, f"unexpected imports: {sorted(modules - ALLOWED_IMPORTS)}"

    def test_reference_never_names_a_production_evaluation_module(self):
        modules = imported_modules(reference_mod.__file__)
        for forbidden in FORBIDDEN_FRAGMENTS:
            assert not any(m.startswith(forbidden) for m in modules), forbidden
        assert "src.execution" not in modules, "import the types module explicitly, not the package"

    def test_the_only_execution_import_is_the_shared_types_module(self):
        modules = {m for m in imported_modules(reference_mod.__file__) if m.startswith("src.execution")}
        assert modules == {"src.execution.types"}

    def test_shared_types_module_has_no_project_imports(self):
        import src.execution.types as types_mod
        assert not {m for m in imported_modules(types_mod.__file__) if m.startswith(("src", "tests"))}

    def test_reference_source_contains_no_reference_to_the_iterative_design(self):
        source = Path(reference_mod.__file__).read_text()
        executable = "\n".join(line for line in source.splitlines()
                               if not line.strip().startswith(("#", "*", '"""')))
        for token in ("FrameType", "Frame(", "result_stack", "_process_frame", "IterativeEvaluator"):
            assert token not in executable, token


# ============================================================================
# DYNAMIC INDEPENDENCE: what importing it loads
# ============================================================================

def fresh_python(code):
    return subprocess.run([sys.executable, "-c", code], cwd=REPO_ROOT, capture_output=True, text=True)


class TestDynamicIndependence:
    def test_importing_the_reference_loads_no_production_execution_module(self):
        proc = fresh_python(
            "import sys\n"
            "import src.oracle.reference_evaluator\n"
            "loaded = [m for m in sys.modules if m in ('src.execution.engine',"
            " 'src.execution.iterative_evaluator')]\n"
            "assert not loaded, loaded\n"
            "assert 'src.execution.types' in sys.modules\n")
        assert proc.returncode == 0, proc.stderr

    def test_the_reference_runs_end_to_end_without_production_modules_present(self):
        proc = fresh_python(
            "import sys\n"
            "from src.oracle.reference_evaluator import ReferenceEvaluator\n"
            "from src.language.generator import LanguageGenerator\n"
            "from src.language.seed import LanguageSeed\n"
            "spec = LanguageGenerator().generate(LanguageSeed(name='L', syntax_style='lisp',"
            " features=['arithmetic','functions'], difficulty=1, arithmetic='wraparound', short_circuit=True))\n"
            "r = ReferenceEvaluator().execute('(def f (x) (add x 1))\\n(f 41)', spec)\n"
            "assert (r.status, r.value) == ('success', 42), r\n"
            "bad = [m for m in sys.modules if m in ('src.execution.engine','src.execution.iterative_evaluator')]\n"
            "assert not bad, bad\n")
        assert proc.returncode == 0, proc.stderr

    def test_the_reference_returns_the_shared_result_type(self):
        r = ReferenceEvaluator().execute("(add 1 2)", make_lang())
        assert type(r) is ExecutionResult
        assert (r.status, r.value) == ("success", 3)


# ============================================================================
# BEHAVIORAL INDEPENDENCE: breaking one does not affect the other
# ============================================================================

class TestBehavioralIndependence:
    PROGRAMS = ["(add 1 2)", "(def f (x) (mul x 3))\n(f 4)", "(if (and true false) 1 2)"]

    def test_the_reference_does_not_delegate_to_the_production_path(self, monkeypatch):
        def boom(*a, **k):
            raise AssertionError("reference reached production code")
        for name in ("execute", "_run", "_process_frame", "_validate_ast_depth", "_new_context"):
            monkeypatch.setattr(IterativeEvaluator, name, boom)
        monkeypatch.setattr(ExecutionEngine, "execute", boom)
        for program in self.PROGRAMS:
            assert ReferenceEvaluator().execute(program, make_lang()).status == "success"

    def test_production_does_not_delegate_to_the_reference(self, monkeypatch):
        def boom(*a, **k):
            raise AssertionError("production reached the oracle")
        monkeypatch.setattr(ReferenceEvaluator, "execute", boom)
        for name in ("_eval", "_eval_program", "_eval_user_func", "_apply_division"):
            monkeypatch.setattr(ReferenceEvaluator, name, boom)
        for program in self.PROGRAMS:
            assert ExecutionEngine().execute(program, make_lang()).status == "success"
            assert IterativeEvaluator().execute(program, make_lang()).status == "success"

    def test_a_deliberately_broken_reference_is_detected_by_the_differential_check(self, monkeypatch):
        """The comparison must be able to fail: sabotage the oracle's division and it must show."""
        monkeypatch.setattr(ReferenceEvaluator, "_apply_division", lambda self, a, b, mode: 12345)
        lang = make_lang()
        ref = ReferenceEvaluator().execute("(div 10 3)", lang)
        prod = ExecutionEngine().execute("(div 10 3)", lang)
        assert (ref.value, prod.value) == (12345, 3)

    def test_the_reference_is_not_the_canonical_resource_accounting(self):
        """It has no AST-depth enforcement, so a program the production path rejects at
        depth 1001 is not rejected by it for that reason. Resource limits are validated on the
        production path against hand-derived contracts, not by comparison with the oracle."""
        deep = "(add 1 " * 1001 + "1" + ")" * 1001
        assert ExecutionEngine().execute(deep, make_lang()).status == "ast_depth_exceeded"
        assert ReferenceEvaluator().execute(deep, make_lang()).status != "ast_depth_exceeded"


# ============================================================================
# DIFFERENTIAL: hand-written corpus
# ============================================================================

HAND_CORPUS = [
    "1", "-5", "true", "(add 1 2)", "(sub 1 2)", "(mul -3 4)", "(add 1 (mul 2 3))",
    "(div 7 2)", "(div -7 2)", "(div 7 -2)", "(div -7 -2)",
    "(mod 7 2)", "(mod -7 2)", "(mod 7 -2)", "(mod -7 -2)", "(div 1 0)", "(mod 1 0)",
    f"(add {INT64_MAX} 1)", f"(sub {INT64_MIN} 1)", f"(mul {INT64_MAX} 2)", f"(mul {INT64_MIN} -1)",
    f"(div {INT64_MIN} -1)", f"(mod {INT64_MIN} -1)", f"(div {INT64_MAX} -1)",
    "(and true false)", "(or false true)", "(and false (div 1 0))", "(or true (div 1 0))",
    "(and true (div 1 0))", "(and 1 true)", "(or false 1)", "(not true)", "(not 1)",
    "(if true 1 (div 1 0))", "(if false (div 1 0) 2)", "(if 1 2 3)",
    "(def f (x) (add x 1))\n(f 41)", "(def f (x) x)\n(f 1 2)", "(def f (x y) x)\n(f 1)",
    "(def f (y) (add x y))\n(def g (x) (f 1))\n(g 5)",
    "(def r (n) (if (eq n 0) 0 (add n (r (sub n 1)))))\n(r 30)",
    "(nope 1)", "x", "(add 1",
]


def key(r):
    return (r.status, r.value, type(r.value))


class TestDifferentialHandCorpus:
    @pytest.mark.parametrize("mode,sc", CONFIGS, ids=[f"{m}-{'sc' if s else 'eager'}" for m, s in CONFIGS])
    def test_production_matches_the_oracle(self, mode, sc):
        lang = make_lang(mode, sc)
        engine, oracle = ExecutionEngine(), ReferenceEvaluator()
        mismatches = [(p, key(engine.execute(p, lang)), key(oracle.execute(p, lang)))
                      for p in HAND_CORPUS if key(engine.execute(p, lang)) != key(oracle.execute(p, lang))]
        assert not mismatches, "\n".join(map(repr, mismatches))

    def test_iterative_evaluator_and_facade_agree_exactly(self):
        lang = make_lang()
        for p in HAND_CORPUS:
            assert ExecutionEngine().execute(p, lang) == IterativeEvaluator().execute(p, lang), p


# ============================================================================
# DIFFERENTIAL: seeded random programs
# ============================================================================

LITERALS = ["0", "1", "-1", "2", "3", "7", "-7", "10", "100", "4611686018427387904",
            str(INT64_MAX), str(INT64_MIN), str(INT64_MAX - 1), str(INT64_MIN + 1)]


def gen_int(rng, depth, names):
    r = rng.random()
    if rng.random() < 0.03:
        return "true"                      # deliberate type error: bool where int expected
    if depth == 0 or r < 0.25:
        return rng.choice(names) if names and rng.random() < 0.4 else rng.choice(LITERALS)
    if r < 0.75:
        op = rng.choice(["add", "sub", "mul", "div", "mod"])
        return f"({op} {gen_int(rng, depth - 1, names)} {gen_int(rng, depth - 1, names)})"
    return f"(if {gen_bool(rng, depth - 1, names)} {gen_int(rng, depth - 1, names)} {gen_int(rng, depth - 1, names)})"


def gen_bool(rng, depth, names):
    r = rng.random()
    if rng.random() < 0.03:
        return "7"                         # deliberate type error: int where bool expected
    if depth == 0 or r < 0.2:
        return rng.choice(["true", "false"])
    if r < 0.45:
        return f"(eq {gen_int(rng, depth - 1, names)} {gen_int(rng, depth - 1, names)})"
    if r < 0.55:
        return f"(not {gen_bool(rng, depth - 1, names)})"
    op = rng.choice(["and", "or"])
    return f"({op} {gen_bool(rng, depth - 1, names)} {gen_bool(rng, depth - 1, names)})"


def gen_program(rng):
    shape = rng.choice(["expr", "expr", "function", "recursive"])
    if shape == "expr":
        return gen_int(rng, rng.randint(1, 4), [])
    if shape == "function":
        body = gen_int(rng, rng.randint(1, 3), ["a", "b"])
        return f"(def f (a b) {body})\n(f {gen_int(rng, 1, [])} {gen_int(rng, 1, [])})"
    step = gen_int(rng, rng.randint(0, 2), ["n", "acc"])
    return (f"(def r (n acc) (if (eq n 0) acc (r (sub n 1) {step})))\n"
            f"(r {rng.randint(0, 12)} {rng.choice(LITERALS)})")


PROGRAMS_PER_CONFIG = 150


class TestDifferentialRandomPrograms:
    @pytest.mark.parametrize("idx,cfg", list(enumerate(CONFIGS)),
                             ids=[f"{m}-{'sc' if s else 'eager'}" for m, s in CONFIGS])
    def test_production_matches_the_oracle_on_random_programs(self, idx, cfg):
        mode, sc = cfg
        lang = make_lang(mode, sc)
        engine, oracle = ExecutionEngine(), ReferenceEvaluator()
        rng = random.Random(20260100 + idx)                  # fixed seed: reproducible
        mismatches, statuses = [], []
        for _ in range(PROGRAMS_PER_CONFIG):
            program = gen_program(rng)
            ours, ref = engine.execute(program, lang), oracle.execute(program, lang)
            statuses.append(ours.status)
            if key(ours) != key(ref):
                mismatches.append((program, key(ours), key(ref)))
        assert not mismatches, f"{len(mismatches)} mismatches, first: {mismatches[0]!r}"
        # The generator must exercise both outcomes or the comparison proves little.
        assert statuses.count("success") >= PROGRAMS_PER_CONFIG * 0.3, statuses.count("success")
        assert statuses.count("error") >= PROGRAMS_PER_CONFIG * 0.05, statuses.count("error")

    def test_the_generator_is_deterministic(self):
        a = [gen_program(random.Random(7)) for _ in range(3)]
        b = [gen_program(random.Random(7)) for _ in range(3)]
        assert a == b

    def test_the_generator_reaches_the_overflow_boundaries(self):
        rng = random.Random(1)
        programs = " ".join(gen_program(rng) for _ in range(400))
        assert str(INT64_MAX) in programs and str(INT64_MIN) in programs and "(div" in programs
