"""Task Generator for M2.5 answer tasks - Complete Implementation.

This module implements deterministic task generation with:
- Seeded reproducibility from derivation seeds
- Template-based generation for EVAL, SYN, INF, CTRL categories
- Two-source verification (production + reference evaluator agreement) - T5
- Pair generation with validation gates T7/T8
- Identifiability (T13) and non-triviality (T9) checks
- Chance floor control (T10)
"""

from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from dataclasses import dataclass, field
from typing import Any

from src.benchmark.generators.identifiability import T13Identifiability

from src.challenge.types import (
    TaskRecord, Protocol, Difficulty, Prompt, AnswerSpec, Evaluation, Test,
    Expected, InputDefinitions, Visibility, Category, InformationCondition,
    ProtocolKind, Role, Variation,
)
from src.challenge.validation import validate_task, ValidationError
from src.challenge.identity import compute_task_id
from src.challenge.projection import project_public
from src.benchmark.canonical import canonical_json, sha256_hex
from src.oracle.reference_evaluator import ReferenceEvaluator
from src.execution.engine import ExecutionEngine
from src.language.generator import LanguageGenerator, LanguageSpec, LanguageSeed
from src.language.semantics import BUILTIN_OPERATIONS
from src.language.surface import SurfaceProfile, to_canonical
from src.benchmark.environments import (
    EnvironmentRecord, GENERATOR_ALGORITHM_VERSION, build_environment, pinned_seed,
)


# Seed-based randomness state
@dataclass
class GenerationState:
    """State for deterministic generation from a seed."""
    seed: str
    position: int = 0
    
    def _seeded_hash(self) -> str:
        data = f"{self.seed}:{self.position}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    def next_int(self, max_value: int) -> int:
        hash_hex = self._seeded_hash()
        self.position += 1
        int_value = int(hash_hex[:16], 16)
        return int_value % max_value
    
    def choice(self, items: list[Any]) -> Any:
        idx = self.next_int(len(items))
        return items[idx]
    
    def shuffle(self, items: list[Any]) -> list[Any]:
        result = items.copy()
        for i in range(len(result) - 1, 0, -1):
            j = self.next_int(i + 1)
            result[i], result[j] = result[j], result[i]
        return result
    
    def copy(self) -> GenerationState:
        return GenerationState(seed=self.seed, position=self.position)
    
    def sample(self, items: list[Any], k: int) -> list[Any]:
        shuffled = self.shuffle(items)
        return shuffled[:k]


@lru_cache(maxsize=None)
def _spec_for(arithmetic: str, short_circuit: bool) -> LanguageSpec:
    return LanguageGenerator().generate(
        pinned_seed(arithmetic, short_circuit), "1.0.0", GENERATOR_ALGORITHM_VERSION)


def language_spec_for(environment: EnvironmentRecord) -> LanguageSpec:
    """The LanguageSpec an environment record denotes (same inputs as build_environment)."""
    return _spec_for(environment.semantic["arithmetic"], environment.semantic["short_circuit"])


