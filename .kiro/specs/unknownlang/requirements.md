# Requirements Document

## Introduction

UnknownLang is an adaptive AI reasoning benchmark platform that evaluates whether AI models can learn and reason within previously unseen, procedurally generated programming languages. The platform generates controlled programming-language environments, provides specifications to AI models, evaluates their generated programs using independent deterministic interpreters, and measures their ability to generalise beyond provided examples.

## Glossary

- **Challenge**: A programming task consisting of a language specification, problem description, and test cases
- **Deterministic Interpreter**: An independent execution engine that produces consistent results for the same program and input
- **Example Program**: A program provided to the AI model demonstrating language constructs
- **Hidden Test Case**: A test case used for evaluation but not shown to the AI model
- **Language Seed**: A unique identifier ensuring reproducible language generation
- **Model Provider**: External service that hosts AI models (OpenAI, Anthropic, Ollama, etc.)
- **Public Test Case**: A test case shown to the AI model as part of the challenge specification
- **Reference Implementation**: A canonical solution used to generate expected outputs
- **Test Oracle**: Independent system that verifies program correctness against expected outputs
- **Versioned Language Definition**: A language specification with version control for reproducibility

## Requirements

### Requirement 1: Product Requirements and User Personas

**User Story:** As a Product Manager, I want to define the target users and their needs, so that the platform is designed with the right features.

#### Acceptance Criteria

1. THE Platform SHALL define at least 4 distinct user personas covering AI researchers, model developers, academic evaluators, and hackathon participants, where "distinct" means each persona has a unique combination of role, goal, and expertise level.
2. THE User Personas SHALL include at least 2 goals, 1 pain point, and 1 specific need for each user type.
3. THE System SHALL produce a ranked feature list with 3 priority levels based on persona needs and hackathon timeline constraints.
4. WHERE budget is zero, THE System SHALL prefer free and open-source technologies, but MAY allow non-free technology only with documented approval.
5. IF the user is a hackathon participant, THE Platform SHALL provide a quick-start path with at least 2 demo capabilities completing within 15 minutes.

### Requirement 2: Research Findings and Competitor Analysis

**User Story:** As an AI Researcher, I want to understand the existing landscape, so that UnknownLang fills a genuine gap.

#### Acceptance Criteria

1. THE System SHALL document existing benchmarks with at minimum: name, language coverage (list of languages evaluated), and evaluation approach (methodology used to assess AI performance) for HumanEval, MBPP, APPS, CodeXGLUE, EsoLang-Bench (arXiv:2603.09678, March 2026), and DSL-Bench (arXiv:2611.05168, November 2026).
2. THE Analysis SHALL document that EsoLang-Bench (arXiv:2603.09678) evaluates LLMs on 5 esoteric programming languages (Brainfuck, Befunge-98, Whitespace, Unlambda, Shakespeare) and that DSL-Bench (arXiv:2611.05168) evaluates LLMs on 18 domain-specific languages from academic papers.
3. THE Analysis SHALL identify what differentiates UnknownLang from EsoLang-Bench (uses pre-existing esolangs vs procedurally generated languages) and DSL-Bench (uses existing DSLs vs novel generated languages).
4. THE Analysis SHALL include technology assessment for Racket, ANTLR, Lark, Trealla, and WASM covering: generation capability (Y/N), sandboxing capability (Y/N), and suitability rating (HIGH/MEDIUM/LOW) for language generation and sandboxing.

### Requirement 3: Research Hypothesis and Measurable Objectives

**User Story:** As a Researcher, I want clear hypotheses and objectives, so that benchmark results have scientific meaning.

#### Acceptance Criteria

1. WHEN a benchmark execution is configured, THE Primary Hypothesis SHALL specify that AI models achieving a score above the 50th percentile on UnknownLang tasks demonstrate superior generalization, as measured by performance on held-out language variants compared to models below the 50th percentile.
2. WHEN a benchmark execution is configured, THE Secondary Hypothesis SHALL specify that language complexity, measured by grammar rule count and token diversity index, positively correlates with AI model performance degradation, as measured by task accuracy.
3. THE Platform SHALL support generation of at least 100 unique language variants per difficulty level during a single benchmark execution.
4. THE Test Oracle SHALL produce 100% deterministic results and SHALL include a correctness verification mechanism that validates output accuracy against known expected results for a baseline set of language variants.
5. THE Platform SHALL integrate with at least 1 model provider (Ollama for free local inference) and SHALL provide a mock adapter for testing without external APIs.

