"""Iterative evaluator for UnknownLang recursion proof.

This module provides a standalone IterativeEvaluator that uses an explicit
frame stack to evaluate programs iteratively, avoiding Python recursion
for user function calls.

Key features:
- Single unified iterative evaluation loop
- Explicit frame stack for user function calls (NO Python recursion)
- Depth limit: 100 (DEFAULT_MAX_CALL_DEPTH)
- Full MVP semantic support: arithmetic modes, boolean modes, 64-bit integers
- Function arity validation, undefined identifier errors
- Resource limits, each enforced independently:
  * AST depth: static, before execution (``_validate_ast_depth``)
  * Execution steps: one per expression node evaluated (see ``_handle_expr_frame``)
  * Call depth: active user-function invocations
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from lark import Lark, Token, Tree

from src.language.generator import LanguageSpec
from src.language.semantics import BUILTIN_OPERATIONS


# Shared data types and constants live in src.execution.types (no project imports there).
# Names are re-exported here, so existing imports from this module keep working.
from src.execution.types import (  # noqa: F401  (re-exports)
    DEFAULT_MAX_AST_DEPTH,
    DEFAULT_MAX_CALL_DEPTH,
    DEFAULT_MAX_OUTPUT_BYTES,
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

# Grammar rules that are semantic expression nodes. These are the ONLY nodes
# that (a) count toward AST depth and (b) are charged one execution step when
# evaluated. Grammar wrappers (program, program_element, expr) and declarations
# (def_decl, param_list) are deliberately absent.
_SEMANTIC_EXPRESSION_RULES: frozenset = frozenset({"literal", "call", "if_expr"})


class FrameType(Enum):
    """Types of frames in the evaluation stack."""
    EXPR = auto()              # General expression evaluation
    CALL = auto()              # Function call (built-in or user)
    ARGUMENT = auto()          # Argument evaluation for calls
    USER_FUNC_ENTRY = auto()   # Entering user function (depth check)
    USER_FUNC_BODY = auto()    # Evaluating user function body
    BUILTIN = auto()           # Built-in operation evaluation
    IF_CONDITION = auto()      # If expression condition evaluation
    IF_BRANCH = auto()         # If expression branch selection
    SC_AND = auto()            # Short-circuit AND evaluation continuation
    SC_OR = auto()             # Short-circuit OR evaluation continuation
    RETURN = auto()              # Return value propagation


@dataclass(frozen=True)
class Frame:
    """A single frame in the evaluation stack."""
    frame_type: FrameType
    # Data specific to frame type:
    expr: Any = None             # For EXPR frame: the expression tree
    func_name: str = None        # For CALL/USER_FUNC frames: function name
    args: list = None            # For CALL frame: argument trees
    arg_index: int = 0           # For ARGUMENT frame: which argument we're evaluating
    arg_values: list = None      # For ARGUMENT frame: accumulated argument values
    params: tuple = None         # For USER_FUNC frames: parameter names
    body: Any = None             # For USER_FUNC_BODY frame: function body
    bindings: dict = None        # For USER_FUNC_BODY frame: parameter bindings
    builtin_op: str = None       # For BUILTIN frame: operation name
    builtin_args: list = None    # For BUILTIN frame: arguments
    condition: Any = None        # For IF frames: condition tree
    then_branch: Any = None      # For IF frames: then branch tree
    else_branch: Any = None      # For IF frames: else branch tree
    result: Any = None           # For RETURN frame: return value
    depth_at_entry: int = 0      # For USER_FUNC frames: depth when entry started
    # For depth-restoring RETURN frames
    restore_depth: bool = False  # True if this frame restores depth and bindings
    old_bindings: dict = None    # Original bindings to restore (for depth-restoring)
    depth_to_restore: int = 0    # Depth to restore to (for depth-restoring)
    # For short-circuit boolean frames
    operand_index: int = 0       # For SC frames: which operand to evaluate next
    remaining_args: list = None  # For SC frames: unevaluated argument expressions
    short_circuit: bool = True   # For SC frames: short_circuit mode setting
    # Legacy depth bookkeeping. NOT used for enforcement: AST depth is validated
    # statically by IterativeEvaluator._validate_ast_depth before execution, and
    # these values do not follow its convention. Retained only to keep this change
    # scoped; safe to remove in a follow-up cleanup.
    ast_depth: int = 0
    if_depth: int = 0
    sc_depth: int = 0


def _validate_limit(name: str, value: int | None) -> int | None:
    """Validate one resource-limit argument. ``None`` means "use the default".

    Accepts exact ``int`` values >= 0 (zero is meaningful: it rejects the first
    expression, any non-empty program, or the first user call respectively).
    ``bool`` is rejected explicitly because ``True``/``False`` are ints in Python.
    """
    if value is None:
        return None
    if type(value) is not int:
        raise TypeError(f"{name} must be an int or None, got {type(value).__name__}")
    if value < 0:
        raise ValueError(f"{name} must be >= 0, got {value}")
    return value


class IterativeEvaluator:
    """
    Iterative evaluator for UnknownLang programs.
    
    Uses an explicit frame stack to evaluate programs without Python recursion,
    enabling deep tail-recursive calls (up to the depth limit).
    
    The evaluator supports:
    - Literals: numbers, booleans
    - Variables: identifier references
    - Functions: user-defined with parameters
    - Conditionals: if expressions
    - Built-ins: add, sub, mul, div, mod, and, or, not, eq, if
    
    Frame types:
    - EXPR: General expression evaluation (wrapper)
    - CALL: Function call dispatch
    - ARGUMENT: Left-to-right argument evaluation
    - USER_FUNC_ENTRY: Entering user function (depth check)
    - USER_FUNC_BODY: Evaluating function body with bindings
    - BUILTIN: Built-in operation evaluation
    - IF_CONDITION: If expression condition evaluation
    - IF_BRANCH: If expression branch selection
    - RETURN: Return value propagation
    
    Resource limits:
    - max_ast_depth: Maximum semantic expression nesting (static validation)
    - max_steps: Maximum semantic expression evaluations (runtime)
    - max_call_depth: Maximum user-function invocations (runtime)
    
    AST depth convention (semantic expression-node depth):
    - Each independent expression root starts at depth 1
    - Calls, IF expressions count as expressions
    - Grammar wrappers (program, program_element, expr) don't count
    - Function declarations don't count as expressions
    - Every child expression increases depth by one
    - Both IF branches must be validated (even unselected)
    - Both short-circuit operands must be validated
    - All function bodies must be validated (even uncalled)
    """
    
    def __init__(
        self,
        *,
        max_steps: int | None = None,
        max_ast_depth: int | None = None,
        max_call_depth: int | None = None,
    ) -> None:
        """Initialize the iterative evaluator.

        Args:
            max_steps: Execution-step budget (default ``DEFAULT_MAX_STEPS``).
            max_ast_depth: Static AST-depth limit (default ``DEFAULT_MAX_AST_DEPTH``).
            max_call_depth: Active user-function invocation limit
                (default ``DEFAULT_MAX_CALL_DEPTH``).

        Each is an ``int >= 0`` or ``None`` for the default. Invalid values raise
        ``TypeError`` / ``ValueError`` immediately, naming the parameter. The limits are
        resolved once here and applied to every ``execute`` call; each call gets a fresh
        context, so no execution state is shared between calls.
        """
        steps = _validate_limit("max_steps", max_steps)
        ast_depth = _validate_limit("max_ast_depth", max_ast_depth)
        call_depth = _validate_limit("max_call_depth", max_call_depth)
        self._max_steps = DEFAULT_MAX_STEPS if steps is None else steps
        self._max_ast_depth = DEFAULT_MAX_AST_DEPTH if ast_depth is None else ast_depth
        self._max_call_depth = DEFAULT_MAX_CALL_DEPTH if call_depth is None else call_depth
        self._parser_cache: dict[str, Lark] = {}
    
    def _get_parser(self, grammar: str) -> Lark:
        """Get or create a Lark parser for the given grammar."""
        if grammar not in self._parser_cache:
            self._parser_cache[grammar] = Lark(grammar, start="program")
        return self._parser_cache[grammar]
    
    def _validate_ast_depth(self, tree: Tree, max_ast_depth: int) -> int:
        """Statically validate syntactic expression depth. Executes nothing.

        Convention (semantic expression-node depth):
        - Every ``literal``, ``call`` and ``if_expr`` node is an expression node.
        - An independent root expression sits at depth 1. Roots are every
          top-level expression and every ``def`` body (called or not).
        - Every child expression of a call / if_expr sits one level deeper
          (call arguments; if condition, then and else branches). Unselected
          branches and short-circuit operands are traversed like any other.
        - Grammar wrappers (program, program_element, expr) and declarations
          (def_decl, param_list) add no depth.

        The traversal is an explicit worklist (no Python recursion). The result
        is the maximum depth over all roots; it is rejected when it exceeds
        ``max_ast_depth`` (max accepted, max + 1 rejected).

        Raises:
            AstDepthExceeded: if the deepest expression node is deeper than the limit.
        """
        worklist: list[tuple[Any, int]] = [(tree, 1)]
        deepest = 0

        while worklist:
            node, depth = worklist.pop()
            if not isinstance(node, Tree):
                continue  # tokens carry no nesting
            rule = node.data

            if rule in _SEMANTIC_EXPRESSION_RULES:
                if depth > deepest:
                    deepest = depth
                if rule != "literal":
                    for child in node.children:
                        if isinstance(child, Tree) and child.data == "expr":
                            worklist.append((child, depth + 1))
            elif rule == "def_decl":
                # Function body is its own root at depth 1; the declaration itself adds nothing.
                for child in node.children:
                    if isinstance(child, Tree) and child.data == "expr":
                        worklist.append((child, 1))
            else:
                # program / program_element / expr wrappers: transparent for depth.
                for child in node.children:
                    worklist.append((child, depth))

        if deepest > max_ast_depth:
            raise AstDepthExceeded(f"AST depth exceeded: {deepest} > {max_ast_depth}")
        return deepest

    def _validate_int_literals(self, tree: Tree) -> None:
        """Statically reject integer literals outside the signed 64-bit range.

        Runs once after parsing and before any evaluation, so a bad literal is rejected
        wherever it appears: top level, nested, in a function body that is never called,
        or in an ``if`` branch that is never taken. It consumes no execution steps and is
        independent of the arithmetic mode: modes govern arithmetic results, never
        literal validity. ``INT64_MIN`` and ``INT64_MAX`` are accepted.

        Raises:
            ExecutionError: "Integer literal out of range: ..." (result status ``error``).
        """
        # iter_subtrees is iterative; Tree.scan_values is recursive and would overflow the
        # Python stack on deep programs that the explicit-stack evaluator is meant to accept.
        for node in tree.iter_subtrees():
            for token in node.children:
                if isinstance(token, Token) and token.type == "NUMBER":
                    if not (MIN_INT64 <= int(token.value) <= MAX_INT64):
                        raise ExecutionError(
                            f"Integer literal out of range: {token.value} "
                            f"(must be between {MIN_INT64} and {MAX_INT64})"
                        )

    def _new_context(
        self,
        language_spec: LanguageSpec,
        *,
        max_steps: int | None = None,
        max_ast_depth: int | None = None,
        max_call_depth: int | None = None,
    ) -> EvalContext:
        """Build the execution context. The ONLY place limits reach a running context.

        Precedence for each limit: explicit per-call argument (private, used by tests)
        > value given to the constructor > module default. The resulting context is the
        single source of truth for static validation and runtime.
        """
        return EvalContext(
            max_steps=self._max_steps if max_steps is None else max_steps,
            max_ast_depth=self._max_ast_depth if max_ast_depth is None else max_ast_depth,
            max_call_depth=self._max_call_depth if max_call_depth is None else max_call_depth,
            functions=dict(language_spec.builtins),
            arithmetic_mode=language_spec.semantics.arithmetic_mode,
            short_circuit_mode=language_spec.semantics.short_circuit_mode,
        )

    def execute(self, program_text: str, language_spec: LanguageSpec) -> ExecutionResult:
        """
        Execute a program in the given language iteratively.

        Args:
            program_text: The program source code to execute
            language_spec: The LanguageSpec containing grammar, semantics, and builtins

        Returns:
            ExecutionResult with status, value, and output
        """
        try:
            parser = self._get_parser(language_spec.grammar)
            tree = parser.parse(program_text)
            context = self._new_context(language_spec)
        except Exception as e:
            return ExecutionResult(status="error", error_message=f"Runtime error: {str(e)}")
        return self._run(tree, context, language_spec)

    def _run(self, tree: Tree, context: EvalContext, language_spec: LanguageSpec) -> ExecutionResult:
        """Validate then evaluate a parsed program using ``context``'s limits.

        Stage 1: static AST-depth validation against ``context.max_ast_depth``;
                 consumes no execution steps and evaluates nothing.
        Stage 2: frame-stack evaluation. Steps are charged per semantic
                 expression in ``_handle_expr_frame``, never per frame.
        """
        frame_stack: list[Frame] = []
        try:
            self._validate_ast_depth(tree, context.max_ast_depth)
            self._validate_int_literals(tree)

            frame_stack.append(Frame(frame_type=FrameType.EXPR, expr=tree, ast_depth=1))
            while frame_stack:
                frame = frame_stack[-1]
                self._process_frame(frame_stack, frame, context, language_spec)

            if context.result_stack:
                return ExecutionResult(
                    status="success",
                    value=context.result_stack[-1],
                    output=context.output_buffer,
                )
            if not tree.children:
                # Empty source (no program elements) is a valid program with no value.
                # Scoped to a childless program so a genuine "no result" bug in a
                # non-empty program is still reported as an error.
                return ExecutionResult(status="success", value=None, output=context.output_buffer)
            return ExecutionResult(
                status="error",
                error_message="No result produced",
                output=context.output_buffer,
            )
        except StepLimitExceeded as e:
            return ExecutionResult(status="step_limit_exceeded", error_message=str(e), output=context.output_buffer)
        except AstDepthExceeded as e:
            return ExecutionResult(status="ast_depth_exceeded", error_message=str(e), output=context.output_buffer)
        except OutputLimitExceeded as e:
            return ExecutionResult(status="output_limit_exceeded", error_message=str(e), output=context.output_buffer)
        except RecursionLimitExceeded as e:
            return ExecutionResult(status="recursion_limit_exceeded", error_message=str(e), output=context.output_buffer)
        except ExecutionError as e:
            return ExecutionResult(status="error", error_message=str(e), output=context.output_buffer)
        except Exception as e:
            return ExecutionResult(status="error", error_message=f"Runtime error: {str(e)}", output=context.output_buffer)
        finally:
            self._unwind_frames(frame_stack, context)

    @staticmethod
    def _unwind_frames(frame_stack: list[Frame], context: EvalContext) -> None:
        """Apply every still-pending call-return marker (innermost first).

        On normal completion the stack is empty and this is a no-op. After a
        failure it restores call_depth and bindings to the outermost caller's
        state, so each entered invocation is undone exactly once.
        """
        for pending in reversed(frame_stack):
            if pending.frame_type == FrameType.RETURN and pending.restore_depth:
                context.call_depth = pending.depth_to_restore
                if pending.old_bindings is not None:
                    context.bindings = pending.old_bindings

    def _process_frame(
        self,
        frame_stack: list[Frame],
        frame: Frame,
        context: EvalContext,
        language_spec: LanguageSpec,
    ) -> None:
        """Process a single frame and potentially push new frames."""
        handler = {
            FrameType.EXPR: self._handle_expr_frame,
            FrameType.CALL: self._handle_call_frame,
            FrameType.ARGUMENT: self._handle_argument_frame,
            FrameType.USER_FUNC_ENTRY: self._handle_user_func_entry_frame,
            FrameType.USER_FUNC_BODY: self._handle_user_func_body_frame,
            FrameType.BUILTIN: self._handle_builtin_frame,
            FrameType.IF_CONDITION: self._handle_if_condition_frame,
            FrameType.IF_BRANCH: self._handle_if_branch_frame,
            FrameType.SC_AND: self._handle_sc_and_frame,
            FrameType.SC_OR: self._handle_sc_or_frame,
            FrameType.RETURN: self._handle_return_frame,
        }[frame.frame_type]
        
        handler(frame_stack, frame, context, language_spec)
    
    def _handle_expr_frame(
        self,
        frame_stack: list[Frame],
        frame: Frame,
        context: EvalContext,
        language_spec: LanguageSpec,
    ) -> None:
        """Handle EXPR frame - dispatch to appropriate handler based on expression type.
        
        This is the single place execution steps are charged (see below). The
        ``ast_depth`` on frames is legacy bookkeeping and is not used to enforce
        any limit.
        """
        tree = frame.expr
        parent_depth = frame.ast_depth

        # SINGLE STEP-CHARGING POINT. One step is charged here, before evaluation
        # begins, for each semantic expression node (literal, call, if_expr) and
        # for nothing else. Wrappers (program, program_element, expr), declarations
        # and every non-EXPR frame (CALL, ARGUMENT, BUILTIN, RETURN, ...) are
        # bookkeeping and are never charged. A node that later fails has already
        # been charged; if the budget is exhausted this raises before the node is
        # evaluated. Nodes in unselected IF branches / skipped short-circuit
        # operands never reach this point, so they cost nothing.
        if isinstance(tree, Tree) and tree.data in _SEMANTIC_EXPRESSION_RULES:
            context.increment_steps()

        # Pop this frame
        frame_stack.pop()

        if isinstance(tree, Tree):
            rule = tree.data
            if rule == "call":
                # Call is a nested expression, so it increases depth
                new_depth = parent_depth + 1
                self._push_call_frame(frame_stack, tree, context, language_spec, new_depth)
            elif rule == "if_expr":
                self._push_if_frame(frame_stack, frame, tree, context, language_spec)
            elif rule == "literal":
                # Literal - evaluate and push result
                value = self._eval_literal(tree, context, language_spec)
                frame_stack.append(Frame(frame_type=FrameType.RETURN, result=value))
            elif rule == "def_decl":
                # Function definition - extract and store the function
                self._handle_def_decl_frame(frame_stack, tree, context, language_spec)
            elif rule == "expr":
                # Expr wrapper - push the child expression with parent depth (not incremented)
                # The expr node is a wrapper and doesn't add to the nesting depth
                if tree.children:
                    frame_stack.append(Frame(frame_type=FrameType.EXPR, expr=tree.children[0], ast_depth=parent_depth))
                else:
                    raise ExecutionError("expr has no children")
            elif rule == "program_element":
                # Program element - evaluate the child (either def_decl or expr)
                # Program element is a wrapper and doesn't add to nesting depth
                if tree.children:
                    frame_stack.append(Frame(frame_type=FrameType.EXPR, expr=tree.children[0], ast_depth=parent_depth))
                else:
                    raise ExecutionError("program_element has no children")
            elif rule == "program":
                # Program - process all program elements, evaluate last as result
                # Push all program elements in reverse order so first is processed first
                # The elements are processed left-to-right, with the last one being the result
                for child in reversed(tree.children):
                    frame_stack.append(Frame(frame_type=FrameType.EXPR, expr=child, ast_depth=parent_depth + 1))
        elif isinstance(tree, Token):
            # Token - it's an identifier or literal
            value = self._eval_token(tree, context, language_spec)
            frame_stack.append(Frame(frame_type=FrameType.RETURN, result=value))
        else:
            # Already a value
            frame_stack.append(Frame(frame_type=FrameType.RETURN, result=tree))
    
    def _handle_def_decl_frame(
        self,
        frame_stack: list[Frame],
        tree: Tree,
        context: EvalContext,
        language_spec: LanguageSpec,
    ) -> None:
        """Handle def_decl frame - extract function definition and store it."""
        # Parse def_decl: (def name (params) body)
        func_name = None
        params = []
        body = None
        
        for child in tree.children:
            if isinstance(child, Token) and child.type == "IDENTIFIER":
                if func_name is None:
                    func_name = child.value
                else:
                    # It's a parameter (but parameters are inside param_list subtree)
                    params.append(child.value)
            elif isinstance(child, Tree):
                if child.data == "param_list":
                    # Extract parameter identifiers from param_list subtree
                    for param_child in child.children:
                        if isinstance(param_child, Token) and param_child.type == "IDENTIFIER":
                            params.append(param_child.value)
                elif child.data == "expr":
                    # Wave 1B: single expression as function body
                    body = child
        if func_name is None or body is None:
            raise ExecutionError("def declaration missing required parts")
        
        # Store the function in context
        context.functions[func_name] = (tuple(params), body)
        
        # Push a success result
        frame_stack.append(Frame(frame_type=FrameType.RETURN, result=True))
    
    def _push_call_frame(
        self,
        frame_stack: list[Frame],
        tree: Tree,
        context: EvalContext,
        language_spec: LanguageSpec,
        parent_depth: int = 1,
    ) -> None:
        """Push a CALL frame to evaluate a function call.
        
        AST depth for function call: parent_depth (for the call itself).
        Function arguments are nested expressions, so they will be pushed
        with parent_depth + 1 by _handle_call_frame.
        """
        func_name = None
        args = []
        
        for child in tree.children:
            if isinstance(child, Token) and child.type == "IDENTIFIER":
                func_name = child.value
            elif isinstance(child, Tree) and child.data == "expr":
                args.append(child)
        
        if func_name is None:
            raise ExecutionError("Call missing function identifier")
        
        # Push a CALL frame with the depth for the call node itself (parent_depth)
        # Arguments will be evaluated with parent_depth + 1
        # Store the parent_depth for use when processing the CALL frame
        frame_stack.append(Frame(
            frame_type=FrameType.CALL,
            func_name=func_name,
            args=args,
            arg_index=0,
            arg_values=[],
            ast_depth=parent_depth,
        ))
    
    def _handle_call_frame(
        self,
        frame_stack: list[Frame],
        frame: Frame,
        context: EvalContext,
        language_spec: LanguageSpec,
    ) -> None:
        """Handle CALL frame - evaluate arguments or dispatch to function."""
        func_name = frame.func_name
        
        # For short-circuit boolean operations, handle differently
        if func_name in {"and", "or"} and context.short_circuit_mode:
            # Same arity rule as the eager path (_eval_boolean_op).
            if len(frame.args) != 2:
                raise ExecutionError(
                    f"Boolean operation '{func_name}' requires 2 arguments, got {len(frame.args)}"
                )
            parent_depth = frame.ast_depth

            # Replace the CALL frame with an SC frame. The SC frame owns operand
            # sequencing: operand_index counts operands dispatched so far and
            # arg_values holds the ones whose results it has already consumed.
            frame_stack.pop()
            frame_stack.append(Frame(
                frame_type=FrameType.SC_AND if func_name == "and" else FrameType.SC_OR,
                func_name=func_name,
                remaining_args=frame.args,
                operand_index=1,  # operand 0 is dispatched just below
                arg_values=[],
                short_circuit=True,
                sc_depth=parent_depth,
            ))
            frame_stack.append(Frame(
                frame_type=FrameType.EXPR,
                expr=frame.args[0],
                ast_depth=parent_depth + 1,
            ))
            return
        
        # Pop this frame first (we're done with it)
        frame_stack.pop()
        
        # Get parent depth from the CALL frame's ast_depth (set in _push_call_frame)
        # The CALL frame's depth is the parent's depth, arguments should be parent_depth + 1
        parent_depth = frame.ast_depth
        
        if frame.arg_index < len(frame.args):
            # Evaluate next argument
            arg_expr = frame.args[frame.arg_index]
            # Function arguments are nested expressions, so they increase depth by 1
            new_arg_depth = parent_depth + 1
            frame_stack.append(Frame(
                frame_type=FrameType.ARGUMENT,
                func_name=frame.func_name,
                args=frame.args,
                arg_index=frame.arg_index,
                arg_values=frame.arg_values,
                ast_depth=parent_depth,
            ))
            # Push EXPR frame with incremented depth for the nested argument
            frame_stack.append(Frame(frame_type=FrameType.EXPR, expr=arg_expr, ast_depth=new_arg_depth))
        else:
            # All arguments evaluated - dispatch to function
            self._evaluate_call(frame_stack, func_name, frame.arg_values, context, language_spec)
    
    def _handle_argument_frame(
        self,
        frame_stack: list[Frame],
        frame: Frame,
        context: EvalContext,
        language_spec: LanguageSpec,
    ) -> None:
        """Handle ARGUMENT frame - received argument value, push next argument or dispatch."""
        # Pop this frame first (we're done with it)
        frame_stack.pop()
        
        # Pop the return value from result stack
        if context.result_stack:
            arg_value = context.result_stack.pop()
        else:
            raise ExecutionError("No result for argument")
        
        # Update arg_values in a new frame
        new_arg_values = list(frame.arg_values) if frame.arg_values else []
        new_arg_values.append(arg_value)
        
        if frame.arg_index + 1 < len(frame.args):
            # Continue with next argument
            # Push CALL frame with same depth (we've evaluated this argument)
            frame_stack.append(Frame(
                frame_type=FrameType.CALL,
                func_name=frame.func_name,
                args=frame.args,
                arg_index=frame.arg_index + 1,
                arg_values=new_arg_values,
                ast_depth=frame.ast_depth,
            ))
        else:
            # Last argument - dispatch
            self._evaluate_call(frame_stack, frame.func_name, new_arg_values, context, language_spec)
    
    def _evaluate_call(
        self,
        frame_stack: list[Frame],
        func_name: str,
        arg_values: list,
        context: EvalContext,
        language_spec: LanguageSpec,
    ) -> None:
        """Evaluate a function call - dispatch to built-in or user function."""
        # Check if built-in
        if func_name in BUILTIN_OPERATIONS:
            # Short-circuit and/or never reach here: _handle_call_frame routes them to
            # SC frames. This path receives fully evaluated arguments (all other
            # builtins, and and/or in eager mode).
            frame_stack.append(Frame(
                frame_type=FrameType.BUILTIN,
                builtin_op=func_name,
                builtin_args=arg_values,
            ))
        elif func_name in context.functions:
            params, _body = context.functions[func_name]
            if len(arg_values) != len(params):
                raise ExecutionError(
                    f"Function '{func_name}' expected {len(params)} arguments, got {len(arg_values)}"
                )
            # User function - check depth first
            # Allow depth up to max_call_depth (inclusive)
            if context.call_depth >= context.max_call_depth:
                raise RecursionLimitExceeded(
                    f"Call depth exceeded: {context.call_depth} >= {context.max_call_depth}"
                )
            
            # Push USER_FUNC_ENTRY. Its argument values are delivered below as RETURN
            # frames and popped positionally by the entry handler; the result stack is
            # never wiped, so values other frames are waiting for stay intact.
            params, body = context.functions[func_name]
            frame_stack.append(Frame(
                frame_type=FrameType.USER_FUNC_ENTRY,
                func_name=func_name,
                params=params,
                body=body,
                depth_at_entry=context.call_depth,
            ))
            
            # Push arguments as return values
            for arg_value in reversed(arg_values):
                frame_stack.append(Frame(frame_type=FrameType.RETURN, result=arg_value))
        else:
            raise ExecutionError(f"Unknown function: {func_name}")
    
    def _handle_user_func_entry_frame(
        self,
        frame_stack: list[Frame],
        frame: Frame,
        context: EvalContext,
        language_spec: LanguageSpec,
    ) -> None:
        """Handle USER_FUNC_ENTRY frame - increment depth and push USER_FUNC_BODY."""
        # Pop argument values from result stack
        arg_values = []
        for _ in range(len(frame.params)):
            if context.result_stack:
                arg_values.append(context.result_stack.pop())
            else:
                raise ExecutionError("Not enough argument values")
        
        # Reverse to get correct order
        arg_values = list(reversed(arg_values))
        
        # Validate arity
        if len(arg_values) != len(frame.params):
            raise ExecutionError(
                f"Function '{frame.func_name}' expected {len(frame.params)} arguments, "
                f"got {len(arg_values)}"
            )
        
        # Create bindings
        bindings = dict(zip(frame.params, arg_values))
        
        # Get current depth (before increment)
        depth_before_entry = context.call_depth
        
        # Pop the entry frame
        frame_stack.pop()
        
        # Increment depth
        context.call_depth += 1
        
        # Push a return marker frame that will restore depth
        frame_stack.append(Frame(
            frame_type=FrameType.RETURN,
            result=None,  # Placeholder
            restore_depth=True,
            old_bindings=context.bindings,  # caller's environment, restored on return/failure
            depth_to_restore=depth_before_entry,
        ))
        
        # Push USER_FUNC_BODY
        frame_stack.append(Frame(
            frame_type=FrameType.USER_FUNC_BODY,
            func_name=frame.func_name,
            params=frame.params,
            body=frame.body,
            bindings=bindings,
            depth_at_entry=context.call_depth,
        ))
    
    def _handle_user_func_body_frame(
        self,
        frame_stack: list[Frame],
        frame: Frame,
        context: EvalContext,
        language_spec: LanguageSpec,
    ) -> None:
        """Handle USER_FUNC_BODY frame - evaluate function body with bindings."""
        # Pop this frame
        frame_stack.pop()
        
        # Switch to the callee's environment. The caller's bindings were already saved on
        # the restore marker pushed at function entry.
        context.bindings = frame.bindings

        # Evaluate body - push EXPR frame with depth 1 (function bodies are independent units)
        frame_stack.append(Frame(
            frame_type=FrameType.EXPR,
            expr=frame.body,
            ast_depth=1,
        ))
        
        # The depth-restoring RETURN frame was already pushed by USER_FUNC_ENTRY
        # It will be processed after this function's result is computed
    
    def _handle_builtin_frame(
        self,
        frame_stack: list[Frame],
        frame: Frame,
        context: EvalContext,
        language_spec: LanguageSpec,
    ) -> None:
        """Handle BUILTIN frame - evaluate built-in operation."""
        # Pop this frame
        frame_stack.pop()
        
        # Evaluate built-in based on operation
        result = self._eval_builtin(
            frame.builtin_op,
            frame.builtin_args,
            context,
            language_spec,
        )
        
        frame_stack.append(Frame(frame_type=FrameType.RETURN, result=result))
    
    def _handle_if_condition_frame(
        self,
        frame_stack: list[Frame],
        frame: Frame,
        context: EvalContext,
        language_spec: LanguageSpec,
    ) -> None:
        """Handle IF_CONDITION frame - received condition value, push branch."""
        # Pop condition result
        if context.result_stack:
            cond_value = context.result_stack.pop()
        else:
            raise ExecutionError("No result for condition")
        
        if not isinstance(cond_value, bool):
            raise ExecutionError(f"if condition must be boolean, got {type(cond_value).__name__}")
        
        # Pop IF_CONDITION frame
        frame_stack.pop()
        
        # The IF_CONDITION frame has an if_depth field for the depth of if expression evaluation
        # Child expressions inherit parent's depth
        if_depth = getattr(frame, 'if_depth', 1)
        
        # Select branch and evaluate
        # Branch evaluation inherits from if expression, but if_expr inside increments depth
        if cond_value:
            frame_stack.append(Frame(
                frame_type=FrameType.EXPR,
                expr=frame.then_branch,
                ast_depth=if_depth,
            ))
        else:
            frame_stack.append(Frame(
                frame_type=FrameType.EXPR,
                expr=frame.else_branch,
                ast_depth=if_depth,
            ))
    
    def _handle_if_branch_frame(
        self,
        frame_stack: list[Frame],
        frame: Frame,
        context: EvalContext,
        language_spec: LanguageSpec,
    ) -> None:
        """Handle IF_BRANCH frame - received branch result, return it."""
        # Pop this frame
        frame_stack.pop()
        
        # Result is already on result stack from branch evaluation
        # Nothing to do - the RETURN frame will propagate it
    
    def _step_short_circuit(
        self,
        frame_stack: list[Frame],
        frame: Frame,
        context: EvalContext,
        decisive: bool,
    ) -> None:
        """Advance a short-circuit AND (decisive=False) / OR (decisive=True) frame.

        Protocol: an SC frame is only processed when it is back on top of the
        stack, i.e. the operand it dispatched has finished and left exactly one
        value on ``context.result_stack``. The SC frame consumes that value by
        position, so unrelated RETURN frames (user-function arguments/results)
        can never be mistaken for operands.
        """
        frame_stack.pop()

        values = list(frame.arg_values)
        if len(values) < frame.operand_index:
            # The most recently dispatched operand has completed.
            if not context.result_stack:
                raise ExecutionError("No result for boolean operand")
            operand = context.result_stack.pop()
            if not isinstance(operand, bool):
                raise ExecutionError(
                    f"Boolean operation requires boolean arguments, got {type(operand).__name__}"
                )
            values.append(operand)
            if operand == decisive:
                # Short-circuit: remaining operands are neither evaluated nor charged.
                frame_stack.append(Frame(frame_type=FrameType.RETURN, result=decisive))
                return

        if frame.operand_index >= len(frame.remaining_args):
            # Every operand was evaluated without hitting the decisive value.
            frame_stack.append(Frame(frame_type=FrameType.RETURN, result=not decisive))
            return

        # Dispatch the next operand; this frame resumes when it completes.
        frame_stack.append(Frame(
            frame_type=frame.frame_type,
            func_name=frame.func_name,
            remaining_args=frame.remaining_args,
            operand_index=frame.operand_index + 1,
            arg_values=values,
            short_circuit=frame.short_circuit,
            sc_depth=frame.sc_depth,
        ))
        frame_stack.append(Frame(
            frame_type=FrameType.EXPR,
            expr=frame.remaining_args[frame.operand_index],
            ast_depth=frame.sc_depth + 1,
        ))

    def _handle_sc_and_frame(
        self,
        frame_stack: list[Frame],
        frame: Frame,
        context: EvalContext,
        language_spec: LanguageSpec,
    ) -> None:
        """Handle SC_AND frame: a false operand decides the result without evaluating the rest."""
        self._step_short_circuit(frame_stack, frame, context, decisive=False)

    def _handle_sc_or_frame(
        self,
        frame_stack: list[Frame],
        frame: Frame,
        context: EvalContext,
        language_spec: LanguageSpec,
    ) -> None:
        """Handle SC_OR frame: a true operand decides the result without evaluating the rest."""
        self._step_short_circuit(frame_stack, frame, context, decisive=True)

    def _handle_return_frame(
        self,
        frame_stack: list[Frame],
        frame: Frame,
        context: EvalContext,
        language_spec: LanguageSpec,
    ) -> None:
        """Handle RETURN frame.

        A value-carrying RETURN publishes its value on ``context.result_stack``;
        whichever frame is waiting for it (ARGUMENT, IF_CONDITION, SC_*) consumes
        it by position when it next reaches the top. A restore marker (pushed on
        user-function entry) instead puts call depth and bindings back to what the
        caller had.
        """
        frame_stack.pop()

        if frame.restore_depth:
            context.call_depth = frame.depth_to_restore
            if frame.old_bindings is not None:
                context.bindings = frame.old_bindings
        else:
            context.result_stack.append(frame.result)

    def _push_if_frame(
        self,
        frame_stack: list[Frame],
        frame: Frame,
        tree: Tree,
        context: EvalContext,
        language_spec: LanguageSpec,
    ) -> None:
        """Push frames to evaluate if expression with correct AST depth."""
        # Parse if expression
        condition = None
        then_branch = None
        else_branch = None
        
        for child in tree.children:
            if isinstance(child, Tree) and child.data == "expr":
                if condition is None:
                    condition = child
                elif then_branch is None:
                    then_branch = child
                else:
                    else_branch = child
        
        if condition is None or then_branch is None or else_branch is None:
            raise ExecutionError("if expression missing required branches")
        
        # Pop the IF frame and push condition evaluation with parent depth
        parent_depth = frame.ast_depth
        # If expression is a nested expression, so it increases depth
        new_depth = parent_depth + 1
        frame_stack.append(Frame(
            frame_type=FrameType.IF_CONDITION,
            condition=condition,
            then_branch=then_branch,
            else_branch=else_branch,
            if_depth=new_depth,  # Depth for if expression branches
        ))
        # Condition is at the new depth
        frame_stack.append(Frame(frame_type=FrameType.EXPR, expr=condition, ast_depth=new_depth))
    
    def _eval_literal(
        self,
        tree: Tree,
        context: EvalContext,
        language_spec: LanguageSpec,
    ) -> Any:
        """Evaluate a literal value."""
        if tree.children:
            child = tree.children[0]
            if isinstance(child, Token):
                return self._eval_token(child, context, language_spec)
        return None
    
    def _eval_token(
        self,
        token: Token | str,
        context: EvalContext,
        language_spec: LanguageSpec,
    ) -> Any:
        """Evaluate a token (identifier, number, boolean)."""
        if isinstance(token, Token):
            token = token.value
        
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
    
    def _eval_builtin(
        self,
        op_name: str,
        args: list,
        context: EvalContext,
        language_spec: LanguageSpec,
    ) -> Any:
        """Evaluate a built-in operation."""
        if op_name in {"add", "sub", "mul", "div", "mod"}:
            return self._eval_arithmetic(op_name, args, context)
        elif op_name in {"and", "or"}:
            return self._eval_boolean_op(op_name, args, context)
        elif op_name == "not":
            return self._eval_not(args, context)
        elif op_name == "eq":
            return self._eval_eq(args, context)
        elif op_name == "if":
            # Builtin if - args already evaluated
            if len(args) != 3:
                raise ExecutionError(f"if requires 3 arguments, got {len(args)}")
            cond, then_val, else_val = args
            if not isinstance(cond, bool):
                raise ExecutionError(f"if condition must be boolean, got {type(cond).__name__}")
            return then_val if cond else else_val
        else:
            raise ExecutionError(f"Unknown built-in operation: {op_name}")
    
    def _eval_arithmetic(self, op_name: str, args: list, context: EvalContext) -> int:
        """Evaluate arithmetic operation with overflow mode support."""
        if len(args) != 2:
            raise ExecutionError(f"Arithmetic operation '{op_name}' requires 2 arguments, got {len(args)}")
        
        a, b = args
        # bool is a subclass of int in Python, so isinstance(True, int) is True. The language's
        # int type is exactly int, so each operand's type is compared exactly.
        for operand in (a, b):
            if type(operand) is not int:
                raise ExecutionError(
                    f"Arithmetic operation '{op_name}' requires int arguments, got {type(operand).__name__}"
                )
        
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
        """Apply arithmetic operation with the given overflow mode."""
        result = operation(a, b)
        
        if mode == "wraparound":
            # Compute modulo 2^64, then convert to signed 64-bit
            unsigned_result = result & 0xFFFFFFFFFFFFFFFF
            if unsigned_result > 0x7FFFFFFFFFFFFFFF:
                return unsigned_result - 0x10000000000000000
            return unsigned_result
        elif mode == "saturating":
            # Clamp to 64-bit signed range
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
        
        # For error-on-overflow, check MIN_INT64 / -1
        if mode == "error-on-overflow":
            if a == MIN_INT64 and b == -1:
                raise OverflowError(f"Integer overflow: {a} / {b}")
        
        # For wraparound and saturating modes, wrap result if outside 64-bit range
        if mode == "wraparound":
            unsigned = result & 0xFFFFFFFFFFFFFFFF
            if unsigned > 0x7FFFFFFFFFFFFFFF:
                return unsigned - 0x10000000000000000
            return unsigned
        elif mode == "saturating":
            if result > MAX_INT64:
                return MAX_INT64
            elif result < MIN_INT64:
                return MIN_INT64
            return result
        
        return result
    
    def _apply_modulo(self, a: int, b: int, mode: str) -> int:
        """Apply modulo with sign following dividend.
        
        Uses: remainder = a - trunc(a / b) * b
        """
        if b == 0:
            raise ZeroDivisionError("Modulo by zero")
        
        if (a >= 0 and b >= 0) or (a <= 0 and b <= 0):
            trunc_result = abs(a) // abs(b)
        else:
            trunc_result = - (abs(a) // abs(b))
        
        remainder = a - trunc_result * b
        return remainder
    
    def _eval_boolean_op(self, op_name: str, args: list, context: EvalContext) -> bool:
        """Evaluate boolean operation with configurable short-circuit/eager mode.
        
        Args:
            args: For short-circuit mode, contains unevaluated Tree expressions.
                  For eager mode, contains already-evaluated values.
        """
        if len(args) != 2:
            raise ExecutionError(f"Boolean operation '{op_name}' requires 2 arguments, got {len(args)}")
        
        # Both operands should already be evaluated (from BUILTIN frame)
        left_value = args[0]
        right_value = args[1]
        
        if not isinstance(left_value, bool):
            raise ExecutionError(f"Boolean operation requires boolean arguments, got {type(left_value).__name__}")
        if not isinstance(right_value, bool):
            raise ExecutionError(f"Boolean operation requires boolean arguments, got {type(right_value).__name__}")
        
        if op_name == "and":
            return left_value and right_value
        else:  # or
            return left_value or right_value
    
    def _eval_not(self, args: list, context: EvalContext) -> bool:
        """Evaluate not operation."""
        if len(args) != 1:
            raise ExecutionError(f"not requires 1 argument, got {len(args)}")
        
        value = args[0]
        if not isinstance(value, bool):
            raise ExecutionError(f"not requires boolean argument, got {type(value).__name__}")
        
        return not value
    
    def _eval_eq(self, args: list, context: EvalContext) -> bool:
        """Evaluate equality comparison."""
        if len(args) != 2:
            raise ExecutionError(f"eq requires 2 arguments, got {len(args)}")
        
        # Strict typing: values of different types are never equal, so 1 is not equal to true.
        # Python would otherwise compare them by value (True == 1).
        return type(args[0]) is type(args[1]) and args[0] == args[1]


@dataclass
class EvalContext:
    """Execution context for evaluation."""
    max_steps: int = DEFAULT_MAX_STEPS
    max_ast_depth: int = DEFAULT_MAX_AST_DEPTH
    max_call_depth: int = DEFAULT_MAX_CALL_DEPTH
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES
    
    steps: int = 0
    ast_depth: int = 0
    call_depth: int = 0
    output_buffer: str = ""
    functions: dict[str, Any] = None
    bindings: dict[str, Any] = None
    result_stack: list[Any] = None
    # Semantic configuration (from LanguageSpec)
    arithmetic_mode: str = "wraparound"
    short_circuit_mode: bool = True

    def __post_init__(self) -> None:
        if self.functions is None:
            object.__setattr__(self, 'functions', {})
        if self.bindings is None:
            object.__setattr__(self, 'bindings', {})
        if self.result_stack is None:
            object.__setattr__(self, 'result_stack', [])
    
    def increment_steps(self, amount: int = 1) -> None:
        """Charge execution steps. Raises before charging if the budget would be exceeded.

        Exactly max_steps charges succeed; the next attempted charge raises
        StepLimitExceeded and is NOT added to ``steps``.
        """
        if self.steps + amount > self.max_steps:
            raise StepLimitExceeded(f"Step limit exceeded: {self.steps + amount} > {self.max_steps}")
        self.steps += amount

    def increment_ast_depth(self, amount: int = 1) -> None:
        """Increment AST depth counter, raising if limit exceeded."""
        self.ast_depth += amount
        if self.ast_depth > self.max_ast_depth:
            raise AstDepthExceeded(f"AST depth exceeded: {self.ast_depth} > {self.max_ast_depth}")
    
    def decrement_ast_depth(self, amount: int = 1) -> None:
        """Decrement AST depth counter."""
        self.ast_depth = max(0, self.ast_depth - amount)
    
    def add_output(self, text: str) -> None:
        """Add text to output buffer, raising if limit exceeded."""
        self.output_buffer += text
        if len(self.output_buffer) > self.max_output_bytes:
            raise OutputLimitExceeded(f"Output size exceeded: {len(self.output_buffer)} > {self.max_output_bytes}")
