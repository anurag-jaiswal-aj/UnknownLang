"""Public/private projection for task data."""

from __future__ import annotations

from typing import Any

from .types import Protocol, TaskRecord, PublicTask, Visibility


def _filter_hidden_definitions(source: str, visibility: Visibility) -> str:
    """
    Filter hidden definitions from source code.
    
    Args:
        source: Source code containing definitions
        visibility: "public" or "hidden"
        
    Returns:
        Source code with hidden definitions filtered (empty if all hidden)
    """
    if visibility == "hidden":
        return ""
    return source


def _project_input_public(input_defs: Any) -> Any:
    """
    Project input definitions to public view.
    
    Filters definitions by visibility, keeping only public ones.
    Handles nested structures recursively.
    """
    if isinstance(input_defs, dict):
        # Filter definitions based on visibility
        visibility = input_defs.get("visibility", "public")
        source = input_defs.get("source", "")
        
        # Filter source based on visibility
        filtered_source = "" if visibility == "hidden" else source
        
        # Handle must_define - remove entries if all definitions are hidden
        must_define = input_defs.get("must_define")
        if must_define and visibility == "hidden":
            must_define = None
            
        return {
            "source": filtered_source,
            "visibility": visibility,
            "must_define": must_define,
        }
    elif isinstance(input_defs, (list, tuple)):
        return [_project_input_public(item) for item in input_defs]
    elif hasattr(input_defs, "__dict__"):
        # Handle dataclass - preserve InputDefinitions type
        from .types import InputDefinitions, Visibility
        
        visibility = getattr(input_defs, "visibility", "public")
        source = getattr(input_defs, "source", "")
        
        # Filter source based on visibility
        filtered_source = "" if visibility == "hidden" else source
        
        # Handle must_define - remove entries if all definitions are hidden
        must_define = getattr(input_defs, "must_define", None)
        if must_define and visibility == "hidden":
            must_define = None
        
        return InputDefinitions(
            source=filtered_source,
            visibility=visibility,
            must_define=tuple(must_define) if must_define else None,
        )
    else:
        return input_defs


def project_public(task: TaskRecord | dict[str, Any]) -> PublicTask:
    """
    Project a task to its public view.
    
    The public view contains only information that may be visible to a model.
    Private data is omitted (not present in PublicTask):
    - expected (answer values)
    - hidden tests (tests with visibility="hidden")
    - hidden definitions (input.definitions with visibility="hidden")
    - verification (evidence for expected)
    - provenance (generator info)
    - notes (free text)
    - protocol.role (for paired tasks)
    - difficulty (level and dimensions)
    
    Args:
        task: TaskRecord or dict with all required fields
        
    Returns:
        PublicTask with only public fields
        
    Raises:
        ValueError: If task structure is invalid
    """
    if isinstance(task, TaskRecord):
        # Extract from TaskRecord
        # Remove difficulty from PublicTask per spec section 5.2
        # Remove protocol.role for paired tasks per spec section 5.2
        public_input = None
        if task.input is not None:
            public_input = _project_input_public(task.input)
        
        # Create new Protocol without role for paired tasks
        protocol = task.protocol
        if protocol.kind == "paired":
            protocol = Protocol(
                kind=protocol.kind,
                pair_group_id=protocol.pair_group_id,
                role=None,
                varies=protocol.varies,
            )
        
        return PublicTask(
            schema_version=task.schema_version,
            task_id=task.task_id,
            template=task.template,
            category=task.category,
            protocol=protocol,
            environment_id=task.environment_id,
            information_condition=task.information_condition,
            input=public_input,
            prompt=task.prompt,
            answer_spec=task.answer_spec,
            evaluation=_project_evaluation_public(task.evaluation),
        )
    else:
        # Extract from dict
        data = task.copy()
        
        # Extract only public fields (exclude expected, difficulty, protocol.role)
        public_input = None
        if data.get("input"):
            public_input = _project_input_public(data["input"])
        
        return PublicTask(
            schema_version=data["schema_version"],
            task_id=data["task_id"],
            template=tuple(data["template"]),
            category=data["category"],
            protocol=_protocol_from_dict(data["protocol"]),
            environment_id=data["environment_id"],
            information_condition=data["information_condition"],
            input=public_input,
            prompt=_prompt_from_dict(data["prompt"]),
            answer_spec=_answer_spec_from_dict(data["answer_spec"]),
            evaluation=_project_evaluation_public(data["evaluation"]),
        )


