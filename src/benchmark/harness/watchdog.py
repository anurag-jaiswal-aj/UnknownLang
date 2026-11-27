"""Trusted-local subprocess watchdog for M2.6.

Provides a wall-clock timeout mechanism for program execution via subprocess.
This is a BACKSTOP mechanism only - not a security sandbox.

M2.6 supports only EVAL, SYN, INF, CTRL (value-answer tasks).
The watchdog wraps the production runtime through ExecutionEngine.execute().

Architecture:
- Parent process creates worker subprocess
- Parent sets wall-clock timeout using subprocess.run(timeout=...)
- Worker reconstructs LanguageSpec and executes ExecutionEngine.execute()
- Parent receives structured result from worker
- On timeout, parent terminates worker

Warning: This is NOT a security sandbox. It provides:
- Wall-clock timeout enforcement via subprocess
- Subprocess cleanup on timeout/finish
- Process termination on timeout

It does NOT provide:
- Network isolation
- Memory quotas
- CPU quotas
- Filesystem isolation
- Security isolation

Official/untrusted execution remains blocked pending Docker/WASM isolation.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.execution.types import ExecutionResult


# Default timeout in seconds for subprocess execution
_DEFAULT_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class WatchdogResult:
    """Result from watchdog-protected execution.
    
    status: "success", "timeout", "terminated", or "error"
    execution_result: ExecutionResult from successful execution (if any)
    error_message: Human-readable error description (if any)
    elapsed_seconds: Wall-clock time elapsed
    """
    status: str
    execution_result: ExecutionResult | None
    error_message: str | None
    elapsed_seconds: float


def _create_worker_script() -> Path:
    """Create a temporary Python script for the worker process.
    
    Returns the path to the worker script that will be executed in a subprocess.
    """
    worker_code = '''
import sys
import os
import json

# Get the working directory from environment
work_dir = os.environ.get("WORK_DIR")
if work_dir:
    sys.path.insert(0, work_dir)

# Read the input from stdin
input_data = json.load(sys.stdin)

from src.benchmark.environments import pinned_seed, semantic_projection
from src.language.generator import LanguageGenerator, LanguageSpec
from src.execution.engine import ExecutionEngine

# Reconstruct environment context from serializable inputs
arithmetic = input_data["arithmetic"]
short_circuit = input_data["short_circuit"]
surface_profile = input_data["surface_profile"]

# Reconstruct LanguageSpec using the same approach as env.py
seed = pinned_seed(arithmetic, short_circuit)
spec = LanguageGenerator().generate(
    seed,
    spec_version="1.0.0",
    algorithm_version="1.0.0",
)

# Execute through production engine
engine = ExecutionEngine(
    max_steps=input_data["max_steps"],
    max_ast_depth=input_data["max_ast_depth"],
    max_call_depth=input_data["max_call_depth"],
)

result = engine.execute(
    input_data["canonical_text"],
    spec,
    surface_profile=surface_profile,
)

# Output result as JSON
output = {
    "status": result.status,
    "value": result.value,
    "error_kind": result.error_kind,
    "error_message": result.error_message,
    "error_detail": result.error_detail,
}
json.dump(output, sys.stdout)
'''
    
    # Create temporary file with unique name
    fd, path = tempfile.mkstemp(prefix='m26_worker_', suffix='.py')
    try:
        os.write(fd, worker_code.encode('utf-8'))
    finally:
        os.close(fd)
    
    return Path(path)


def _execute_with_subprocess_timeout(
    canonical_text: str,
    spec: LanguageSpec,
    surface_profile: dict[str, Any],
    max_steps: int | None,
    max_ast_depth: int | None,
    max_call_depth: int | None,
    timeout_seconds: float,
) -> WatchdogResult:
    """Execute function in subprocess with wall-clock timeout detection.
    
    Creates a separate worker process and uses subprocess.run with timeout
    to enforce the wall-clock limit. This provides true subprocess isolation.
    
    Args:
        canonical_text: Canonical syntax program text
        spec: LanguageSpec for the environment
        surface_profile: Surface profile for translation
        max_steps: Maximum execution steps
        max_ast_depth: Maximum AST depth
        max_call_depth: Maximum call depth
        timeout_seconds: Wall-clock timeout in seconds
        
    Returns:
        WatchdogResult with execution status and timing
    """
    start_time = time.monotonic()
    worker_script = None
    
    try:
        # Create worker script
        worker_script = _create_worker_script()
        
        # Extract serializable environment context from spec
        # The spec contains seed.arithmetic and seed.short_circuit
        # We also need surface_profile
        arithmetic = spec.semantics.arithmetic_mode
        short_circuit = spec.semantics.short_circuit_mode
        
        input_data = {
            "canonical_text": canonical_text,
            "arithmetic": arithmetic,
            "short_circuit": short_circuit,
            "surface_profile": surface_profile,
            "max_steps": max_steps,
            "max_ast_depth": max_ast_depth,
            "max_call_depth": max_call_depth,
        }
        
        # Get working directory
        work_dir = os.getcwd()
        
        # Launch subprocess with timeout
        process = subprocess.run(
            [sys.executable, str(worker_script)],
            input=json.dumps(input_data),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env={**os.environ, "WORK_DIR": work_dir},
        )
        
        elapsed = time.monotonic() - start_time
        
        if process.returncode != 0:
            return WatchdogResult(
                status="error",
                execution_result=None,
                error_message=f"Worker process exited with code {process.returncode}: {process.stderr}",
                elapsed_seconds=elapsed,
            )
        
        # Parse JSON output from worker
        try:
            output = json.loads(process.stdout)
            result = ExecutionResult(
                status=output["status"],
                value=output["value"],
                error_kind=output.get("error_kind"),
                error_message=output.get("error_message"),
                error_detail=output.get("error_detail"),
            )
            return WatchdogResult(
                status="success",
                execution_result=result,
                error_message=None,
                elapsed_seconds=elapsed,
            )
        except (json.JSONDecodeError, KeyError) as e:
            return WatchdogResult(
                status="error",
                execution_result=None,
                error_message=f"Failed to parse worker result: {e}. stdout: {process.stdout}. stderr: {process.stderr}",
                elapsed_seconds=elapsed,
            )
            
    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - start_time
        return WatchdogResult(
            status="timeout",
            execution_result=None,
            error_message=f"Wall-clock timeout exceeded ({timeout_seconds}s)",
            elapsed_seconds=elapsed,
        )
    
    except Exception as e:
        elapsed = time.monotonic() - start_time if 'start_time' in locals() else 0.0
        return WatchdogResult(
            status="error",
            execution_result=None,
            error_message=f"Subprocess execution error: {e}",
            elapsed_seconds=elapsed,
        )
    
    finally:
        # Cleanup worker script
        if worker_script is not None and worker_script.exists():
            try:
                worker_script.unlink()
            except:
                pass


def execute_with_watchdog(
    canonical_text: str,
    spec: LanguageSpec,
    surface_profile: dict[str, Any],
    max_steps: int | None,
    max_ast_depth: int | None,
    max_call_depth: int | None,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
) -> WatchdogResult:
    """Execute program with watchdog timeout protection via subprocess.
    
    Creates a separate worker process using subprocess.run with timeout.
    This provides true subprocess isolation for trusted-local execution.
    
    Args:
        canonical_text: Canonical syntax program text
        spec: LanguageSpec for the environment
        surface_profile: Surface profile for translation
        max_steps: Maximum execution steps (from task evaluation.limits)
        max_ast_depth: Maximum AST depth (from task evaluation.limits)
        max_call_depth: Maximum call depth (from task evaluation.limits)
        timeout_seconds: Wall-clock timeout in seconds
        
    Returns:
        WatchdogResult with execution status and timing
    """
    return _execute_with_subprocess_timeout(
        canonical_text=canonical_text,
        spec=spec,
        surface_profile=surface_profile,
        max_steps=max_steps,
        max_ast_depth=max_ast_depth,
        max_call_depth=max_call_depth,
        timeout_seconds=timeout_seconds,
    )


def classify_watchdog_result(result: WatchdogResult) -> tuple[str, str | None]:
    """Classify watchdog result into harness failure category.
    
    Returns:
        Tuple of (failure_category, detail)
    """
    if result.status == "success":
        return "ok", None
    
    if result.status == "timeout":
        return "resource_limit", "wall_clock"
    
    if result.status == "terminated":
        return "resource_limit", "process_terminated"
    
    if result.status == "error":
        return "harness_fault", result.error_message or "unknown_error"
    
    return "harness_fault", f"unrecognized_status: {result.status}"