### Requirement 4: Differentiation Strategy

**User Story:** As a Product Manager, I want clear differentiation, so that UnknownLang has a unique market position.

#### Acceptance Criteria

1. WHEN generating a new language, THE Platform SHALL verify that no version of the language exists in public repositories or training datasets, AND THE Platform SHALL record verification results with timestamp.
2. THE System SHALL publish all generation algorithms in a publicly accessible repository with version control.
3. WHEN a language definition version is specified, THE Platform SHALL generate identical language outputs for that version across repeated generations.
4. THE Platform's differentiation SHALL be specifically that it procedurally generates entirely NEW programming languages (not using pre-existing esolangs or DSLs), enabling controlled measurement of language complexity impact on LLM reasoning.

### Requirement 5: Language Generation Architecture

**User Story:** As a System Architect, I want a modular language generation system, so that new languages can be created consistently.

#### Acceptance Criteria

1. THE Language Generator SHALL accept seed input as a dictionary containing language name, syntax preferences, feature flags, and semantic options, and produce a LanguageSpec containing grammar rules, semantic configuration, and interpreter mappings.
2. THE Language identity SHALL be computed as SHA256(canonical_seed + spec_version + algorithm_version), where canonical_seed is JSON with sorted keys and generated_at is metadata only.
3. WHEN a language specification is produced, THE Grammar Engine SHALL produce context-free grammars in Lark format containing terminal definitions, production rules, and start symbols.
4. THE Language Generator SHALL NOT generate executable Python code; instead, it SHALL produce declarative specifications that the fixed interpreter uses with semantic mappings.
5. WHEN a generated language syntax is validated, THE System SHALL compare the generated syntax against the language registry and ensure no syntactic conflicts exist, where syntactic conflicts are defined as identical grammar rules producing different parse trees.
6. THE System SHALL support semantic variation through configurable dimensions including: arithmetic and short_circuit (MVP), with evaluation_order, type_coercion, scoping, and function_call deferred to future versions.
7. THE System SHALL REJECT language seeds requesting unsupported semantic combinations with a validation error; DO NOT silently fall back to default behavior.
8. WHERE a seed is provided with identical language parameters and version, THE Generator SHALL produce language specifications with identical language_id.

### Requirement 6: Formal Language Specification Format

**User Story:** As a Developer, I want a standard format for language specifications, so that languages can be stored and versioned.

#### Acceptance Criteria

1. THE Language Specification SHALL include: version, algorithm_version, language_id, seed, and difficulty fields.
2. THE Specification SHALL include a grammar object with start symbol, rules, and terminals.
3. THE Specification SHALL include a semantics object defining: evaluation_order, scoping, arithmetic, type_coercion.
4. THE Specification SHALL include built-in functions with their signatures and semantic operation mappings.
5. THE Specification SHALL include resource_limits defining: max_steps, max_ast_depth, max_call_depth, max_collection_size, max_string_size, max_output_size.
6. THE Specification SHALL include example programs demonstrating usage.
7. THE Specification SHALL include a generated_at timestamp as METADATA ONLY (NOT part of identity hash).

### Requirement 7: Grammar, Parser, and Interpreter Architecture

**User Story:** As a System, I need to parse and execute programs in generated languages.

#### Acceptance Criteria

1. THE Parser Generator SHALL use Lark to generate parsers from grammar specifications.
2. THE Interpreter SHALL operate on the Abstract Syntax Tree produced by the parser and evaluate using a FIXED evaluation engine with language-specific semantic mappings.
3. THE Interpreter SHALL support integer arithmetic, boolean logic, and function calls.
4. THE Interpreter SHALL be deterministic: same input always produces same output.
5. THE Interpreter SHALL enforce deterministic resource limits: max_steps (100000), max_ast_depth (1000), max_call_depth (100), max_collection_size (10000), max_string_size (1MB), max_output_size (1MB).
6. THE Interpreter SHALL return typed execution statuses: success, error, step_limit_exceeded, recursion_limit_exceeded, output_limit_exceeded, ast_depth_exceeded, invalid_program.
7. THE Interpreter SHALL NOT be considered fully sandboxed; process-level isolation is required for security.

### Requirement 8: Independent Test Oracle Strategy

**User Story:** As an Evaluator, I need independent verification of program correctness, so that evaluation is unbiased.

#### Acceptance Criteria

