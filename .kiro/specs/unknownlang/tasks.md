# Implementation Plan: UnknownLang

## Overview

This implementation plan covers Phase 1 MVP (48 hours) for the UnknownLang platform - an adaptive AI reasoning benchmark that evaluates AI models' ability to learn and reason within procedurally generated programming languages.

The tasks are organized in dependency waves for optimal parallel execution. Core functionality builds progressively from language generation through execution, challenge creation, model evaluation, and finally API/frontend integration.

## Tasks

- [ ] 1. Project Setup and Foundation
  - [ ] 1.1 Initialize Python project structure
    - Create directory structure: `src/`, `tests/`, `sandbox/`, `frontend/`
    - Create `pyproject.toml` with dependencies: fastapi, lark, hypothesis, pytest, uvicorn, httpx
    - Set up virtual environment and install dependencies
    - Initialize git repository
    - _Requirements: 19.1_

  - [ ] 1.2 Set up testing framework
    - Configure pytest with `conftest.py`
    - Set up Hypothesis for property-based testing
    - Create test fixtures for language generation
    - _Requirements: 16.1, 16.2_

- [ ] 2. Language Generator
  - [x] 2.1 Implement seed hashing and validation
    - Create `LanguageSeed` dataclass with name, syntax_style, features, difficulty
    - Implement deterministic seed hashing using hashlib
    - Add input validation for seed parameters
    - _Requirements: 5.1, 5.5_
    - _Property: 1, 7_

  - [ ] 2.2 Implement grammar builder
    - Create `GrammarBuilder` class to generate CFG from seed
    - Implement terminal definitions (NUMBER, STRING, IDENTIFIER)
    - Implement production rules based on syntax_style (lisp, c-like, etc.)
    - Add start symbol configuration
    - _Requirements: 5.2, 5.3_
    - _Property: 2_

  - [ ] 2.3 Implement Lark serializer
    - Create `LarkSerializer` to output Lark-compatible grammar
    - Add grammar validation using Lark's `lark.Grammar`
    - Implement conflict detection
    - _Requirements: 5.2, 7.1_

  - [ ] 2.4 Implement semantic mapping and interpreter operations
    - Create semantic operation registry (MVP: arithmetic, short_circuit ONLY)
    - Implement semantic validation: reject unsupported dimensions with ValidationError
    - Support ONLY: arithmetic (wraparound/saturating/error-on-overflow) and short_circuit (true/false)
    - Map built-in functions to interpreter operations via semantics config
    - Implement fixed interpreter that uses semantic mapping (NOT generated code)
    - Ensure deterministic execution through fixed evaluator
    - _Requirements: 5.4, 5.6, 5.7, 6.3, 7.2, 7.3, 7.4_
    - _Property: 3_

  - [ ] 2.5 Implement LanguageGenerator facade
    - Create `LanguageGenerator` class with `generate()` and `validate_grammar()` methods
    - Implement `detect_conflicts()` for syntactic uniqueness
    - Add language specification serialization
    - _Requirements: 5.4, 6.1_
    - _Property: 1, 2, 7_

  - [ ]* 2.6 Write property tests for Language Generator
    - **Property 1: Language Generation Determinism**
    - **Property 2: Grammar Validity**
    - **Property 7: Reproducibility via Seeds**
    - **Validates: Requirements 5.5, 5.2, 4.3, 20.2, 20.3**

- [x] 3. Execution Engine
  - [x] 3.1 Implement Lark parser integration
    - Create `ExecutionEngine` class
    - Integrate Lark parser with generated grammars
    - Handle parse errors gracefully
    - _Requirements: 7.1_

  - [x] 3.2 Implement interpreter with AST evaluation
    - Implement tree-walking interpreter for AST
    - Support integer arithmetic, boolean logic, function calls
    - Add scope management for variables
    - _Requirements: 7.3_

  - [x] 3.3 Implement deterministic resource limits
    - Implement interpreter-level limits: max_steps, max_ast_depth, max_call_depth, max_collection_size, max_string_size, max_output_size
    - Add step counter that increments per AST node evaluation
    - Add depth tracking for AST traversal and function calls
    - Add output size tracking for accumulated results
    - Return typed status: step_limit_exceeded, recursion_limit_exceeded, output_limit_exceeded, ast_depth_exceeded
    - DO NOT use signal.alarm as primary mechanism
    - _Requirements: 7.5, 7.6, 20.8_
    - _Property: 8_

  - [x] 3.4 Implement ExecutionResult with status
    - Create result types: success, error, step_limit_exceeded, recursion_limit_exceeded, output_limit_exceeded, ast_depth_exceeded, invalid_program
    - Include output, error_message, execution_time_ms
    - Add deterministic output verification
    - Document that interpreter is NOT fully sandboxed
    - _Requirements: 7.4, 7.6, 20.8_

  - [ ]* 3.5 Write property tests for Execution Engine
    - **Property 3: Interpreter Execution Determinism**
    - **Property 8: Timeout Handling**
    - **Validates: Requirements 3.4, 7.4, 20.1, 20.8**