class VariationRejected(Exception):
    """A variation cannot be applied to this task. ``code`` is the machine-readable reason."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code


_RESOURCE_STATUSES = frozenset({
    "step_limit_exceeded", "recursion_limit_exceeded", "ast_depth_exceeded", "output_limit_exceeded",
})
_ERROR_CLASSES = ("syntax", "name", "arity", "type", "division_by_zero",
                  "overflow", "literal_range", "resource")


def _outcome(result: Any) -> tuple[str, Any]:
    """Reduce an ExecutionResult to ("int"|"bool", value) or ("error", error_class).

    Types are strict: bool subclasses int in Python, so True is not an int result and
    1 is not a bool result.
    """
    if result.status == "success":
        v = result.value
        if type(v) is bool:
            return "bool", v
        if type(v) is int:
            return "int", v
        return "other", v
    if result.status in _RESOURCE_STATUSES:
        return "error", "resource"
    if result.status == "error":
        return "error", result.error_kind
    return "other", result.status


def _fmt(o: tuple[str, Any]) -> str:
    return f"error({o[1]})" if o[0] == "error" else f"{o[0]}({o[1]!r})"


class T5Verification:
    """T5: two-source expected-result verification.

    The reference evaluator and the production engine must each reproduce ``expected``
    (kind, strict value type, error class) under the task's own environment spec, taken
    from ``environment_registry`` (environment_id -> EnvironmentRecord). An environment
    missing from the registry fails closed.
    """

    def __init__(self, environment_registry: dict[str, EnvironmentRecord] | None = None):
        # Shares the caller's dict so environments registered later are visible.
        self.environment_registry = environment_registry if environment_registry is not None else {}
        self.reference_evaluator = ReferenceEvaluator()
        self.production_engine = ExecutionEngine()

    @staticmethod
    def _parse_expected(expected: Expected) -> tuple[tuple[str, Any] | None, str]:
        ev = expected.value
        if not isinstance(ev, dict):
            return None, "Expected value must be a dictionary"
        kind = ev.get("kind")
        if kind == "int":
            if type(ev.get("value")) is not int:
                return None, "Expected integer value must be an int type"
            return ("int", ev["value"]), ""
        if kind == "bool":
            if type(ev.get("value")) is not bool:
                return None, "Expected boolean value must be a bool type"
            return ("bool", ev["value"]), ""
        if kind == "error":
            if ev.get("error_class") not in _ERROR_CLASSES:
                return None, f"Invalid error class: {ev.get('error_class')}"
            return ("error", ev["error_class"]), ""
        return None, f"Invalid expected value kind: {kind}"

    def verify(
        self,
        query: str,
        expected: Expected,
        environment_id: str,
        surface_profile: dict[str, Any] | None = None,
    ) -> tuple[bool, str]:
        """Return (ok, message). On failure the message gives expected and both results.

        The surface profile defaults to the environment's own.
        """
        exp, err = self._parse_expected(expected)
        if exp is None:
            return False, err
        env = self.environment_registry.get(environment_id)
        if env is None:
            return False, f"environment {environment_id!r} not in registry"
        if surface_profile is None:
            surface_profile = env.surface_profile
        try:
            spec = language_spec_for(env)
            ref = _outcome(self.reference_evaluator.execute(query, spec, surface_profile))
            prod = _outcome(self.production_engine.execute(query, spec, surface_profile))
        except Exception as e:
            return False, f"Verification error: {e}"
        if ref == exp and prod == exp:
            return True, ""
        bad = [n for n, o in (("reference", ref), ("production", prod)) if o != exp]
        return False, (
            f"{' and '.join(bad)} differ from expected for query {query!r}: "
            f"expected={_fmt(exp)}, reference={_fmt(ref)}, production={_fmt(prod)}"
        )
@dataclass
class GenerationResult:
    """Result of task generation."""
    success: bool
    task: TaskRecord | None = None
    error: str | None = None
    rejection_reason: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass
class PairGenerationResult:
    """Result of pair generation."""
    success: bool
    control: TaskRecord | None = None
    treatment: TaskRecord | None = None
    error: str | None = None
    rejection_reason: str | None = None


# Surface profile used by environment:surface_names. Maps canonical operator -> renamed token.
# shortcut: one fixed profile and no environment registry, so the treatment keeps the control's
# environment_id. Upgrade when the environment registry can mint a renamed-surface environment.
SURFACE_PROFILE: dict[str, str] = {
    "add": "prax", "sub": "dwel", "mul": "kerm", "div": "volt", "mod": "zeph",
    "and": "qell", "or": "yarn", "not": "nubs", "eq": "iyo", "gt": "brix", "if": "whet",
}
_INVERSE_PROFILE = {v: k for k, v in SURFACE_PROFILE.items()}
_CALL_HEAD = re.compile(r"\((\w+)\b")


def _translate(text: str, mapping: dict[str, str]) -> str:
    """Rewrite call-head tokens `(name ...` through mapping; other tokens are untouched."""
    return _CALL_HEAD.sub(lambda m: f"({mapping.get(m.group(1), m.group(1))}", text)


_TOKEN = re.compile(r"\(|\)|[^\s()]+")
_EXAMPLE = re.compile(r"^(.*?)(\(.*\))( = )(-?\d+)$")
_ARITHMETIC_MODES = ("wraparound", "saturating", "error-on-overflow")

# INT_MAX constant for semantic configuration boundary queries
INT_MAX = 9223372036854775807


def _identity_profile() -> dict[str, Any]:
    """Profile under which every canonical operator is spelled as itself."""
    return {
        "keywords": {"def": "def", "if": "if"},
        "operators": {o: o for o in sorted(BUILTIN_OPERATIONS - {"if"})},
        "literals": {"true": "true", "false": "false"},
        "profile_schema_version": 1,
    }


def to_canonical_query(text: str) -> str:
    """Translate a surface-profile query or example back to canonical operator names."""
    return _translate(text, _INVERSE_PROFILE)


# Fields a variation is allowed to change (D-001 comparison projection). Everything else must be equal.
_SURFACE = {"prompt.query", "prompt.public_examples", "environment_id"}
_MEANING = _SURFACE | {"expected"}
_ALLOWED_DIFF: dict[str, set[str]] = {
    "environment:surface_names": _SURFACE,
    "environment:operator_meaning": _MEANING,
    "environment:semantic_config": _MEANING,
    "information_condition": {"information_condition"},
    "example_policy": {"prompt.example_policy"},
}
_DISCRIMINATING = {"environment:operator_meaning", "environment:semantic_config"}


def _flatten(task: TaskRecord) -> dict[str, Any]:
    d = task.to_canonical_dict()
    flat = {k: v for k, v in d.items() if k not in ("prompt", "protocol")}
    flat.update({f"prompt.{k}": v for k, v in d["prompt"].items()})
    flat.update({f"protocol.{k}": v for k, v in d["protocol"].items() if k != "role"})
    return flat


def validate_pair(control: TaskRecord, treatment: TaskRecord) -> list[str]:
    """Check D-001 / T7 / T8 for a control-treatment pair. Returns violations; empty means valid."""
    errs: list[str] = []
    cp, tp = control.protocol, treatment.protocol
    if (cp.kind, tp.kind) != ("paired", "paired"):
        return ["both tasks must have protocol.kind=paired"]
    if (cp.role, tp.role) != ("control", "treatment"):
        errs.append("roles must be control then treatment")
    if not cp.pair_group_id or cp.pair_group_id != tp.pair_group_id:
        errs.append("pair_group_id must be set and equal")
    if not cp.varies or cp.varies != tp.varies:
        errs.append("varies must be non-empty and equal")
    if control.task_id == treatment.task_id:
        errs.append("control and treatment have the same task_id (no-op variation)")
    varies = set(cp.varies)
    for v in varies:
        if v not in _ALLOWED_DIFF:
            errs.append(f"unknown variation {v}")

    # T7: only fields of the listed factors may differ.
    allowed = set().union(*(_ALLOWED_DIFF.get(v, set()) for v in varies))
    cf, tf = _flatten(control), _flatten(treatment)
    unrelated = sorted(k for k in cf.keys() | tf.keys() if cf.get(k) != tf.get(k) and k not in allowed)
    if unrelated:
        errs.append(f"T7 unrelated differences: {unrelated}")
    cq, tq = control.prompt.query or "", treatment.prompt.query or ""
    if "environment:surface_names" in varies:
        if not varies & _DISCRIMINATING:
            if to_canonical_query(tq) != to_canonical_query(cq):
                errs.append("T7 canonical queries differ under surface_names")
            if [to_canonical_query(e) for e in treatment.prompt.public_examples] != \
                    [to_canonical_query(e) for e in control.prompt.public_examples]:
                errs.append("T7 canonical public examples differ under surface_names")
        if (cq, control.prompt.public_examples) == (tq, treatment.prompt.public_examples):
            errs.append("surface_names changed nothing")
    # Query text must be identical for variations that don't explicitly allow query changes
    # surface_names is the only variation that allows different surface tokens while preserving canonical meaning
    if "environment:surface_names" not in varies and cq != tq:
        errs.append("T7 query text must be identical")

    # T8: expected equal unless a discriminating variation is listed.
    same = control.expected.value == treatment.expected.value
    if varies & _DISCRIMINATING:
        if same:
            errs.append("T8 discriminating pair needs different expected")
    elif not same:
        errs.append("T8 expected must be equal")
    return errs


class TaskGenerator:
    """Deterministic task generator for M2.5 answer tasks."""
    MAX_T9_ATTEMPTS = 5
    
    def __init__(
        self,
        environment_id: str,
        derivation_seed: str,
        environment_registry: dict[str, EnvironmentRecord] | None = None,
    ):
        self.environment_id = environment_id
        # Copied so minted treatment environments never leak into the caller's dict.
        self.environment_registry: dict[str, EnvironmentRecord] = dict(environment_registry or {})
        # None when environment_id is not registered: T5 then uses the legacy default spec.
        self.environment_record = self.environment_registry.get(environment_id)
        self.derivation_seed = derivation_seed
        self.state = GenerationState(seed=derivation_seed)
        self._t5_verification = T5Verification(self.environment_registry)
        # Use the task environment's semantics for T13 identifiability
        if self.environment_record is not None:
            semantic = self.environment_record.semantic
            arithmetic = semantic.get("arithmetic", "wraparound")
            short_circuit = semantic.get("short_circuit", True)
            self._t13_identifiability = T13Identifiability(arithmetic=arithmetic, short_circuit=short_circuit)
        else:
            # T13 will fail-closed when used with unregistered environment
            self._t13_identifiability = None
    
    def generate_single_task(
        self,
        category: Category,
        difficulty_level: int,
        information_condition: InformationCondition,
    ) -> GenerationResult:
        """Generate a single value-answer task."""
        try:
            task_data = self._generate_task_content(
                category=category,
                difficulty_level=difficulty_level,
                information_condition=information_condition,
            )
            
            if task_data is None:
                return GenerationResult(success=False, rejection_reason="Failed to generate valid task content")
            
            # T9 check. Regenerate if needed. The state is deliberately not rewound,
            # so each attempt draws fresh values and yields a different candidate.
            for _ in range(self.MAX_T9_ATTEMPTS - 1):
                if self._check_t9_non_trivial(task_data):
                    break
                task_data = self._generate_task_content(
                    category=category,
                    difficulty_level=difficulty_level,
                    information_condition=information_condition,
                )
                if task_data is None:
                    break
            if task_data is None or not self._check_t9_non_trivial(task_data):
                return GenerationResult(success=False, rejection_reason="Failed to generate non-trivial task after regeneration")
            # Build task record
            surface_profile = task_data.get("surface_profile")
            task = self._build_task_record(
                task_data=task_data,
                category=category,
                difficulty_level=difficulty_level,
                information_condition=information_condition,
            )
            
            # T13 check for INF
            if category == "INF":
                if self._t13_identifiability is None:
                    return GenerationResult(
                        success=False,
                        rejection_reason=f"T13 identifiability requires a registered environment. "
                        f"Environment '{self.environment_id}' is not in the registry."
                    )
                t13_ok, t13_error = self._t13_identifiability.check(
                    task.prompt.query or "",
                    list(task.prompt.public_examples),
                )
                if not t13_ok:
                    return GenerationResult(success=False, rejection_reason=f"T13 identifiability failed: {t13_error}")
            
            # T5 verification
            t5_ok, t5_error = self._t5_verification.verify(
                task.prompt.query or "", task.expected, task.environment_id, surface_profile)
            if not t5_ok:
                return GenerationResult(success=False, rejection_reason=f"T5 verification failed: {t5_error}")
            
            # Validate task
            try:
                validate_task(task)
            except ValidationError as e:
                return GenerationResult(success=False, rejection_reason=f"Validation failed: {e.rule} - {e.message}")
            
            # Add metadata
            task = self._add_provenance(task)
            if surface_profile is not None:
                # Hidden answer key: provenance is stripped from the public projection.
                task = TaskRecord(**{**task.__dict__, "provenance": {**task.provenance, "surface_profile": surface_profile}})

            return GenerationResult(
                success=True,
                task=task,
                provenance={
                    "generator": "M2.5.2_TaskGenerator",
                    "environment_id": self.environment_id,
                    "derivation_seed": self.derivation_seed,
                },
            )
            
        except Exception as e:
            return GenerationResult(success=False, error=str(e))
    
    def generate_pair(
        self,
        base_task: TaskRecord,
        variation: Variation,
    ) -> PairGenerationResult:
        """Generate a paired task (control/treatment)."""
        try:
            if base_task.protocol.kind != "standalone":
                return PairGenerationResult(success=False, rejection_reason="base task must be standalone")
            group = "pair_" + sha256_hex(canonical_json([base_task.task_id, variation]))
            control = self._with_protocol(base_task, Protocol(
                kind="paired", pair_group_id=group, role="control", varies=(variation,)))
            try:
                treatment = self._apply_variation(base_task=control, variation=variation)
            except VariationRejected as e:
                return PairGenerationResult(
                    success=False, rejection_reason=f"{variation} rejected [{e.code}]: {e}")
            if treatment is None:
                return PairGenerationResult(
                    success=False,
                    rejection_reason="Failed to apply variation",
                )
            base_task = control

            for task, name in [(base_task, "control"), (treatment, "treatment")]:
                try:
                    validate_task(task)
                except ValidationError as e:
                    return PairGenerationResult(
                        success=False,
                        rejection_reason=f"{name} validation failed: {e.rule} - {e.message}",
                    )
            # T5 runs in the canonical surface, so renamed queries are translated back first.
            for task, name in [(base_task, "control"), (treatment, "treatment")]:
                t5_ok, t5_error = self._t5_verification.verify(
                    task.prompt.query or "", task.expected, task.environment_id,
                    (task.provenance or {}).get("surface_profile"))
                if not t5_ok:
                    return PairGenerationResult(
                        success=False,
                        rejection_reason=f"{name} T5 verification failed: {t5_error}",
                    )
            pair_errors = validate_pair(base_task, treatment)
            if pair_errors:
                return PairGenerationResult(
                    success=False, rejection_reason="pair validation failed: " + "; ".join(pair_errors))
            base_task = self._add_provenance(base_task)
            treatment = self._add_provenance(treatment)
            
            return PairGenerationResult(success=True, control=base_task, treatment=treatment)
            
        except Exception as e:
            return PairGenerationResult(success=False, error=str(e))
    
    def _generate_task_content(
        self,
        category: Category,
        difficulty_level: int,
        information_condition: InformationCondition,
    ) -> dict[str, Any] | None:
        """Generate candidate task content for the specified category."""
        if category == "SYN":
            return self._generate_syn_task(difficulty_level, information_condition)
        elif category == "EVAL":
            return self._generate_eval_task(difficulty_level, information_condition)
        elif category == "INF":
            return self._generate_inf_task(difficulty_level, information_condition)
        elif category == "CTRL":
            return self._generate_ctrl_task(difficulty_level, information_condition)
        else:
            return None
    
    def _generate_syn_task(
        self,
        difficulty: int,
        information_condition: InformationCondition,
    ) -> dict[str, Any]:
        """Generate syntax comprehension task."""
        expression = self._generate_expression(difficulty)
        expected_value = self._evaluate_expression(expression)
        if not self._t9_ok(expression, expected_value, []):
            expression = self._generate_complex_expression(difficulty + 1)
            expected_value = self._evaluate_expression(expression)
        return {
            "query": expression,
            "expected": {"kind": "int", "value": expected_value},
            "public_examples": [],
            "difficulty": difficulty,
        }
    
    def _generate_semantic_config_boundary_task(self) -> dict[str, Any] | None:
        """Generate a boundary-sensitive task that distinguishes wraparound from saturation.
        
        Uses intermediate arithmetic to construct INT_MAX without the literal appearing in query.
        Query: (add (add 9223372036854775707 100) 1)
        Wraparound result: -9223372036854775808 (INT_MIN)
        Saturating result: 9223372036854775807 (INT_MAX)
        """
        # Build the query using intermediate values to construct INT_MAX
        # The inner addition (add 9223372036854775707 100) = INT_MAX in both modes
        # The outer addition (add INT_MAX 1) produces INT_MIN in wraparound, INT_MAX in saturating
        query = "(add (add 9223372036854775707 100) 1)"
        
        # Verify through engine
        seed = LanguageSeed(name="env", syntax_style="lisp", features=["arithmetic", "functions", "recursion", "short_circuit"],
                           difficulty=1, arithmetic="wraparound", short_circuit=True)
        spec = LanguageGenerator().generate(seed, "1.0.0", "1.0.0")
        result = self._t5_verification.reference_evaluator.execute(query, spec, _identity_profile())
        
        if result.status != "success" or type(result.value) is not int:
            return None
        
        # Check T9: neither expected value should appear in query
        import re
        literals = set(re.findall(r'-?\d+', query))
        wrap_value = int(result.value)
        sat_value = 9223372036854775807  # INT_MAX
        
        if str(wrap_value) in literals or str(sat_value) in literals:
            return None
        
        return {
            "query": query,
            "expected": {"kind": "int", "value": wrap_value},
            "public_examples": [],
            "difficulty": 1,
        }
    def _generate_eval_task(
        self,
        difficulty: int,
        information_condition: InformationCondition,
    ) -> dict[str, Any]:
        """Generate expression evaluation task."""
        expression = self._generate_complex_expression(difficulty)
        expected_value = self._evaluate_expression(expression)
        if not self._t9_ok(expression, expected_value, []):
            expression = self._generate_complex_expression(difficulty + 1)
            expected_value = self._evaluate_expression(expression)
        num_examples = min(difficulty, 3)
        public_examples = []
        for _ in range(num_examples):
            # Retry so no example contains the expected value as a token (T9).
            for _attempt in range(self.MAX_T9_ATTEMPTS):
                expr = self._generate_expression(max(1, difficulty - 1))
                example = f"Example: {expr} = {self._evaluate_expression(expr)}"
                if self._t9_ok(expression, expected_value, [example]):
                    break
            public_examples.append(example)
        return {
            "query": expression,
            "expected": {"kind": "int", "value": expected_value},
            "public_examples": public_examples,
            "difficulty": difficulty,
        }
    def _t9_ok(self, query: str, expected_value: int, examples: list[str]) -> bool:
        return self._check_t9_non_trivial({
            "query": query,
            "expected": {"kind": "int", "value": expected_value},
            "public_examples": examples,
        })
    _SURFACE_NAMES = ("zorp", "blik", "quen", "trav", "mox", "dwil", "frum", "keps")
    _INF_OPS = {"add": lambda a, b: a + b, "sub": lambda a, b: a - b, "mul": lambda a, b: a * b}

    def _generate_inf_task(
        self,
        difficulty: int,
        information_condition: InformationCondition,
    ) -> dict[str, Any] | None:
        """Generate an INF task: the query defines a function whose body uses surface
        operators and calls it; the public examples are the only way to learn what the
        operators mean. The surface->canonical mapping is returned as ``surface_profile``
        (hidden answer key, stored in provenance).
        """
        func_name = f"f{self.state.next_int(100)}"
        param_name = f"x{self.state.next_int(10)}"
        n_ops = 1 if difficulty <= 3 else 2
        names = self.state.sample(list(self._SURFACE_NAMES), n_ops)
        canon = [self.state.choice(list(self._INF_OPS)) for _ in range(n_ops)]
        consts = [self.state.next_int(8) + 2 for _ in range(n_ops)]
        body = param_name
        for name, k in zip(names, consts):
            body = f"({name} {body} {k})"
        profile = {
            "keywords": {"def": "def"}, "operators": dict(zip(names, canon)),
            "literals": {}, "profile_schema_version": 1,
        }
        arg = self.state.next_int(20) + 2
        value = arg
        for c, k in zip(canon, consts):
            value = self._INF_OPS[c](value, k)
        examples: list[str] = []
        for name, c in zip(names, canon):
            examples.extend(self._identifying_examples(name, c, banned={str(value)}))
        query = f"(def {func_name} ({param_name}) {body}) ({func_name} {arg})"
        return {
            "query": query,
            "expected": {"kind": "int", "value": value},
            "public_examples": examples,
            "difficulty": difficulty,
            "surface_profile": profile,
        }

    def _identifying_examples(self, surface: str, canonical: str, banned: set[str]) -> list[str]:
        """Pick examples for one surface operator until only its true meaning is consistent.

        shortcut: draws from a small int range with at most 50 tries, then returns what it has;
        T13 (not this method) is the gate that rejects any task left ambiguous.
        """
        t13 = self._t13_identifiability
        # For unregistered environments, use a minimal fallback that still works
        if t13 is None:
            # Return simple examples without T13 checking (will be rejected later)
            return [f"({surface} {a} {b}) = {r}" for a, b, r in [(2, 3, self._INF_OPS[canonical](2, 3))]]
        
        chosen: list[tuple[tuple[tuple[str, int], ...], tuple[str, int]]] = []
        for _ in range(50):
            a, b = self.state.next_int(9) + 2, self.state.next_int(9) + 2
            res = self._INF_OPS[canonical](a, b)
            if str(res) in banned or str(a) in banned or str(b) in banned:
                continue
            ex = ((("int", a), ("int", b)), ("int", res))
            if ex in chosen:
                continue
            chosen.append(ex)
            if t13.candidates(2, chosen) == [canonical]:
                break
        return [f"({surface} {a} {b}) = {r}" for ((_, a), (_, b)), (_, r) in chosen]

    def _generate_ctrl_task(
        self,
        difficulty: int,
        information_condition: InformationCondition,
    ) -> dict[str, Any]:
        """Generate control-flow task: (if condition then_expr else_expr).

        Expected is the evaluation of the query itself. Branches are expressions
        (not bare literals) so the expected value is not a token of the query (T9).
        """
        a, b = self.state.next_int(3), self.state.next_int(3)
        if difficulty <= 2:
            condition = f"(eq {a} {b})"
        else:
            condition = f"(eq (add {a} {self.state.next_int(3)}) {b})"
        then_expr = self._generate_expression(1)
        else_expr = self._generate_expression(1)
        query = f"(if {condition} {then_expr} {else_expr})"
        return {
            "query": query,
            "expected": {"kind": "int", "value": self._evaluate_expression(query)},
            "public_examples": [],
            "difficulty": difficulty,
        }
    def _generate_expression(self, difficulty: int) -> str:
        """Generate a simple expression."""
        operators = ["add", "sub", "mul", "div"]
        op = self.state.choice(operators)
        
        if difficulty <= 1:
            n1 = self.state.next_int(20)
            n2 = self.state.next_int(10) + 1
            return f"({op} {n1} {n2})"
        else:
            n1 = self.state.next_int(10)
            n2 = self.state.next_int(10) + 1
            n3 = self.state.next_int(5) + 1
            return f"({op} ({op} {n1} {n2}) {n3})"
    
    def _generate_complex_expression(self, difficulty: int) -> str:
        """Generate a complex expression with multiple operations."""
        if difficulty <= 2:
            return self._generate_expression(2)
        else:
            expr = self._generate_expression(2)
            for _ in range(difficulty - 2):
                op = self.state.choice(["add", "sub"])
                n = self.state.next_int(10)
                expr = f"({op} {expr} {n})"
            return expr
    
    def _evaluate_expression(self, expression: str) -> int:
        """Recursively evaluate a nested s-expression to an int.

        Supports add, sub, mul, div (truncates toward zero), mod, gt, eq, if.
        Booleans from gt/eq are 1/0. Raises ValueError on malformed input and
        ZeroDivisionError on div/mod by zero.
        """
        tokens = expression.replace("(", " ( ").replace(")", " ) ").split()
        node, pos = self._parse_sexpr(tokens, 0)
        if pos != len(tokens):
            raise ValueError(f"Trailing tokens in expression: {expression!r}")
        return self._eval_node(node)
    def _parse_sexpr(self, tokens: list[str], pos: int) -> tuple[Any, int]:
        if pos >= len(tokens):
            raise ValueError("Unexpected end of expression")
        tok = tokens[pos]
        if tok == ")":
            raise ValueError("Unexpected ')'")
        if tok != "(":
            return tok, pos + 1
        pos += 1
        items: list[Any] = []
        while pos < len(tokens) and tokens[pos] != ")":
            item, pos = self._parse_sexpr(tokens, pos)
            items.append(item)
        if pos >= len(tokens):
            raise ValueError("Missing ')'")
        return items, pos + 1
    def _eval_node(self, node: Any) -> int:
        if isinstance(node, str):
            return int(node)
        if not node or not isinstance(node[0], str):
            raise ValueError(f"Malformed expression node: {node!r}")
        op, args = node[0], node[1:]
        if op == "if":
            if len(args) != 3:
                raise ValueError("if takes 3 arguments")
            return self._eval_node(args[1] if self._eval_node(args[0]) != 0 else args[2])
        if len(args) != 2:
            raise ValueError(f"{op} takes 2 arguments")
        x, y = self._eval_node(args[0]), self._eval_node(args[1])
        if op == "add":
            return x + y
        if op == "sub":
            return x - y
        if op == "mul":
            return x * y
        if op in ("div", "mod"):
            q = abs(x) // abs(y)
            q = q if (x < 0) == (y < 0) else -q
            return q if op == "div" else x - y * q
        if op == "gt":
            return 1 if x > y else 0
        if op == "eq":
            return 1 if x == y else 0
        raise ValueError(f"Unknown operator: {op}")
    def _build_task_record(
        self,
        task_data: dict[str, Any],
        category: Category,
        difficulty_level: int,
        information_condition: InformationCondition,
    ) -> TaskRecord:
        """Build a complete TaskRecord from generated content."""
        difficulty = Difficulty(
            level=difficulty_level,
            reasoning_steps=difficulty_level,
            nesting_depth=difficulty_level,
            control_flow="none" if difficulty_level <= 2 else "conditional",
            state="none",
        )
        
        prompt = Prompt(
            template=("prompt.answer", 1),
            example_policy="neutral",
            public_examples=tuple(task_data.get("public_examples", [])),
            query=task_data.get("query"),
        )
        
        answer_spec = AnswerSpec(
            type="value",
            kind="int",
            form=None,
            chance_floor_ppm=None,
        )
        
        expected_value = task_data.get("expected", {"kind": "int", "value": 0})
        expected = Expected(value=expected_value)
        
        evaluation = Evaluation(
            method="exact_match",
            limits={"max_steps": 100000, "max_call_depth": 100},
            tests=[],
        )
        
        protocol = Protocol(kind="standalone")
        
        task = TaskRecord(
            schema_version=1,
            task_id="",
            template=("task.answer", 1),
            category=category,
            protocol=protocol,
            environment_id=self.environment_id,
            difficulty=difficulty,
            information_condition=information_condition,
            prompt=prompt,
            answer_spec=answer_spec,
            expected=expected,
            evaluation=evaluation,
        )
        
        task_id = compute_task_id(task)
        
        return TaskRecord(**{**task.__dict__, "task_id": task_id})
    
    def _check_t9_non_trivial(self, task_data: dict[str, Any]) -> bool:
        """Check T9 non-triviality before building task record."""
        expected_value = task_data.get("expected", {})
        if not isinstance(expected_value, dict):
            return True
        
        expected_kind = expected_value.get("kind")
        if expected_kind not in ("int", "bool"):
            return True
        
        if expected_kind == "int":
            expected_str = str(expected_value.get("value", ""))
        elif expected_kind == "bool":
            expected_str = str(expected_value.get("value", "")).lower()
        else:
            return True
        
        query = task_data.get("query", "")
        query_tokens = set(query.replace("(", " ").replace(")", " ").split())
        
        if expected_str in query_tokens:
            return False
        
        for example in task_data.get("public_examples", []):
            example_tokens = set(example.replace("(", " ").replace(")", " ").split())
            if expected_str in example_tokens:
                return False
        
        return True
    
    def _add_provenance(self, task: TaskRecord) -> TaskRecord:
        """Add provenance metadata to task."""
        provenance = {"generator": "M2.5.2_TaskGenerator", "version": "1.0.0", "derivation_seed": self.derivation_seed}
        return TaskRecord(**{**task.__dict__, "provenance": provenance})
    
    def _apply_variation(
        self,
        base_task: TaskRecord,
        variation: Variation,
    ) -> TaskRecord | None:
        """Apply a variation to create a treatment task.

        Raises VariationRejected (with a machine-readable ``code``) when the task cannot carry
        an environment variation. Environment variations mint a new EnvironmentRecord, register
        it, and point the treatment's environment_id at it.
        """
        if variation == "environment:surface_names":
            new_task = self._vary_surface_names(base_task)
        elif variation == "environment:operator_meaning":
            new_task = self._vary_operator_meaning(base_task)
        elif variation == "environment:semantic_config":
            new_task = self._vary_semantic_config(base_task)
        elif variation == "information_condition":
            other = "EXAMPLES_ONLY" if base_task.information_condition != "EXAMPLES_ONLY" else "FULL_DOC"
            new_task = self._replace(base_task, information_condition=other)
        elif variation == "example_policy":
            new_policy = "misleading" if base_task.prompt.example_policy == "neutral" else "neutral"
            new_prompt = Prompt(
                template=base_task.prompt.template,
                example_policy=new_policy,
                public_examples=base_task.prompt.public_examples,
                query=base_task.prompt.query,
            )
            new_task = self._replace(base_task, prompt=new_prompt)
        else:
            return None
        protocol = Protocol(
            kind="paired", pair_group_id=base_task.protocol.pair_group_id,
            role="treatment", varies=base_task.protocol.varies,
        )
        return self._with_protocol(new_task, protocol)

    # --- environment variations -------------------------------------------------------------

    def _task_context(self, task: TaskRecord) -> tuple[EnvironmentRecord | None, dict[str, Any]]:
        """The registered environment (or None) and the surface profile the task's text uses.

        A per-task profile in provenance (INF) wins; else the environment's; else the canonical
        identity profile.
        """
        record = self.environment_registry.get(task.environment_id)
        profile = (task.provenance or {}).get("surface_profile")
        if profile is None:
            profile = record.surface_profile if record is not None else _identity_profile()
        return record, profile

    def _require_registered(self, task: TaskRecord, variation: str) -> EnvironmentRecord:
        record = self.environment_registry.get(task.environment_id)
        if record is None:
            raise VariationRejected(
                "environment_not_registered",
                f"{variation} needs environment {task.environment_id!r} in the environment registry")
        return record

    def _mint(
        self, record: EnvironmentRecord | None, arithmetic: str, short_circuit: bool,
        profile: dict[str, Any], variation: str, parent_id: str,
    ) -> EnvironmentRecord:
        env = build_environment(arithmetic, short_circuit, profile, derivation={
            "variation": variation, "parent_environment_id": parent_id,
            "parent_registered": record is not None,
        })
        self.environment_registry[env.environment_id] = env
        return env

    def _run(self, query: str, arithmetic: str, short_circuit: bool, profile: dict[str, Any]):
        return self._t5_verification.reference_evaluator.execute(
            query, _spec_for(arithmetic, short_circuit), profile)

    def _int_result(self, query: str, arithmetic: str, short_circuit: bool, profile: dict[str, Any]) -> int | None:
        result = self._run(query, arithmetic, short_circuit, profile)
        if result.status == "success" and type(result.value) is int:
            return result.value
        return None

    def _remap_examples(
        self, examples: tuple[str, ...], arithmetic: str, short_circuit: bool, profile: dict[str, Any],
    ) -> tuple[str, ...]:
        """Recompute `<expr> = <value>` examples under a changed environment.

        shortcut: examples that do not match `<expr> = <int>` or do not evaluate to an int are
        kept as written; upgrade if example formats beyond these are generated.
        """
        out = []
        for example in examples:
            m = _EXAMPLE.match(example)
            value = self._int_result(m.group(2), arithmetic, short_circuit, profile) if m else None
            out.append(f"{m.group(1)}{m.group(2)}{m.group(3)}{value}" if value is not None else example)
        return tuple(out)

    def _treatment_provenance(self, task: TaskRecord, profile: dict[str, Any]) -> dict[str, Any]:
        prov = dict(task.provenance or {})
        if "surface_profile" in prov:
            prov["surface_profile"] = profile
        return prov

    def _vary_surface_names(self, task: TaskRecord) -> TaskRecord:
        """Rename every operator surface token; canonical meaning is unchanged."""
        record, profile = self._task_context(task)
        query = task.prompt.query or ""
        texts = [query, *task.prompt.public_examples]
        operators: dict[str, str] = profile["operators"]
        if not {h for t in texts for h in _CALL_HEAD.findall(t) if h in operators}:
            raise VariationRejected(
                "no_surface_tokens", "query and examples use no operator surface tokens to rename")
        taken = set(re.findall(r"[A-Za-z_]\w*", " ".join(texts)))
        taken |= set(profile["keywords"]) | set(profile["literals"])
        rename: dict[str, str] = {}
        for old in sorted(operators):
            base = SURFACE_PROFILE.get(operators[old], old + "x")
            new, n = base, 2
            while new in taken:
                new, n = f"{base}{n}", n + 1
            taken.add(new)
            rename[old] = new
        new_profile = {**profile, "operators": {rename[o]: c for o, c in operators.items()}}
        SurfaceProfile.from_dict(new_profile)
        # canonical form -> render with the new profile; user identifiers are restored.
        translated = to_canonical(query, profile)
        by_generated = {v: k for k, v in translated.name_map.items()}
        by_canonical: dict[str, str] = {}
        for category in ("keywords", "operators", "literals"):
            for surface, canonical in new_profile[category].items():
                by_canonical.setdefault(canonical, surface)
        tokens = [by_generated.get(t) or by_canonical.get(t, t) for t in _TOKEN.findall(translated.canonical_text)]
        new_query = " ".join(tokens).replace("( ", "(").replace(" )", ")")
        if to_canonical(new_query, new_profile).canonical_text != translated.canonical_text:
            raise VariationRejected("render_mismatch", "renamed query does not translate back to the same canonical form")
        examples = tuple(
            _CALL_HEAD.sub(lambda m: "(" + rename.get(m.group(1), m.group(1)), e)
            for e in task.prompt.public_examples)
        arithmetic, short_circuit = self._semantics(record)
        env = self._mint(record, arithmetic, short_circuit, new_profile,
                         "environment:surface_names", task.environment_id)
        prompt = Prompt(
            template=task.prompt.template, example_policy=task.prompt.example_policy,
            public_examples=examples, query=new_query)
        return self._replace(
            task, prompt=prompt, environment_id=env.environment_id,
            provenance=self._treatment_provenance(task, new_profile))

    @staticmethod
    def _semantics(record: EnvironmentRecord | None) -> tuple[str, bool]:
        """Semantic settings of the record; the legacy T5 defaults when unregistered."""
        if record is None:
            return "wraparound", True
        return record.semantic["arithmetic"], record.semantic["short_circuit"]

    def _expected_int(self, task: TaskRecord, variation: str) -> int:
        value = task.expected.value
        if not isinstance(value, dict) or value.get("kind") != "int" or type(value.get("value")) is not int:
            raise VariationRejected("unsupported_expected", f"{variation} supports int expected values only")
        return value["value"]

    def _finish_meaning_change(
        self, task: TaskRecord, variation: str, record: EnvironmentRecord, arithmetic: str,
        short_circuit: bool, profile: dict[str, Any], new_value: int,
    ) -> TaskRecord:
        env = self._mint(record, arithmetic, short_circuit, profile, variation, task.environment_id)
        prompt = Prompt(
            template=task.prompt.template, example_policy=task.prompt.example_policy,
            public_examples=self._remap_examples(task.prompt.public_examples, arithmetic, short_circuit, profile),
            query=task.prompt.query)
        return self._replace(
            task, prompt=prompt, environment_id=env.environment_id,
            expected=Expected(value={"kind": "int", "value": new_value}),
            provenance=self._treatment_provenance(task, profile))

    def _vary_operator_meaning(self, task: TaskRecord) -> TaskRecord:
        """Keep the surface tokens, but swap what two of them mean."""
        variation = "environment:operator_meaning"
        record = self._require_registered(task, variation)
        _, profile = self._task_context(task)
        old = self._expected_int(task, variation)
        query = task.prompt.query or ""
        operators: dict[str, str] = profile["operators"]
        used = {h for h in _CALL_HEAD.findall(query) if h in operators}
        if not used:
            raise VariationRejected("no_surface_tokens", "query uses no operator whose meaning can change")
        arithmetic, short_circuit = self._semantics(record)
        for a in sorted(operators):
            for b in sorted(operators):
                if a >= b or operators[a] == operators[b] or not ({a, b} & used):
                    continue
                swapped = {**operators, a: operators[b], b: operators[a]}
                new_profile = {**profile, "operators": swapped}
                value = self._int_result(query, arithmetic, short_circuit, new_profile)
                if value is not None and value != old:
                    return self._finish_meaning_change(
                        task, variation, record, arithmetic, short_circuit, new_profile, value)
        raise VariationRejected("no_distinguishing_mapping", "no operator swap changes the expected value")

    def _vary_semantic_config(self, task: TaskRecord) -> TaskRecord:
        """Keep text and surface profile, but change arithmetic or short-circuit mode."""
        variation = "environment:semantic_config"
        record = self._require_registered(task, variation)
        _, profile = self._task_context(task)
        old = self._expected_int(task, variation)
        query = task.prompt.query or ""
        arithmetic, short_circuit = self._semantics(record)
        candidates = [(a, short_circuit) for a in _ARITHMETIC_MODES if a != arithmetic]
        candidates.append((arithmetic, not short_circuit))
        # shortcut: only candidates that still yield an int count; a mode that turns the query
        # into an error is skipped. Upgrade when error-valued expected answers are supported.
        for new_arithmetic, new_short_circuit in candidates:
            value = self._int_result(query, new_arithmetic, new_short_circuit, profile)
            if value is not None and value != old:
                return self._finish_meaning_change(
                    task, variation, record, new_arithmetic, new_short_circuit, profile, value)
        
        # If no simple configuration change works, the task cannot be varied with semantic_config
        # The generator must produce boundary-sensitive queries during normal generation
        raise VariationRejected("no_distinguishing_config", "no semantic setting changes the expected value")

    @staticmethod
    def _replace(task: TaskRecord, **changes: Any) -> TaskRecord:
        return TaskRecord(**{**task.__dict__, **changes})

    def _with_protocol(self, task: TaskRecord, protocol: Protocol) -> TaskRecord:
        """Return task with the given protocol and a recomputed task_id."""
        new_task = self._replace(task, protocol=protocol, task_id="")
        return self._replace(new_task, task_id=compute_task_id(new_task))

    def generate_semantic_config_boundary_task(self) -> GenerationResult:
        """Generate a boundary-sensitive task suitable for semantic_config pairs.
        
        This method produces a task with a query that produces different results
        in wraparound vs saturating arithmetic modes. The boundary expression is:
        
            (add (add 9223372036854775707 100) 1)
        
        Results:
            wraparound: -9223372036854775808 (INT_MIN)
            saturating: 9223372036854775807 (INT_MAX)
        
        Returns:
            GenerationResult with success=True and task populated if generation succeeds,
            or success=False with rejection_reason if it fails.
        """
        boundary_task_data = self._generate_semantic_config_boundary_task()
        if boundary_task_data is None:
            return GenerationResult(
                success=False,
                rejection_reason="Failed to generate boundary task content"
            )
        
        task = self._build_task_record(
            task_data=boundary_task_data,
            category="SYN",
            difficulty_level=1,
            information_condition="FULL_DOC",
        )
        
        # T5 verification
        t5_ok, t5_error = self._t5_verification.verify(
            task.prompt.query or "", task.expected, task.environment_id,
            (task.provenance or {}).get("surface_profile"))
        if not t5_ok:
            return GenerationResult(
                success=False,
                rejection_reason=f"T5 verification failed: {t5_error}"
            )
        
        # Validate task
        try:
            validate_task(task)
        except ValidationError as e:
            return GenerationResult(
                success=False,
                rejection_reason=f"Validation failed: {e.rule} - {e.message}"
            )
        
        task = self._add_provenance(task)
        
        return GenerationResult(
            success=True,
            task=task,
            provenance={
                "generator": "M2.5.2_TaskGenerator",
                "environment_id": self.environment_id,
                "derivation_seed": self.derivation_seed,
                "generation_method": "semantic_config_boundary",
            },
        )

    def generate_semantic_config_pair(self, difficulty_level: int = 1) -> PairGenerationResult:
        """Generate a semantic-config pair with a boundary-sensitive query.
        
        This convenience method first generates a boundary-sensitive base task,
        then creates a control/treatment pair with semantic_config variation.
        
        The pair has:
            - Identical queries (boundary expression)
            - Different environments (wraparound vs saturating)
            - Different expected values (INT_MIN vs INT_MAX)
        
        Returns:
            PairGenerationResult with success=True and tasks populated if generation succeeds,
            or success=False with rejection_reason if it fails.
        """
        # Generate boundary-sensitive base task
        base_result = self.generate_semantic_config_boundary_task()
        if not base_result.success:
            return PairGenerationResult(
                success=False,
                rejection_reason=f"Failed to generate boundary task: {base_result.rejection_reason}"
            )
        
        # Clear the protocol so generate_pair can set up the control properly
        base_task = self._replace(base_result.task, protocol=Protocol(kind="standalone"))
        
        # Generate pair from the standalone base task
        pair_result = self.generate_pair(base_task, "environment:semantic_config")
        return pair_result


def create_generator(environment_id: str, derivation_seed: str) -> TaskGenerator:
    """Factory function to create a task generator."""
    return TaskGenerator(environment_id=environment_id, derivation_seed=derivation_seed)