1. FOR each challenge, THE System SHALL generate a reference implementation using DIFFERENT templates than production challenges.
2. THE Reference Evaluator SHALL use a GENUINELY SEPARATE evaluation code path that DOES NOT import, call, or otherwise depend on the production ExecutionEngine.
3. THE Independent Reference Evaluator SHALL implement formal language semantics directly, without reusing production interpreter logic.
4. THE Reference Evaluator SHALL validate expected outputs against mathematical invariants and hand-verified baseline cases.
5. THE Test Oracle SHALL include cross-validation that detects disagreements between reference and production evaluators.
6. WHEN reference and production evaluators disagree, THE System SHALL mark the affected challenge or test case as INVALID/INCONCLUSIVE, never silently selecting one result.
7. THE Oracle SHALL compare actual outputs to expected outputs with detailed mismatch reporting.

### Requirement 9: Challenge Generation Architecture

**User Story:** As a Challenge Generator, I need to create evaluation challenges with public and hidden test cases.

#### Acceptance Criteria

1. THE Challenge Generator SHALL select problem templates from categories: array operations, string manipulation, recursion, sorting, search.
2. THE Problem Selector SHALL scale complexity based on difficulty parameter (1-5 scale), measuring: reasoning_steps, nesting_depth, state_dependencies, control_flow_complexity.
3. THE System SHALL produce 3-5 public example programs and 10-20 total test cases.
4. THE Hidden Test Cases SHALL include edge cases not demonstrated in examples.
5. ALL Test Cases SHALL have deterministic expected outputs verified by the reference implementation.
6. Challenge difficulty SHALL be computed independently from language difficulty.

### Requirement 10: Benchmark Evaluation Methodology

**User Story:** As a Benchmark Runner, I need a standardized evaluation workflow, so that results are comparable.

#### Acceptance Criteria

1. THE Evaluation Workflow SHALL include: challenge selection, language generation, example creation, test case generation, model invocation, execution, scoring, and aggregation.
2. THE Platform SHALL compute pass rate as (passed test cases / total test cases).
3. THE Platform SHALL compute generalization gap as (public_score - hidden_score).
4. THE Platform SHALL compute weighted correctness score using normalized weighted average: weighted_score = sum(raw_score_i * difficulty_weight_i) / sum(difficulty_weight_i).
5. THE Results SHALL be comparable across different runs using versioned language definitions.

### Requirement 11: Model Provider Abstraction

**User Story:** As a Platform, I need to support multiple model providers through a common interface.

#### Acceptance Criteria

1. THE Model Adapter SHALL implement a standard interface with list_models, generate, and estimate_tokens methods.
2. THE Platform SHALL support OpenAI-compatible APIs as the first implementation.
3. NEW model providers SHALL be addable without modifying core evaluation logic.
4. THE Prompt Builder SHALL include language specification, syntax rules, examples, and problem description but NOT hidden test cases.
5. THE Response Parser SHALL extract code from markdown code blocks or the entire response.

### Requirement 12: Database Schema Requirements

**User Story:** As a Platform, I need to store benchmark data for analysis and reproducibility.

#### Acceptance Criteria

1. THE Database SHALL store languages with id, seed, version, algorithm_version, specification, grammar, semantics_config, resource_limits, difficulty, and created_at. (Note: Database implementation is deferred to post-MVP)
2. THE Database SHALL store challenges with language reference, problem type, difficulty, description, examples, public_tests, hidden_tests, and reference_implementation.
3. THE Database SHALL store benchmark runs with model provider, model name, timestamps, status, and configuration.
4. THE Database SHALL store results with benchmark_run reference, challenge reference, model_response, execution_output, execution_time_ms, passed status, and test_results.
5. THE Database SHALL use SQLite for the MVP with zero cost.

### Requirement 13: Backend API Design

**User Story:** As a Developer, I want a RESTful API, so that I can integrate the platform programmatically.

#### Acceptance Criteria

1. THE API SHALL provide endpoints for language generation, challenge creation, evaluation, benchmark running, and result retrieval.
2. ALL API requests and responses SHALL use JSON format.
3. LONG-RUNNING operations SHALL return a job ID for polling status.
4. ERROR responses SHALL include error code, message, and details.
5. THE API SHALL provide OpenAPI-compatible documentation.

### Requirement 14: Frontend Information Architecture

**User Story:** As a User, I want an intuitive interface, so that I can easily navigate and use the platform.

#### Acceptance Criteria

