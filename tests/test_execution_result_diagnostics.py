"""Wave 2 structured ExecutionResult compatibility tests."""
from src.execution.engine import ExecutionEngine
from src.execution.types import ExecutionResult
from src.language.generator import LanguageGenerator
from src.language.seed import LanguageSeed


def _lang():
    return LanguageGenerator().generate(LanguageSeed(
        name="Diagnostics", syntax_style="lisp", features=["arithmetic", "functions"],
        difficulty=1, arithmetic="wraparound", short_circuit=True))


def test_legacy_result_serialization_is_unchanged():
    result = ExecutionResult(status="success", value=3, steps_used=2, ast_depth_reached=2)
    assert result.to_dict() == {
        "status": "success", "value": 3, "output": "", "error_message": ""
    }


def test_diagnostic_serialization_includes_wave2_fields():
    result = ExecutionResult(
        status="error", error_message="bad", error_kind="type", error_detail="arithmetic",
        steps_used=3, ast_depth_reached=2,
    )
    assert result.to_diagnostic_dict() == {
        "status": "error", "value": None, "output": "", "error_message": "bad",
        "error_kind": "type", "error_detail": "arithmetic",
        "steps_used": 3, "ast_depth_reached": 2,
    }


def test_production_success_reports_step_and_depth_diagnostics():
    result = ExecutionEngine().execute("(add 1 2)", _lang())
    assert result.status == "success"
    assert result.steps_used == 3
    assert result.ast_depth_reached == 2


def test_division_error_has_structured_kind():
    result = ExecutionEngine().execute("(div 1 0)", _lang())
    assert result.status == "error"
    assert (result.error_kind, result.error_detail) == ("division_by_zero", "division_by_zero")



    result = ExecutionEngine().execute("(def f (x) x)", _lang())
    assert (result.status, result.value, result.steps_used) == ("success", None, 0)
