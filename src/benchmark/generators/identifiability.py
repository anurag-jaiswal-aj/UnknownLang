"""T13 identifiability for INF tasks.

For every surface operator used in the query, the public examples must leave exactly one
canonical operation (taken from the language's own operator registry, restricted to the
operator's type class) consistent with all examples, and the examples must not contradict
each other. Example format: ``(surface_op arg ...) = result``.
"""
from __future__ import annotations

import re
from typing import Any

from src.execution.engine import ExecutionEngine
from src.language.generator import LanguageGenerator
from src.language.seed import LanguageSeed

_SEXPR_TOKEN = re.compile(r"\(|\)|[^\s()]+")
_INT_LITERAL = re.compile(r"-?[0-9]+")
_FORM_KEYWORDS = frozenset({"def", "if", "begin"})

Literal = tuple[str, Any]  # ("int" | "bool", value)


def _read_sexprs(text: str) -> list[Any]:
    """Parse text into nested lists of atom strings. Raises ValueError if unbalanced."""
    stack: list[list[Any]] = [[]]
    for tok in _SEXPR_TOKEN.findall(text):
        if tok == "(":
            stack.append([])
        elif tok == ")":
            if len(stack) == 1:
                raise ValueError("unbalanced ')'")
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(tok)
    if len(stack) != 1:
        raise ValueError("unbalanced '('")
    return stack[0]


def _literal(atom: Any) -> Literal | None:
    if isinstance(atom, str):
        if _INT_LITERAL.fullmatch(atom):
            return "int", int(atom)
        if atom in ("true", "false"):
            return "bool", atom == "true"
    return None


class T13Identifiability:
    """T13: every surface operator in an INF query is uniquely determined by the examples."""

    def __init__(self, arithmetic: str = "wraparound", short_circuit: bool = True) -> None:
        """Initialize with specific semantic configuration.
        
        Args:
            arithmetic: Arithmetic mode (wraparound, saturating, error-on-overflow)
            short_circuit: Whether to use short-circuit evaluation for booleans
        """
        self._spec = LanguageGenerator().generate(
            LanguageSeed(
                name="t13", syntax_style="lisp", features=["arithmetic", "functions"],
                difficulty=1, arithmetic=arithmetic, short_circuit=short_circuit,
            ),
            "1.0.0", "1.0.0",
        )
        self._operations = self._spec.semantics.operations
        self._engine = ExecutionEngine()

    def query_operators(self, query: str) -> dict[str, int]:
        """Surface operators used in query (name -> arity). Defined functions are excluded."""
        forms = _read_sexprs(query)
        defined = {f[1] for f in forms if isinstance(f, list) and len(f) >= 2 and f[0] == "def"}
        found: dict[str, int] = {}

        def walk(node: Any) -> None:
            if not isinstance(node, list) or not node:
                return
            head, rest = node[0], node[1:]
            if head == "def":
                walk(node[-1])
                return
            if isinstance(head, str) and head not in _FORM_KEYWORDS and head not in defined:
                if found.setdefault(head, len(rest)) != len(rest):
                    raise ValueError(f"Operator '{head}' used with inconsistent arity")
            for child in rest:
                walk(child)

        for form in forms:
            walk(form)
        return found

    def parse_example(self, example: str) -> tuple[str, tuple[Literal, ...], Literal]:
        """Parse ``(op lit ...) = lit`` into (op, args, result)."""
        text = example.strip()
        if text.lower().startswith("example:"):
            text = text[len("example:"):].strip()
        lhs, sep, rhs = text.rpartition(" = ")
        forms = _read_sexprs(lhs) if sep else []
        result = _literal(rhs.strip())
        if len(forms) != 1 or not isinstance(forms[0], list) or not forms[0] or result is None:
            raise ValueError(f"Unparseable example: {example!r}")
        head, *args = forms[0]
        lits = tuple(_literal(a) for a in args)
        if not isinstance(head, str) or any(lit is None for lit in lits):
            raise ValueError(f"Example must be a flat call on literals: {example!r}")
        return head, lits, result  # type: ignore[return-value]

    def _apply(self, canonical_op: str, args: tuple[Literal, ...]) -> Literal | None:
        """Run a canonical operation through the real engine; None if it errors."""
        rendered = " ".join(
            ("true" if v else "false") if t == "bool" else str(v) for t, v in args
        )
        res = self._engine.execute(f"({canonical_op} {rendered})", self._spec)
        if res.status != "success":
            return None
        return ("bool" if isinstance(res.value, bool) else "int", res.value)

    def candidates(
        self, arity: int, examples: list[tuple[tuple[Literal, ...], Literal]]
    ) -> list[str]:
        """Canonical operations of the examples' type class consistent with all examples."""
        out = []
        for name, info in sorted(self._operations.items()):
            if info.arity != arity or name == "if":
                continue
            if any(
                t != ty and ty != "any"
                for args, _ in examples
                for (t, _v), ty in zip(args, info.arg_types)
            ):
                continue
            if any(r[0] != info.return_type and info.return_type != "any" for _, r in examples):
                continue
            if all(self._apply(name, args) == res for args, res in examples):
                out.append(name)
        return out

    def check(self, query: str, examples: list[str]) -> tuple[bool, str]:
        """Return (True, "") if every query operator has exactly one consistent meaning."""
        try:
            operators = self.query_operators(query)
            parsed = [self.parse_example(e) for e in examples]
        except ValueError as e:
            return False, str(e)
        for op, arity in sorted(operators.items()):
            mine = [(args, res) for head, args, res in parsed if head == op]
            if not mine:
                return False, f"Operator '{op}' in query has no examples"
            seen: dict[Any, Any] = {}
            for args, res in mine:
                if len(args) != arity:
                    return False, (
                        f"Operator '{op}' example arity {len(args)} differs from query arity {arity}"
                    )
                if seen.setdefault(args, res) != res:
                    return False, (
                        f"Examples contradict for operator '{op}' on args {[v for _, v in args]}"
                    )
            cands = self.candidates(arity, mine)
            if not cands:
                return False, f"Operator '{op}' matches no canonical operation consistent with its examples"
            if len(cands) > 1:
                return False, f"Operator '{op}' is ambiguous between {cands}"
        return True, ""