- [ ] 4. Challenge Generator
  - [ ] 4.1 Implement problem templates
    - Create templates for: array operations, string manipulation, recursion, sorting, search
    - Define function signatures for each problem type
    - Add difficulty-specific variations
    - _Requirements: 9.1_

  - [ ] 4.2 Implement difficulty scaling
    - Scale complexity from level 1-5
    - Adjust data size, operation complexity, edge cases
    - Map difficulty to language difficulty
    - _Requirements: 9.2_

  - [ ] 4.3 Implement example and test case generation
    - Generate 3-5 public example programs
    - Generate 10-20 total test cases
    - Ensure hidden tests differ from examples
    - _Requirements: 9.3, 9.4, 20.4_
    - _Property: 5_

  - [ ] 4.4 Implement reference implementation generator
    - Create reference solutions in generated language using SEPARATE templates (not production challenge templates)
    - Reference solutions must be mathematically derivable from formal semantics
    - DO NOT verify outputs using ExecutionEngine - use Independent Reference Evaluator
    - _Requirements: 8.1, 8.2, 9.5_
    - _Property: 4_

  - [ ] 4.5 Implement ChallengeGenerator facade
    - Create `ChallengeGenerator` class with generate() method
    - Integrate with Language Generator
    - Store challenge with all components (requires verified oracle outputs from 5.2)
    - _Requirements: 9.1, 9.2, 9.3_
    - _Prerequisites: Task 5.2 (oracle cross-validation) must complete before challenge verification_

  - [ ]* 4.6 Write property tests for Challenge Generator
    - **Property 5: Challenge Uniqueness**
    - **Validates: Requirements 9.4, 9.5, 20.4_

