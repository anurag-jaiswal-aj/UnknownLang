"""ExecutionEngine compatibility facade (Wave 1C.14, stage 6).

``ExecutionEngine`` must keep its public API while delegating to the iterative evaluator:

    ExecutionEngine(*, max_steps=None, max_ast_depth=None, max_call_depth=None)
    ExecutionEngine().execute(program_text, language_spec) -> ExecutionResult

Expected values are derived by hand from the resource-limit contract:
  (add 1 2)            3 steps, AST depth 2
  recur(k)             k + 1 simultaneously active invocations (limit 100)
  nested(n)            n calls around a literal: AST depth n + 1
"""

import dataclasses
import inspect
import subprocess
import sys
from pathlib import Path

import pytest

import src.execution as execution_pkg
import src.execution.engine as engine_mod
import src.execution.iterative_evaluator as iterative_mod
import src.execution.types as types_mod
from src.execution import ExecutionEngine, ExecutionResult
from src.language.generator import LanguageGenerator
from src.language.seed import LanguageSeed

REPO_ROOT = Path(__file__).resolve().parents[1]
RECUR = "(def recur (n)\n  (if (eq n 0)\n      0\n      (recur (sub n 1))))\n"
SHARED_CLASSES = ["ExecutionResult", "ExecutionError", "StepLimitExceeded", "AstDepthExceeded",
                  "RecursionLimitExceeded", "OutputLimitExceeded"]
SHARED_CONSTANTS = ["MIN_INT64", "MAX_INT64", "DEFAULT_MAX_STEPS", "DEFAULT_MAX_AST_DEPTH",
                    "DEFAULT_MAX_CALL_DEPTH", "DEFAULT_MAX_OUTPUT_BYTES"]
LEGACY_ENGINE_NAMES = ["ExecutionEngine", "ExecutionResult", "EvalContext", "ExecutionError",
                       "StepLimitExceeded", "RecursionLimitExceeded", "AstDepthExceeded",
                       "OutputLimitExceeded", "MIN_INT64", "MAX_INT64"]


@pytest.fixture(scope="module")
def lang():
    return LanguageGenerator().generate(LanguageSeed(
        name="FacadeLang", syntax_style="lisp", features=["recursion", "functions"],
        difficulty=2, arithmetic="wraparound", short_circuit=True))


def nested(n: int) -> str:
    return "(add 1 " * n + "1" + ")" * n


def fresh_python(code: str) -> subprocess.CompletedProcess:
    """Run ``code`` in a brand-new interpreter from the repository root."""
    return subprocess.run([sys.executable, "-c", code], cwd=REPO_ROOT, capture_output=True, text=True)


# ============================================================================
# PUBLIC API AND IMPORT COMPATIBILITY
# ============================================================================

class TestPublicImports:
    def test_package_level_exports(self):
        assert execution_pkg.__all__ == ["ExecutionEngine", "ExecutionResult"]
        assert ExecutionEngine is engine_mod.ExecutionEngine
        assert ExecutionResult is types_mod.ExecutionResult

    @pytest.mark.parametrize("name", LEGACY_ENGINE_NAMES)
    def test_every_name_importable_before_the_facade_still_importable(self, name):
        assert hasattr(engine_mod, name), f"src.execution.engine.{name} disappeared"

    def test_default_limit_constants_still_importable_from_engine(self):
        assert engine_mod.DEFAULT_MAX_STEPS == 100_000
        assert engine_mod.DEFAULT_MAX_AST_DEPTH == 1_000
        assert engine_mod.DEFAULT_MAX_CALL_DEPTH == 100

    @pytest.mark.parametrize("name", SHARED_CLASSES)
    def test_result_and_exception_types_are_single_definitions(self, name):
        assert getattr(engine_mod, name) is getattr(types_mod, name) is getattr(iterative_mod, name)

    @pytest.mark.parametrize("name", SHARED_CONSTANTS)
    def test_constants_are_shared(self, name):
        assert getattr(engine_mod, name) == getattr(types_mod, name) == getattr(iterative_mod, name)

    def test_exception_hierarchy_is_intact(self):
        for name in ["StepLimitExceeded", "AstDepthExceeded", "OutputLimitExceeded", "RecursionLimitExceeded"]:
            assert issubclass(getattr(types_mod, name), types_mod.ExecutionError)

    def test_eval_context_is_the_iterative_one_and_keeps_its_old_usage(self):
        assert engine_mod.EvalContext is iterative_mod.EvalContext
        assert engine_mod.EvalContext(max_steps=10).max_steps == 10
        assert engine_mod.EvalContext(max_call_depth=5).max_call_depth == 5

    def test_unknown_package_attribute_raises_attribute_error(self):
        with pytest.raises(AttributeError):
            execution_pkg.does_not_exist  # noqa: B018

    def test_dir_lists_the_lazy_exports(self):
        assert {"ExecutionEngine", "ExecutionResult"} <= set(dir(execution_pkg))