def _protocol_from_dict(data: dict[str, Any]) -> Any:
    """Create Protocol from dict."""
    from .types import Protocol, Variation
    
    kind = data["kind"]
    varies = tuple(data.get("varies", []))
    
    if kind == "standalone":
        return Protocol(kind=kind, varies=varies)
    else:  # paired
        # protocol.role is excluded from public view for paired tasks
        return Protocol(
            kind=kind,
            pair_group_id=data.get("pair_group_id"),
            role=None,
            varies=varies,
        )


def _difficulty_from_dict(data: dict[str, Any]) -> Any:
    """Create Difficulty from dict."""
    from .types import Difficulty
    
    return Difficulty(
        level=data["level"],
        reasoning_steps=data["reasoning_steps"],
        nesting_depth=data["nesting_depth"],
        control_flow=data["control_flow"],
        state=data["state"],
    )


def _input_from_dict(data: dict[str, Any]) -> Any:
    """Create InputDefinitions from dict."""
    from .types import InputDefinitions, Visibility
    
    return InputDefinitions(
        source=data["source"],
        visibility=data["visibility"],
        must_define=tuple(data.get("must_define", [])) if data.get("must_define") else None,
    )


def _prompt_from_dict(data: dict[str, Any]) -> Any:
    """Create Prompt from dict."""
    from .types import Prompt
    
    return Prompt(
        template=tuple(data["template"]),
        example_policy=data["example_policy"],
        public_examples=tuple(data["public_examples"]),
        query=data.get("query"),
        spec=data.get("spec"),
    )


def _answer_spec_from_dict(data: dict[str, Any]) -> Any:
    """Create AnswerSpec from dict."""
    from .types import AnswerSpec
    
    return AnswerSpec(
        type=data["type"],
        kind=data.get("kind"),
        form=data.get("form"),
        chance_floor_ppm=data.get("chance_floor_ppm"),
    )


def _project_evaluation_public(evaluation: Any) -> Any:
    """
    Project evaluation to public view.
    
    Excludes hidden tests.
    """
    from .types import Evaluation
    
    if isinstance(evaluation, Evaluation):
        # Extract only public tests
        public_tests = tuple(t for t in evaluation.tests if t.visibility == "public")
        
        return Evaluation(
            method=evaluation.method,
            limits=dict(evaluation.limits),
            tests=public_tests,
        )
    else:
        # Extract from dict
        tests = evaluation.get("tests", [])
        public_tests = tuple(t for t in tests if t.get("visibility") == "public")
        
        return Evaluation(
            method=evaluation["method"],
            limits=dict(evaluation.get("limits", {})),
            tests=public_tests,
        )


def leak_test(task: TaskRecord, sentinel: str = "PRIVATE_SENTINEL") -> bool:
    """
    Test that private data does not leak into public projection.
    
    This is a test helper for T12 leakage lint.
    
    Args:
        task: TaskRecord to test
        sentinel: Unique string to search for in public view
        
    Returns:
        True if no sentinel found in public projection
    """
    public = project_public(task)
    public_dict = public.__dict__
    
    # Search recursively for sentinel in public view
    def search(obj: Any, path: str = "") -> bool:
        """Recursively search for sentinel in object."""
        if isinstance(obj, str):
            return sentinel not in obj
        elif isinstance(obj, dict):
            return all(search(v, f"{path}.{k}") for k, v in obj.items())
        elif isinstance(obj, (list, tuple)):
            return all(search(v, f"{path}[]") for v in obj)
        elif hasattr(obj, "__dict__"):
            return all(search(v, f"{path}.{k}") for k, v in obj.__dict__.items())
        return True
    
    return search(public_dict)