- [ ] 5. Test Oracle
  - [ ] 5.1 Implement independent reference evaluator
    - **CRITICAL**: This evaluator MUST be a completely separate codebase that does NOT import ExecutionEngine
    - Implement formal arithmetic semantics independently:
      - wraparound: r = ((a op b) mod 2^64), convert to signed
      - saturating: clamp result to INT64 range
      - error-on-overflow: raise OverflowError on overflow
    - Implement formal short-circuit semantics independently (NOT using Python's and/or)
    - Implement formal boolean logic: true, false, and, or, not
    - Validate against hand-verified baseline cases (see design.md for exact values)
    - Include cross-validation that detects disagreements with production
    - When evaluators disagree, mark test case as INVALID/INCONCLUSIVE - never contribute to scores
    - Document for each operation: formal semantics, reference algorithm, invariants
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_
    - _Property: 4_

  - [ ] 5.2 Implement cross-validation and invariant checking
    - Run both production and reference evaluators on baseline cases
    - Verify mathematical invariants hold (e.g., and(x, false) = false)
    - When disagreement detected, invalidate affected test cases/challenges
    - Never silently select one evaluator's result over the other's
    - _Requirements: 8.5, 8.6_
    - _Property: 4_

  - [ ]* 5.3 Write unit tests for Test Oracle
    - Test output comparison logic
    - Test mismatch reporting
    - _Requirements: 8.4_

- [ ] 6. Model Provider - Ollama Integration
  - [ ] 6.1 Implement ModelAdapter abstract interface
    - Define abstract methods: list_models(), generate(), estimate_tokens()
    - Create base class with common functionality
    - _Requirements: 11.1_

  - [ ] 6.2 Implement OllamaAdapter
    - Implement Ollama local inference integration
    - Support llama2, codellama and other available models
    - Handle connection errors gracefully
    - _Requirements: 11.2, 3.5_

  - [ ] 6.3 Implement MockAdapter for testing
    - Implement mock responses for development without Ollama
    - Support predefined test cases
    - Enable full benchmark flow testing offline
    - _Requirements: 3.5_

  - [ ] 6.4 Implement Prompt Builder
    - Build prompts with language specification
    - Include syntax rules and examples
    - Exclude hidden test cases from prompts
    - _Requirements: 11.4_

  - [ ] 6.5 Implement Response Parser
    - Extract code from markdown code blocks
    - Fall back to entire response if no code block
    - Handle malformed responses gracefully
    - _Requirements: 11.5_

  - [ ]* 6.6 Write unit tests for Model Adapters
    - Test prompt building
    - Test response parsing
    - Test Ollama and Mock adapter interfaces
    - _Requirements: 11.4, 11.5_

- [ ] 7. Benchmark Evaluator
  - [ ] 7.1 Implement evaluation workflow orchestration
    - Coordinate: challenge selection, language generation, example creation
    - Coordinate: test case generation, model invocation, execution, scoring
    - _Requirements: 10.1_

  - [ ] 7.2 Implement scoring functions
    - Compute pass rate: passed / total
    - Compute generalization gap: public_score - hidden_score
    - Compute weighted correctness score with difficulty weights
    - _Requirements: 10.2, 10.3, 10.4_
    - _Property: 6_

  - [ ] 7.3 Implement result aggregation
    - Aggregate results across challenges
    - Compute overall metrics
    - Generate result summaries
    - _Requirements: 10.1_

  - [ ]* 7.4 Write property tests for Scoring
    - **Property 6: Scoring Correctness**
    - **Validates: Requirements 10.2, 10.3, 10.4**

---

## Post-MVP Phases (NOT PART OF WAVE 1)

The following phases are deferred to after the core language engine is complete and verified.

### Phase 2: Backend API (Post-MVP)
- API endpoints for language generation, challenge creation, benchmark running
- Async job handling
- OpenAPI documentation
- _Requirements: 13.1-13.5_

### Phase 3: Frontend (Post-MVP)
- React + TypeScript frontend with Vite
- Dashboard, Language Explorer, Benchmark Runner, Results Viewer
- _Requirements: 14.1-14.5_

### Phase 4: Model Integration (Post-MVP)
- Ollama adapter
- MockAdapter for testing
- Prompt builder and response parser
- _Requirements: 11.1-11.5_

### Phase 5: Database Integration (Post-MVP)
- SQLite persistence
- CRUD operations for languages, challenges, benchmarks, results
- _Requirements: 12.1-12.5_

### Phase 6: Demo and Deployment (Post-MVP)
- End-to-end demo flow
- Docker deployment
- Free-tier cloud deployment configuration
- _Requirements: 17.1-17.5, 18.1-18.5_
    - Show recent benchmarks
    - Display quick actions (New Language, New Challenge, Run Benchmark)
    - _Requirements: 14.1, 14.4_

  - [ ] 9.3 Implement Language Explorer page
    - List generated languages
    - View language specification details
    - Display grammar and examples
    - _Requirements: 14.1, 14.3_

  - [ ] 9.4 Implement Benchmark Runner page
    - Configure benchmark: select language, select models
    - Start benchmark execution
    - Show real-time progress
    - _Requirements: 14.1, 14.2_

  - [ ] 9.5 Implement Results Viewer page
    - Display pass rates per model
    - Show generalization gap metrics
    - Add comparison charts
    - _Requirements: 14.1, 14.5_

  - [ ]* 9.6 Write frontend unit tests
    - Test component rendering
    - Test user flows
    - _Requirements: 16.3_

- [ ] 10. Demo Flow Integration
  - [ ] 10.1 Implement end-to-end demo flow
    - Connect: language generation → challenge creation → model evaluation → results
    - Ensure all components work together
    - _Requirements: 18.1, 18.2, 18.3, 18.4_

  - [ ] 10.2 Add demo script
    - Create demo CLI command
    - Support pre-generated languages for backup
    - Include cached results for fallback
    - _Requirements: 18.5_

  - [ ] 10.3 Checkpoint - Ensure all tests pass
    - Run full test suite
    - Verify all acceptance criteria
    - Ask user if questions arise

- [ ] 11. Database Integration (Optional for MVP)
  - [ ] 11.1 Implement SQLite database
    - Create database schema from design
    - Add CRUD operations for languages, challenges, benchmarks, results
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

  - [ ] 11.2 Integrate database with API
    - Connect API endpoints to database
    - Add persistence for benchmark runs
    - _Requirements: 13.1_

## Notes

### Wave 1 Scope (Core Language Engine Only)
- **THIS IS WAVE 1**: Language generation, fixed interpreter, independent oracle, challenge generation
- **NOT IN WAVE 1**: API, frontend, AI model integration, database, deployment

### Implementation Rules
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties defined in the design
- Unit tests validate specific examples and edge cases
- Checkpoints ensure incremental validation

### Critical Implementation Constraints
- **NO ExecutionEngine imports in reference evaluator** - The independent evaluator must be a separate codebase
- **Semantic validation required** - Reject unsupported semantic configurations
- **Iterative AST traversal** - Avoid Python recursion for AST walking
- **All four resource limits must have boundary tests**

### Phase Reference
- **Wave 1** (THIS PHASE): Core Language Engine - DONE WHEN all tasks in 1A-1E complete
- **Phase 2**: Backend API - After Wave 1 verification
- **Phase 3**: Frontend - After Wave 1 verification
- **Phase 4**: Model Integration - After Wave 1 verification
- **Phase 5**: Database - After Wave 1 verification
- **Phase 6**: Demo/Deployment - After all phases complete

## Task Dependency Graph

### Wave 1: Core Language Engine Only (DO NOT INCLUDE API, FRONTEND, DATABASE)

**Note**: Wave 1 is the core language engine only. The following are explicitly NOT in Wave 1:
- ❌ Backend API (tasks 8.x)
- ❌ Frontend (tasks 9.x)
- ❌ Model Integration (tasks 6.x)
- ❌ Database (tasks 11.x)
- ❌ Demo/Deployment (tasks 10.x)

```json
{
  "waves": [
    { "id": "1A", "tasks": ["1.1", "1.2"], "description": "Project setup" },
    { "id": "1B", "tasks": ["2.1", "2.2", "2.3", "2.4", "2.5"], "description": "Language generation" },
    { "id": "1C", "tasks": ["3.1", "3.2", "3.3", "3.4"], "description": "Fixed interpreter" },
    { "id": "1D", "tasks": ["5.1", "5.2"], "description": "Independent oracle" },
    { "id": "1E", "tasks": ["4.1", "4.2", "4.3", "4.4", "4.5"], "description": "Challenge generation" }
  ]
}
```

### Explicit Directed Acyclic Graph (DAG)

```
                           BRANCH A: Production Interpreter
                          ┌──────────────────────────────────┐
1.1 ──► 2.1 ──► 2.2 ──► 2.3 ──► 2.4 ──► 2.5 ──► 3.1 ──► 3.2 ──► 3.3 ──► 3.4
                          └──────────────────────────────────┘
                                        │
                                        │ (both depend on 2.4 semantics)
                                        ▼
                          ┌──────────────────────────────────┐
                      5.1 (Independent Evaluator) ◄── 2.4  │
                     (MUST NOT import ExecutionEngine)     │
                          └──────────────────────────────────┘
                                        │
                                        ▼
                                    5.2 (cross-validation)
                                        │
                                        ▼
                          ┌──────────────────────────────────┐
1.2 ──────────────────────► 4.1 ──► 4.2 ──► 4.3 ──► 4.4 ──► 4.5
                          └──────────────────────────────────┘
                                       BRANCH C: Challenge Generation
```

### Wave Structure

| Wave | Tasks | Description | Blocking Dependencies |
|------|-------|-------------|----------------------|
| 1A | 1.1, 1.2 | Project setup | None |
| 1B | 2.1, 2.2, 2.3, 2.4, 2.5 | Language generation | 1A |
| 1C | 3.1, 3.2, 3.3, 3.4 | Fixed interpreter | 1B (2.5) |
| 1D | 5.1, 5.2 | Independent oracle | 1B (2.4), 1C (3.4) |
| 1E | 4.1, 4.2, 4.3, 4.4, 4.5 | Challenge generation | 1B (2.5), 1D (5.1, 5.2) |

### Task Prerequisites (Explicit)

**INDEPENDENT BRANCHES**: The production interpreter and independent evaluator are SEPARATE branches.

| Task ID | Prerequisites | What This Task Enables |
|---------|--------------|------------------------|
| 1.1 | - | Language generation |
| 1.2 | - | Testing framework |
| 2.1 | 1.1 | Seed model |
| 2.2 | 2.1 | Grammar builder |
| 2.3 | 2.2 | Lark grammar |
| 2.4 | 2.3 | Semantic mapping, formal definitions |
| 2.5 | 2.2, 2.3, 2.4 | Complete LanguageGenerator |
| **Branch A: Production Interpreter** |||
| 3.1 | 2.3 | Parser integration |
| 3.2 | 2.4, 3.1 | Interpreter core |
| 3.3 | 3.2 | Resource limits |
| 3.4 | 3.3 | ExecutionResult types |
| **Branch B: Independent Reference Evaluator** |||
| **5.1** | **2.4 (semantics ONLY)** | **Independent reference evaluator** |
| 5.2 | 5.1 | Cross-validation |
| **Branch C: Challenge Generation** |||
| 4.1 | 2.5 | Problem templates |
| 4.2 | 4.1 | Difficulty metrics |
| 4.3 | 4.2 | Test case generation |
| 4.4 | 4.3, 5.1 | Reference implementation |
| 4.5 | 4.4, 4.2 | ChallengeGenerator facade |

### Critical Independence Constraints

1. **Task 5.1 does NOT depend on tasks 3.x** - The reference evaluator is completely independent
2. **Task 5.1 ONLY depends on task 2.4** - For formal semantic definitions
3. **Task 5.1 MUST NOT import ExecutionEngine** - Architecturally enforced
4. **Task 5.2 (cross-validation) runs after both branches complete** - Depends on 3.4 and 5.1
5. **No dependency from Branch B to Branch A** - True independence