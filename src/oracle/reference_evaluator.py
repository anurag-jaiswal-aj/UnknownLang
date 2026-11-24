"""Independent recursive reference evaluator for UnknownLang.

This is the project's test oracle: a deliberately simple tree-walking interpreter that
uses ordinary Python recursion. It exists so the production evaluator can be checked
against a second implementation that shares no evaluation code with it.

Independence rules (enforced by tests/test_oracle_reference.py):
* It shares DATA TYPES only, from ``src.execution.types`` (no project imports there).
* It must NOT import ``src.execution.engine``, ``src.execution.iterative_evaluator`` or
  any other production execution helper. Importing it must not load them either.
* Its arithmetic, boolean, IF and function-call logic is its own.

Limits of the oracle:
* It uses Python recursion for user-function calls, so it is only reliable for programs
  nested well below Python's recursion limit (measured: 75 nested calls under the default
  limit, fewer from a deep stack such as a test runner). Use it for
  differential comparison on small programs, not as a production engine.
* Its step and call-depth counters are legacy and are NOT the canonical resource-limit
  contract (see the iterative evaluator). Compare status and value, not step counts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from lark import Lark, Token, Tree

from src.language.generator import LanguageSpec
from src.language.semantics import OperationInfo


from src.execution.types import (
    DEFAULT_MAX_AST_DEPTH,
    DEFAULT_MAX_CALL_DEPTH,
    DEFAULT_MAX_STEPS,
    MAX_INT64,
    MIN_INT64,
    AstDepthExceeded,
    ExecutionError,
    ExecutionResult,
    OutputLimitExceeded,
    RecursionLimitExceeded,
    StepLimitExceeded,
)


@dataclass
class ReferenceContext:
    """Execution context for evaluation."""
    max_steps: int = DEFAULT_MAX_STEPS
    max_ast_depth: int = DEFAULT_MAX_AST_DEPTH
    max_call_depth: int = DEFAULT_MAX_CALL_DEPTH

    steps: int = 0
    call_depth: int = 0
    output_buffer: str = ""

    # Language-specific semantic configuration
    arithmetic_mode: str = "wraparound"
    short_circuit_mode: bool = True

    # Function environment: name -> (params, body, parent_env)
    functions: dict[str, tuple[tuple[str, ...], Tree, ReferenceContext | None]] = None

    # Variable bindings for function parameters (dict mapping param name to value)
    bindings: dict[str, Any] = None

    def __post_init__(self) -> None:
        if self.functions is None:
            object.__setattr__(self, 'functions', {})
        if self.bindings is None:
            object.__setattr__(self, 'bindings', {})

    def with_bindings(self, bindings: dict[str, Any]) -> ReferenceContext:
        """Return a new context with updated bindings."""
        return ReferenceContext(
            max_steps=self.max_steps,
            max_ast_depth=self.max_ast_depth,
            max_call_depth=self.max_call_depth,
            steps=self.steps,
            call_depth=self.call_depth,
            output_buffer=self.output_buffer,
            arithmetic_mode=self.arithmetic_mode,
            short_circuit_mode=self.short_circuit_mode,
            functions=self.functions,
            bindings=bindings,
        )

    def with_functions(self, functions: dict[str, tuple[tuple[str, ...], Tree, ReferenceContext | None]]) -> ReferenceContext:
        """Return a new context with updated functions."""
        return ReferenceContext(
            max_steps=self.max_steps,
            max_ast_depth=self.max_ast_depth,
            max_call_depth=self.max_call_depth,
            steps=self.steps,
            call_depth=self.call_depth,
            output_buffer=self.output_buffer,
            arithmetic_mode=self.arithmetic_mode,
            short_circuit_mode=self.short_circuit_mode,
            functions=functions,
            bindings=self.bindings,
        )

    def increment_steps(self, amount: int = 1) -> None:
        """Increment step counter, raising if limit exceeded."""
        self.steps += amount
        if self.steps > self.max_steps:
            raise StepLimitExceeded(f"Step limit exceeded: {self.steps} > {self.max_steps}")

    def increment_call_depth(self) -> int:
        """Increment call depth, returning new depth. Raises if limit exceeded."""
        self.call_depth += 1
        if self.call_depth > self.max_call_depth:
            raise RecursionLimitExceeded(f"Call depth exceeded: {self.call_depth} > {self.max_call_depth}")
        return self.call_depth

    def decrement_call_depth(self) -> None:
        """Decrement call depth."""
        self.call_depth = max(0, self.call_depth - 1)

    def add_output(self, text: str) -> None:
        """Add text to output buffer, raising if limit exceeded."""
        self.output_buffer += text
        if len(self.output_buffer) > 1_048_576:  # 1 MB
            raise OutputLimitExceeded("Output size exceeded")


class ReferenceEvaluator:
    """
    Independent recursive reference evaluator (the project's test oracle).

    Parses a program with Lark using the generated grammar and evaluates the AST by plain
    recursion, applying the LanguageSpec's arithmetic and boolean semantics. See the module
    docstring for the independence rules and the limits of this implementation.
    """

    def __init__(self) -> None:
        """Initialize the reference evaluator."""
        self._parser_cache: dict[str, Lark] = {}

    def _get_parser(self, grammar: str) -> Lark:
        """Get or create a Lark parser for the given grammar."""
        if grammar not in self._parser_cache:
            self._parser_cache[grammar] = Lark(grammar, start="program")
        return self._parser_cache[grammar]

    def execute(self, program_text: str, language_spec: LanguageSpec) -> ExecutionResult:
        """
        Execute a program in the given language.

        Args:
            program_text: The program source code to execute
            language_spec: The LanguageSpec containing grammar and semantics

        Returns:
            ExecutionResult with status, value, and output
        """
        try:
            # Parse the program
            grammar = language_spec.grammar
            parser = self._get_parser(grammar)
            tree = parser.parse(program_text)

            # Build initial execution context
            context = ReferenceContext(
                arithmetic_mode=language_spec.semantics.arithmetic_mode,
                short_circuit_mode=language_spec.semantics.short_circuit_mode,
            )

            # Evaluate the program tree
            result = self._eval_program(tree, context, language_spec)

            return ExecutionResult(
                status="success",
                value=result,
                output=context.output_buffer,
            )

        except ExecutionError as e:
            # Map exceptions to status types
            if isinstance(e, StepLimitExceeded):
                status = "step_limit_exceeded"
            elif isinstance(e, RecursionLimitExceeded):
                status = "recursion_limit_exceeded"
            elif isinstance(e, AstDepthExceeded):
                status = "ast_depth_exceeded"
            elif isinstance(e, OutputLimitExceeded):
                status = "output_limit_exceeded"
            else:
                status = "error"
            return ExecutionResult(
                status=status,
                error_message=str(e),
            )
        except Exception as e:
            return ExecutionResult(
                status="error",
                error_message=f"Runtime error: {str(e)}",
            )

    def _eval_program(self, tree: Tree, context: ReferenceContext, language_spec: LanguageSpec) -> Any:
        """Evaluate a program (list of statements/expressions)."""
        # Process declarations first (defs), then evaluate expressions
        declarations = []
        expressions = []

        for child in tree.children:
            if isinstance(child, Tree):
                if child.data == "def_decl":
                    declarations.append(child)
                else:
                    expressions.append(child)
            else:
                expressions.append(child)

        # Process declarations (function definitions)
        functions = dict(context.functions)
        for decl in declarations:
            self._eval_def(decl, functions, context, language_spec)

        # Evaluate expressions sequentially, return last value
        result = None
        for expr in expressions:
            result = self._eval(expr, context.with_functions(functions), language_spec)

        return result

    def _eval_def(self, tree: Tree, functions: dict[str, tuple[tuple[str, ...], Tree, ReferenceContext | None]],
                  context: ReferenceContext, language_spec: LanguageSpec) -> None:
        """Evaluate a function definition."""
        # Find the identifier and parameters
        identifier = None
        params = []
        body = None

        for child in tree.children:
            if isinstance(child, Token):
                if child.type == "IDENTIFIER":
                    identifier = child.value
            elif isinstance(child, Tree):
                if child.data == "param_list":
                    params = [c.value for c in child.children if isinstance(c, Token) and c.type == "IDENTIFIER"]
                elif child.data == "expr":
                    # Wave 1B: single expression as function body
                    body = child

        if identifier is None:
            raise ExecutionError("Function definition missing identifier")

        functions[identifier] = (tuple(params), body, context)

    def _eval(self, node: Any, context: ReferenceContext, language_spec: LanguageSpec) -> Any:
        """Evaluate a node in the AST."""
        context.increment_steps()

        if isinstance(node, Tree):
            return self._eval_tree(node, context, language_spec)
        elif isinstance(node, str):
            return self._eval_token(node, context, language_spec)
        else:
            return node

    def _eval_tree(self, tree: Tree, context: ReferenceContext, language_spec: LanguageSpec) -> Any:
        """Evaluate a Tree node."""
        rule_name = tree.data

        handlers = {
            "program": self._eval_program,
            "expr": self._eval_expr,
            "call": self._eval_call,
            "if_expr": self._eval_if,
            "literal": self._eval_literal,
            "def_decl": lambda t, c, l: self._eval_def(t, c.functions, c, l),
        }

        handler = handlers.get(rule_name)
        if handler:
            return handler(tree, context, language_spec)

        if tree.children:
            return self._eval(tree.children[0], context, language_spec)
        return None

    def _eval_expr(self, tree: Tree, context: ReferenceContext, language_spec: LanguageSpec) -> Any:
        """Evaluate an expression."""
        if tree.children:
            return self._eval(tree.children[0], context, language_spec)
        return None

    def _eval_call(self, tree: Tree, context: ReferenceContext, language_spec: LanguageSpec) -> Any:
        """Evaluate a function call."""
        # Find the function name
        func_name = None
        args = []

        for child in tree.children:
            if isinstance(child, Token):
                if child.type == "IDENTIFIER":
                    func_name = child.value
            elif isinstance(child, Tree):
                if child.data == "expr":
                    args.append(child)

        if func_name is None:
            raise ExecutionError("Call missing function identifier")

        # Check if it's a built-in operation or user-defined function
        if func_name in language_spec.builtins:
            return self._eval_builtin(func_name, args, context, language_spec)
        elif func_name in context.functions:
            return self._eval_user_func(func_name, args, context, language_spec)
        else:
            raise ExecutionError(f"Unknown function: {func_name}")

    def _eval_builtin(self, func_name: str, args: list[Tree], context: ReferenceContext,
                      language_spec: LanguageSpec) -> Any:
        """Evaluate a built-in operation."""
        # Dispatch based on operation type
        if func_name in {"add", "sub", "mul", "div", "mod"}:
            return self._eval_arithmetic(func_name, args, context, language_spec)
        elif func_name in {"and", "or"}:
            return self._eval_boolean_op(func_name, args, context, language_spec)
        elif func_name == "not":
            return self._eval_not(args, context, language_spec)
        elif func_name == "eq":
            return self._eval_eq(args, context, language_spec)
        elif func_name == "if":
            return self._eval_if_builtin(args, context, language_spec)
        else:
            raise ExecutionError(f"Unknown built-in operation: {func_name}")

    def _eval_arithmetic(self, op_name: str, args: list[Tree], context: ReferenceContext,
                         language_spec: LanguageSpec) -> int:
        """Evaluate arithmetic operation with selected mode."""
        context.increment_steps()

        if len(args) != 2:
            raise ExecutionError(f"Arithmetic operation '{op_name}' requires 2 arguments, got {len(args)}")

        # Evaluate arguments
        context.increment_steps()
        a = self._eval(args[0], context, language_spec)
        context.increment_steps()
        b = self._eval(args[1], context, language_spec)

        # Validate types
        if not isinstance(a, int) or not isinstance(b, int):
            raise ExecutionError(f"Arithmetic operation '{op_name}' requires integer arguments")

        mode = context.arithmetic_mode

        if op_name == "add":
            return self._apply_arithmetic(a, b, lambda x, y: x + y, mode)
        elif op_name == "sub":
            return self._apply_arithmetic(a, b, lambda x, y: x - y, mode)
        elif op_name == "mul":
            return self._apply_arithmetic(a, b, lambda x, y: x * y, mode)
        elif op_name == "div":
            return self._apply_division(a, b, mode)
        elif op_name == "mod":
            return self._apply_modulo(a, b, mode)
        else:
            raise ExecutionError(f"Unknown arithmetic operation: {op_name}")

    def _apply_arithmetic(self, a: int, b: int, operation: callable, mode: str) -> int:
        """Apply arithmetic operation with the given mode."""
        result = operation(a, b)

        if mode == "wraparound":
            unsigned_result = result & 0xFFFFFFFFFFFFFFFF
            if unsigned_result > 0x7FFFFFFFFFFFFFFF:
                return unsigned_result - 0x10000000000000000
            return unsigned_result
        elif mode == "saturating":
            if result > MAX_INT64:
                return MAX_INT64
            elif result < MIN_INT64:
                return MIN_INT64
            return result
        elif mode == "error-on-overflow":
            if result > MAX_INT64 or result < MIN_INT64:
                raise OverflowError(f"Integer overflow: {a} {operation.__name__} {b}")
            return result
        else:
            raise ExecutionError(f"Unknown arithmetic mode: {mode}")

    def _apply_division(self, a: int, b: int, mode: str) -> int:
        """Apply division with truncation toward zero."""
        if b == 0:
            raise ZeroDivisionError("Division by zero")

        if (a >= 0 and b >= 0) or (a <= 0 and b <= 0):
            result = abs(a) // abs(b)
        else:
            result = - (abs(a) // abs(b))

        # The only quotient outside signed 64-bit range is INT64_MIN / -1 (= 2**63).
        if mode == "error-on-overflow":
            if result > MAX_INT64 or result < MIN_INT64:
                raise OverflowError(f"Integer overflow: {a} / {b}")
        elif mode == "wraparound":
            # Shift into [0, 2**64), reduce, shift back: 2**63 -> INT64_MIN.
            result = (result - MIN_INT64) % (2 ** 64) + MIN_INT64
        elif mode == "saturating":
            result = min(MAX_INT64, max(MIN_INT64, result))

        return result

    def _apply_modulo(self, a: int, b: int, mode: str) -> int:
        """Apply modulo with sign following dividend."""
        if b == 0:
            raise ZeroDivisionError("Modulo by zero")

        if (a >= 0 and b >= 0) or (a <= 0 and b <= 0):
            trunc_result = abs(a) // abs(b)
        else:
            trunc_result = - (abs(a) // abs(b))

        remainder = a - trunc_result * b
        return remainder

    def _eval_boolean_op(self, op_name: str, args: list[Tree], context: ReferenceContext,
                         language_spec: LanguageSpec) -> bool:
        """Evaluate boolean operation (and/or) with short-circuit support."""
        context.increment_steps()

        if len(args) != 2:
            raise ExecutionError(f"Boolean operation '{op_name}' requires 2 arguments, got {len(args)}")

        short_circuit = context.short_circuit_mode

        # Evaluate left operand
        context.increment_steps()
        left_value = self._eval(args[0], context, language_spec)

        if not isinstance(left_value, bool):
            raise ExecutionError(f"Boolean operation requires boolean arguments, got {type(left_value).__name__}")

        if op_name == "and":
            if not left_value:  # False
                if short_circuit:
                    return False  # Don't evaluate right
                else:
                    context.increment_steps()
                    right_value = self._eval(args[1], context, language_spec)
                    if not isinstance(right_value, bool):
                        raise ExecutionError(f"Boolean operation requires boolean arguments, got {type(right_value).__name__}")
                    return False
            else:  # True
                if short_circuit:
                    context.increment_steps()
                    right_value = self._eval(args[1], context, language_spec)
                    if not isinstance(right_value, bool):
                        raise ExecutionError(f"Boolean operation requires boolean arguments, got {type(right_value).__name__}")
                    return right_value
                else:
                    context.increment_steps()
                    right_value = self._eval(args[1], context, language_spec)
                    if not isinstance(right_value, bool):
                        raise ExecutionError(f"Boolean operation requires boolean arguments, got {type(right_value).__name__}")
                    return right_value

        elif op_name == "or":
            if left_value:  # True
                if short_circuit:
                    return True  # Don't evaluate right
                else:
                    context.increment_steps()
                    right_value = self._eval(args[1], context, language_spec)
                    if not isinstance(right_value, bool):
                        raise ExecutionError(f"Boolean operation requires boolean arguments, got {type(right_value).__name__}")
                    return True
            else:  # False
                if short_circuit:
                    context.increment_steps()
                    right_value = self._eval(args[1], context, language_spec)
                    if not isinstance(right_value, bool):
                        raise ExecutionError(f"Boolean operation requires boolean arguments, got {type(right_value).__name__}")
                    return right_value
                else:
                    context.increment_steps()
                    right_value = self._eval(args[1], context, language_spec)
                    if not isinstance(right_value, bool):
                        raise ExecutionError(f"Boolean operation requires boolean arguments, got {type(right_value).__name__}")
                    return right_value

        raise ExecutionError(f"Unknown boolean operation: {op_name}")

    def _eval_not(self, args: list[Tree], context: ReferenceContext, language_spec: LanguageSpec) -> bool:
        """Evaluate not operation."""
        context.increment_steps()

        if len(args) != 1:
            raise ExecutionError(f"not requires 1 argument, got {len(args)}")

        context.increment_steps()
        value = self._eval(args[0], context, language_spec)

        if not isinstance(value, bool):
            raise ExecutionError(f"not requires boolean argument, got {type(value).__name__}")

        return not value

    def _eval_eq(self, args: list[Tree], context: ReferenceContext, language_spec: LanguageSpec) -> bool:
        """Evaluate equality comparison."""
        context.increment_steps()

        if len(args) != 2:
            raise ExecutionError(f"eq requires 2 arguments, got {len(args)}")

        context.increment_steps()
        left = self._eval(args[0], context, language_spec)
        context.increment_steps()
        right = self._eval(args[1], context, language_spec)

        return left == right

    def _eval_if(self, tree: Tree, context: ReferenceContext, language_spec: LanguageSpec) -> Any:
        """Evaluate if-expression (if condition then else)."""
        context.increment_steps()

        condition = None
        then_branch = None
        else_branch = None

        for child in tree.children:
            if isinstance(child, Tree):
                if child.data == "expr":
                    if condition is None:
                        condition = child
                    elif then_branch is None:
                        then_branch = child
                    else:
                        else_branch = child

        if condition is None or then_branch is None or else_branch is None:
            raise ExecutionError("if expression missing required branches")

        # Evaluate condition
        context.increment_steps()
        cond_value = self._eval(condition, context, language_spec)

        if not isinstance(cond_value, bool):
            raise ExecutionError(f"if condition must be boolean, got {type(cond_value).__name__}")

        # Evaluate only the selected branch (short-circuit)
        if cond_value:
            return self._eval(then_branch, context, language_spec)
        else:
            return self._eval(else_branch, context, language_spec)

    def _eval_if_builtin(self, args: list[Tree], context: ReferenceContext,
                         language_spec: LanguageSpec) -> Any:
        """Evaluate if builtin (after arguments are pre-evaluated)."""
        context.increment_steps()

        if len(args) != 3:
            raise ExecutionError(f"if requires 3 arguments, got {len(args)}")

        # Evaluate arguments
        context.increment_steps()
        cond_value = self._eval(args[0], context, language_spec)
        context.increment_steps()
        then_value = self._eval(args[1], context, language_spec)
        context.increment_steps()
        else_value = self._eval(args[2], context, language_spec)

        if not isinstance(cond_value, bool):
            raise ExecutionError(f"if condition must be boolean, got {type(cond_value).__name__}")

        if cond_value:
            return then_value
        else:
            return else_value

    def _eval_user_func(self, func_name: str, args: list[Tree], context: ReferenceContext,
                        language_spec: LanguageSpec) -> Any:
        """Evaluate a user-defined function call."""
        context.increment_steps()

        # Check call depth
        context.increment_call_depth()

        try:
            params, body, parent_context = context.functions[func_name]

            # Evaluate arguments (left-to-right) with current bindings
            evaluated_args = []
            for arg in args:
                context.increment_steps()
                value = self._eval(arg, context, language_spec)
                evaluated_args.append(value)

            # Check argument count
            if len(evaluated_args) != len(params):
                raise ExecutionError(
                    f"Function '{func_name}' expected {len(params)} arguments, got {len(evaluated_args)}"
                )

            # Lexical scoping (design.md, semantics.scoping = "lexical"): the body sees ONLY
            # its own parameters. Variables of the caller are deliberately not inherited.
            new_bindings = dict(zip(params, evaluated_args))

            # Evaluate body with new bindings
            result = self._eval(body, context.with_bindings(new_bindings), language_spec)

            return result

        finally:
            context.decrement_call_depth()

    def _eval_literal(self, tree: Tree, context: ReferenceContext, language_spec: LanguageSpec) -> Any:
        """Evaluate a literal value."""
        if tree.children:
            child = tree.children[0]
            if isinstance(child, Token):
                return self._eval_token(child.value, context, language_spec)
        return None

    def _eval_token(self, token: str, context: ReferenceContext, language_spec: LanguageSpec) -> Any:
        """Evaluate a token (identifier, number, boolean)."""
        context.increment_steps()

        if token == "true":
            return True
        elif token == "false":
            return False
        elif token.isdigit() or (token.startswith("-") and token[1:].isdigit()):
            return int(token)
        else:
            # It's an identifier - look it up in bindings
            if token in context.bindings:
                return context.bindings[token]
            raise ExecutionError(f"Unknown identifier: {token}")