class TestResultContract:
    def test_execute_returns_the_shared_result_type(self, lang):
        result = ExecutionEngine().execute("(add 1 2)", lang)
        assert type(result) is types_mod.ExecutionResult
        assert (result.status, result.value, result.output, result.error_message) == ("success", 3, "", "")

    def test_to_dict_has_the_four_established_keys(self, lang):
        d = ExecutionEngine().execute("(add 1 2)", lang).to_dict()
        assert d == {"status": "success", "value": 3, "output": "", "error_message": ""}

    def test_result_is_immutable(self, lang):
        result = ExecutionEngine().execute("1", lang)
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.status = "error"  # type: ignore[misc]

    def test_results_from_facade_and_evaluator_compare_equal(self, lang):
        from src.execution.iterative_evaluator import IterativeEvaluator
        assert ExecutionEngine().execute("(add 1 2)", lang) == IterativeEvaluator().execute("(add 1 2)", lang)

    @pytest.mark.parametrize("program,status", [
        ("(add 1 2)", "success"), ("(div 1 0)", "error"), ("(nope 1)", "error"),
        ("(add 1", "error"), ("", "success"),
    ])
    def test_statuses(self, lang, program, status):
        assert ExecutionEngine().execute(program, lang).status == status

    def test_empty_program_succeeds_with_no_value(self, lang):
        result = ExecutionEngine().execute("", lang)
        assert (result.status, result.value) == ("success", None)


# ============================================================================
# CONSTRUCTOR CONFIGURATION THROUGH THE FACADE
# ============================================================================

class TestConstructor:
    def test_no_argument_construction_is_unchanged(self, lang):
        assert ExecutionEngine().execute("(add 1 2)", lang).value == 3

    def test_arguments_are_keyword_only(self):
        with pytest.raises(TypeError):
            ExecutionEngine(10)  # type: ignore[misc]

    def test_signature_is_exactly_the_agreed_one(self):
        params = inspect.signature(ExecutionEngine.__init__).parameters
        assert list(params)[1:] == ["max_steps", "max_ast_depth", "max_call_depth"]
        assert all(p.kind is inspect.Parameter.KEYWORD_ONLY and p.default is None
                   for n, p in params.items() if n != "self")

    @pytest.mark.parametrize("name", ["max_steps", "max_ast_depth", "max_call_depth"])
    @pytest.mark.parametrize("bad", [True, 1.5, "7"])
    def test_wrong_type_is_a_type_error_naming_the_parameter(self, name, bad):
        with pytest.raises(TypeError, match=name):
            ExecutionEngine(**{name: bad})

    @pytest.mark.parametrize("name", ["max_steps", "max_ast_depth", "max_call_depth"])
    def test_negative_is_a_value_error_naming_the_parameter(self, name):
        with pytest.raises(ValueError, match=name):
            ExecutionEngine(**{name: -1})

    def test_max_steps_propagates(self, lang):
        assert ExecutionEngine(max_steps=3).execute("(add 1 2)", lang).status == "success"
        assert ExecutionEngine(max_steps=2).execute("(add 1 2)", lang).status == "step_limit_exceeded"

    def test_max_ast_depth_propagates(self, lang):
        e = ExecutionEngine(max_ast_depth=2)
        assert e.execute("(add 1 2)", lang).status == "success"
        assert e.execute("(add (add 1 1) 2)", lang).status == "ast_depth_exceeded"

    def test_max_call_depth_propagates(self, lang):
        e = ExecutionEngine(max_call_depth=5)
        assert e.execute(RECUR + "(recur 4)", lang).status == "success"                      # 5 active
        rejected = e.execute(RECUR + "(recur 5)", lang)                                       # 6 active
        assert rejected.status == "recursion_limit_exceeded"
        assert "Call depth exceeded" in rejected.error_message

    def test_limits_can_be_raised_above_the_defaults(self, lang):
        assert ExecutionEngine(max_ast_depth=2_000).execute(nested(1500), lang).value == 1501
        assert ExecutionEngine(max_call_depth=150).execute(RECUR + "(recur 120)", lang).status == "success"

    def test_zero_limits_are_real_limits(self, lang):
        assert ExecutionEngine(max_steps=0).execute("1", lang).status == "step_limit_exceeded"
        assert ExecutionEngine(max_ast_depth=0).execute("1", lang).status == "ast_depth_exceeded"

    def test_the_facade_adds_no_defaults_of_its_own(self):
        """Defaults live in one place (types.py); the facade just passes None through."""
        src = inspect.getsource(ExecutionEngine.__init__)
        assert "DEFAULT_" not in src

    def test_each_limit_is_independent_of_the_others(self, lang):
        # nested(500): depth 501 (fine) but 2*500 + 1 = 1001 steps.
        assert ExecutionEngine(max_steps=3).execute(nested(500), lang).status == "step_limit_exceeded"
        assert ExecutionEngine(max_steps=1001).execute(nested(500), lang).value == 501
        # The recursion body is  (if (eq n 0) 0 (recur (sub n 1)))  =  AST depth 4:
        #   if (1) -> recur call (2) -> sub call (3) -> literal n (4).
        # A small AST-depth limit must not be confused with the call-depth limit (100 here).
        assert ExecutionEngine(max_ast_depth=4).execute(RECUR + "(recur 99)", lang).status == "success"
        assert ExecutionEngine(max_ast_depth=3).execute(RECUR + "(recur 99)", lang).status == "ast_depth_exceeded"