1. THE Frontend SHALL include pages for: Dashboard, Language Explorer, Challenge Editor, Benchmark Runner, Results Viewer, and Settings.
2. THE User Journey for running a benchmark SHALL be: configure → start → watch progress → view results.
3. THE User Journey for exploring a language SHALL be: browse → view specification → see challenges.
4. THE Dashboard SHALL show recent benchmarks and quick actions.
5. THE Results Viewer SHALL show detailed metrics and comparison charts.

### Requirement 15: Security and Execution Isolation

**User Story:** As a Security Engineer, I need to ensure safe execution of untrusted code, so that the platform is secure.

#### Acceptance Criteria

1. ALL program execution SHALL occur in sandboxed environments (Docker containers or WASM sandbox).
2. THE Sandbox SHALL enforce: maximum 5 seconds CPU time, maximum 128MB memory, maximum 1MB output size.
3. THE Sandbox containers SHALL have no network access.
4. THE Sandbox SHALL have access only to a temporary working directory.
5. USER API keys SHALL be encrypted at rest and never logged.

### Requirement 16: Testing and Reproducibility Strategy

**User Story:** As a Developer, I need comprehensive testing, so that the platform works correctly.

#### Acceptance Criteria

1. THE Platform SHALL implement unit tests with 80% coverage target.
2. THE Platform SHALL implement integration tests for component interactions.
3. THE Platform SHALL implement end-to-end tests for core workflows.
4. ALL language generations SHALL record the seed used for reproducibility.
5. ALL benchmark results SHALL include sufficient context to reproduce exactly.

### Requirement 17: Deployment Strategy

**User Story:** As a DevOps Engineer, I need a zero-cost deployment solution, so that the platform is accessible without budget.

#### Acceptance Criteria

1. THE Platform SHALL be deployable as a Docker container.
2. THE Platform SHALL support configuration via environment variables.
3. THE Platform SHALL support local deployment for development.
4. THE Platform SHALL support free-tier cloud deployment (Railway, Render, or Fly.io).
5. docker-compose SHALL start API, DB, and sandbox services.

### Requirement 18: Hackathon Demonstration Plan

**User Story:** As a Hackathon Participant, I need a compelling demo, so that I can showcase the platform effectively.

#### Acceptance Criteria

1. THE Demo SHALL generate a new language live, showing grammar and interpreter.
2. THE Demo SHALL create a challenge with that language.
3. THE Demo SHALL run evaluation against 2-3 models side-by-side.
4. THE Demo SHALL show results comparison with detailed metrics.
5. THE Demo SHALL complete within the allocated time; backup plans reduce risk but on-time completion is mandatory.

### Requirement 19: Phased Implementation Roadmap

**User Story:** As a Project Manager, I need a phased roadmap, so that the MVP is achievable within the hackathon timeline.

#### Acceptance Criteria

1. PHASE 1 (MVP - 48 hours) SHALL include: Language Generator, Interpreter Executor, Challenge Generator, Basic API, Simple Frontend, OpenAI Integration, and Demo Flow.
2. PHASE 2 (Post-Hackathon) SHALL include: Multiple Providers, Result Persistence, Advanced Metrics, Benchmark Runner, Improved UI.
3. PHASE 3 (Future) SHALL include: Language Registry, Challenge Library, Leaderboards, API Rate Limiting, Community Features.
4. EACH task SHALL have clear dependencies and acceptance criteria.
5. THE MVP SHALL be achievable within the hackathon timeline with free technologies.

### Requirement 20: Critical Technical Requirements

**User Story:** As a Technical Lead, I need to ensure critical technical capabilities, so that the platform functions correctly.

#### Acceptance Criteria

1. THE Platform SHALL ensure deterministic execution through versioned interpreters.
2. THE Platform SHALL provide versioned language definitions with seed tracking.
3. THE Platform SHALL support reproducible generation using recorded seeds and versions.
4. THE Platform SHALL separate public examples from hidden test cases.
5. THE Platform SHALL prevent benchmark leakage through procedural generation.
6. THE Platform SHALL measure generalization beyond demonstration examples.
7. THE Platform SHALL enable fair comparison across models using same challenges.
8. THE Platform SHALL enforce interpreter-level resource limits (max_steps, max_ast_depth, max_call_depth, max_collection_size, max_string_size, max_output_size); submissions exceeding limits SHALL be treated as a distinct inconclusive status, not a failed/incorrect result.
9. THE Platform SHALL maintain reproducibility of benchmark results with full audit trail.
10. THE Interpreter SHALL NOT be considered fully sandboxed; THE Platform SHALL require process-level isolation (Docker/WASM) for untrusted program execution.