class TestPerCallIsolation:
    def test_failed_runs_do_not_poison_later_runs(self, lang):
        e = ExecutionEngine(max_call_depth=3)
        assert e.execute(RECUR + "(recur 9)", lang).status == "recursion_limit_exceeded"
        assert e.execute("(add 1 2)", lang).value == 3
        assert e.execute(RECUR + "(recur 2)", lang).status == "success"                       # 3 active
        assert e.execute(RECUR + "(recur 9)", lang).status == "recursion_limit_exceeded"

    def test_step_budget_is_per_call_not_cumulative(self, lang):
        e = ExecutionEngine(max_steps=3)
        for _ in range(5):
            assert e.execute("(add 1 2)", lang).status == "success"

    def test_two_engines_do_not_share_limits(self, lang):
        strict, lenient = ExecutionEngine(max_steps=2), ExecutionEngine(max_steps=3)
        assert strict.execute("(add 1 2)", lang).status == "step_limit_exceeded"
        assert lenient.execute("(add 1 2)", lang).status == "success"
        assert strict.execute("(add 1 2)", lang).status == "step_limit_exceeded"

    def test_function_definitions_do_not_leak_between_executions(self, lang):
        e = ExecutionEngine()
        assert e.execute("(def f (x) x)\n(f 1)", lang).value == 1
        leaked = e.execute("(f 1)", lang)
        assert leaked.status == "error" and "Unknown function" in leaked.error_message

    def test_one_engine_can_run_different_languages(self, lang):
        other = LanguageGenerator().generate(LanguageSeed(
            name="Sat", syntax_style="lisp", features=["arithmetic"], difficulty=1,
            arithmetic="saturating", short_circuit=False))
        e = ExecutionEngine()
        big = f"(add {2**63 - 1} 1)"
        assert e.execute(big, lang).value == -(2 ** 63)            # wraparound language
        assert e.execute(big, other).value == 2 ** 63 - 1          # saturating language


# ============================================================================
# THE RECURSION BOUNDARY AND "NO PYTHON RECURSION"
# ============================================================================

class TestRecursionThroughTheFacade:
    @pytest.mark.parametrize("k,status", [(0, "success"), (98, "success"), (99, "success"),
                                          (100, "recursion_limit_exceeded"),
                                          (150, "recursion_limit_exceeded")])
    def test_default_call_depth_boundary(self, lang, k, status):
        # recur(k) has k + 1 active invocations; 100 are allowed, 101 are not.
        assert ExecutionEngine().execute(RECUR + f"(recur {k})", lang).status == status

    def test_recur_99_returns_zero_and_recur_100_reports_the_limit(self, lang):
        ok = ExecutionEngine().execute(RECUR + "(recur 99)", lang)
        assert (ok.status, ok.value) == ("success", 0)
        bad = ExecutionEngine().execute(RECUR + "(recur 100)", lang)
        assert (bad.status, bad.value) == ("recursion_limit_exceeded", None)

    def test_100_active_invocations_succeed_with_python_recursion_limit_lowered(self, lang):
        """Not Python's recursion limit: it is ~40 frames above this test, far below the
        ~1000 frames a recursive evaluator would need for 100 nested user calls."""
        base = len(inspect.stack())
        old = sys.getrecursionlimit()
        sys.setrecursionlimit(base + 40)
        try:
            result = ExecutionEngine().execute(RECUR + "(recur 99)", lang)
        finally:
            sys.setrecursionlimit(old)
        assert (result.status, result.value) == ("success", 0)

    def test_mutual_recursion_boundary(self, lang):
        program = ("(def even (n) (if (eq n 0) true (odd (sub n 1))))\n"
                   "(def odd (n) (if (eq n 0) false (even (sub n 1))))\n")
        assert ExecutionEngine().execute(program + "(even 98)", lang).value is True       # 99 active
        assert ExecutionEngine().execute(program + "(even 99)", lang).value is False      # 100 active
        assert ExecutionEngine().execute(program + "(even 100)", lang).status == "recursion_limit_exceeded"

    def test_deep_argument_nesting_does_not_count_as_call_depth(self, lang):
        """Arguments are evaluated BEFORE function entry, so (id (id (id 1))) peaks at 1."""
        program = "(def id (x) x)\n(id (id (id (id 1))))"
        assert ExecutionEngine(max_call_depth=1).execute(program, lang).value == 1

    def test_recovery_after_recursion_limit_rejection(self, lang):
        e = ExecutionEngine()
        assert e.execute(RECUR + "(recur 100)", lang).status == "recursion_limit_exceeded"
        assert e.execute(RECUR + "(recur 99)", lang).status == "success"

    def test_the_facade_contains_no_evaluation_code(self):
        """It must stay a thin delegate: the only public method is execute()."""
        public = {n for n in vars(ExecutionEngine) if not n.startswith("_")}
        assert public == {"execute"}
        source = inspect.getsource(engine_mod)
        assert "def _eval" not in source and "import lark" not in source and "from lark" not in source


# ============================================================================
# IMPORT STRUCTURE: NO CYCLES, LAZY PACKAGE
# ============================================================================

ENTRY_POINTS = ["import src.execution.types", "import src.execution.engine",
                "import src.execution.iterative_evaluator", "from src.execution import ExecutionEngine, ExecutionResult",
                "import src.oracle.reference_evaluator", "import src.execution"]


class TestImportStructure:
    @pytest.mark.parametrize("entry", ENTRY_POINTS, ids=lambda s: s.replace(" ", "_"))
    def test_every_module_imports_cleanly_as_the_first_import(self, entry):
        """A circular import would fail depending on which module is imported first."""
        proc = fresh_python(entry)
        assert proc.returncode == 0, proc.stderr

    def test_package_import_is_lazy(self):
        proc = fresh_python(
            "import sys, src.execution\n"
            "assert 'src.execution.engine' not in sys.modules\n"
            "assert 'src.execution.iterative_evaluator' not in sys.modules\n"
            "src.execution.ExecutionEngine\n"
            "assert 'src.execution.engine' in sys.modules\n")
        assert proc.returncode == 0, proc.stderr

    def test_types_module_imports_nothing_from_the_project(self):
        import ast
        tree = ast.parse(Path(types_mod.__file__).read_text())
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules |= {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                modules.add(node.module or "")
        assert not {m for m in modules if m.startswith(("src", "tests"))}, modules

    def test_importing_types_loads_neither_engine_nor_evaluator(self):
        proc = fresh_python(
            "import sys, src.execution.types\n"
            "assert 'src.execution.engine' not in sys.modules\n"
            "assert 'src.execution.iterative_evaluator' not in sys.modules\n")
        assert proc.returncode == 0, proc.stderr
