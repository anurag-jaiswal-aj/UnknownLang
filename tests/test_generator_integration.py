"""Generator-to-evaluator integration tests for M2.6.

These tests use the actual M2.5 task generator to produce valid tasks
and verify they pass through the public evaluate() API correctly.

Tests cover all four approved categories: EVAL, SYN, INF, CTRL.
"""

from __future__ import annotations

import pytest

from src.benchmark.generators.generator import TaskGenerator
from src.benchmark.harness import evaluate, AttemptOutcome
from src.benchmark.environments import build_environment


@pytest.fixture
def test_env():
    """Create a test environment."""
    return build_environment('wraparound', True, {
        'profile_schema_version': 1,
        'keywords': {'def': 'def', 'if': 'if'},
        'operators': {'add': 'add', 'sub': 'sub', 'mul': 'mul', 
                      'div': 'div', 'mod': 'mod', 'and': 'and', 
                      'or': 'or', 'not': 'not', 'eq': 'eq'},
        'literals': {'true': 'true', 'false': 'false'},
    })


@pytest.fixture
def task_generator(test_env):
    """Create a task generator with the test environment."""
    return TaskGenerator(
        environment_id=test_env.environment_id,
        derivation_seed='integration_test_seed_12345',
        environment_registry={test_env.environment_id: test_env},
    )


class TestGeneratorIntegration:
    """Integration tests using real M2.5 task generators."""
    
    def test_eval_category_correct_answer(self, task_generator, test_env):
        """Test EVAL category with correct answer."""
        result = task_generator.generate_single_task('EVAL', 1, 'FULL_DOC')
        assert result.success, f"Failed to generate EVAL task: {result.rejection_reason}"
        
        task = result.task
        expected_value = task.expected.value.get('value')
        
        response = f"ANSWER: {expected_value}"
        outcome = evaluate(task, test_env, response)
        
        assert outcome.outcome == "ok"
        assert outcome.score == 1
        assert outcome.failure_category == "ok"
    
    def test_eval_category_wrong_answer(self, task_generator, test_env):
        """Test EVAL category with wrong answer."""
        result = task_generator.generate_single_task('EVAL', 1, 'FULL_DOC')
        assert result.success, f"Failed to generate EVAL task: {result.rejection_reason}"
        
        task = result.task
        
        response = "ANSWER: 0"
        outcome = evaluate(task, test_env, response)
        
        assert outcome.outcome == "fail"
        assert outcome.score == 0
        assert outcome.failure_category == "wrong_answer"
    
    def test_eval_category_empty_response(self, task_generator, test_env):
        """Test EVAL category with empty response."""
        result = task_generator.generate_single_task('EVAL', 1, 'FULL_DOC')
        assert result.success, f"Failed to generate EVAL task: {result.rejection_reason}"
        
        task = result.task
        
        response = ""
        outcome = evaluate(task, test_env, response)
        
        assert outcome.outcome == "void"
        assert outcome.score is None
        assert outcome.failure_category == "extraction_failed"
    
    def test_eval_category_missing_answer_line(self, task_generator, test_env):
        """Test EVAL category with missing ANSWER: line."""
        result = task_generator.generate_single_task('EVAL', 1, 'FULL_DOC')
        assert result.success, f"Failed to generate EVAL task: {result.rejection_reason}"
        
        task = result.task
        
        response = "The answer is 42."
        outcome = evaluate(task, test_env, response)
        
        assert outcome.outcome == "void"
        assert outcome.score is None
        assert outcome.failure_category == "extraction_failed"
    
    def test_eval_category_malformed_answer(self, task_generator, test_env):
        """Test EVAL category with malformed (non-integer) answer."""
        result = task_generator.generate_single_task('EVAL', 1, 'FULL_DOC')
        assert result.success, f"Failed to generate EVAL task: {result.rejection_reason}"
        
        task = result.task
        
        response = "ANSWER: not_a_number"
        outcome = evaluate(task, test_env, response)
        
        assert outcome.outcome == "fail"
        assert outcome.score == 0
        assert outcome.failure_category == "invalid_answer"
    
    def test_syn_category_correct_answer(self, task_generator, test_env):
        """Test SYN category with correct answer."""
        result = task_generator.generate_single_task('SYN', 1, 'FULL_DOC')
        assert result.success, f"Failed to generate SYN task: {result.rejection_reason}"
        
        task = result.task
        expected_value = task.expected.value.get('value')
        
        response = f"ANSWER: {expected_value}"
        outcome = evaluate(task, test_env, response)
        
        assert outcome.outcome == "ok"
        assert outcome.score == 1
        assert outcome.failure_category == "ok"
    
    def test_inf_category_correct_answer(self, task_generator, test_env):
        """Test INF category with correct answer."""
        result = task_generator.generate_single_task('INF', 1, 'FULL_DOC')
        assert result.success, f"Failed to generate INF task: {result.rejection_reason}"
        
        task = result.task
        expected_value = task.expected.value.get('value')
        
        response = f"ANSWER: {expected_value}"
        outcome = evaluate(task, test_env, response)
        
        assert outcome.outcome == "ok"
        assert outcome.score == 1
        assert outcome.failure_category == "ok"
    
    def test_ctrl_category_correct_answer(self, task_generator, test_env):
        """Test CTRL category with correct answer."""
        result = task_generator.generate_single_task('CTRL', 1, 'FULL_DOC')
        assert result.success, f"Failed to generate CTRL task: {result.rejection_reason}"
        
        task = result.task
        expected_value = task.expected.value.get('value')
        
        response = f"ANSWER: {expected_value}"
        outcome = evaluate(task, test_env, response)
        
        assert outcome.outcome == "ok"
        assert outcome.score == 1
        assert outcome.failure_category == "ok"
    
    def test_deterministic_evaluation(self, task_generator, test_env):
        """Test that repeated evaluation produces identical outcomes."""
        result = task_generator.generate_single_task('EVAL', 1, 'FULL_DOC')
        assert result.success, f"Failed to generate EVAL task: {result.rejection_reason}"
        
        task = result.task
        expected_value = task.expected.value.get('value')
        response = f"ANSWER: {expected_value}"
        
        outcomes = []
        for _ in range(5):
            outcome = evaluate(task, test_env, response)
            outcomes.append(outcome)
        
        # All outcomes should be identical
        first = outcomes[0]
        for outcome in outcomes[1:]:
            assert outcome == first
    
    def test_expected_value_extraction_int(self, task_generator, test_env):
        """Test that Expected dataclass with int value is handled correctly."""
        result = task_generator.generate_single_task('EVAL', 1, 'FULL_DOC')
        assert result.success, f"Failed to generate EVAL task: {result.rejection_reason}"
        
        task = result.task
        
        # Verify expected is Expected dataclass
        assert hasattr(task.expected, 'value')
        assert isinstance(task.expected.value, dict)
        assert task.expected.value.get('kind') == 'int'
        
        response = f"ANSWER: {task.expected.value.get('value')}"
        outcome = evaluate(task, test_env, response)
        
        assert outcome.outcome == "ok"
    

    
    def test_program_task_rejection(self, task_generator, test_env):
        """Test that program tasks are rejected with invalid_submission."""
        # Generate a task first
        result = task_generator.generate_single_task('EVAL', 1, 'FULL_DOC')
        assert result.success, f"Failed to generate task: {result.rejection_reason}"
        
        task = result.task
        
        # Create a program task by modifying the answer_spec
        from src.challenge.types import TaskRecord, AnswerSpec, Protocol, Difficulty, Prompt, Evaluation, Expected
        program_task = TaskRecord(
            schema_version=task.schema_version,
            task_id='program_task_test',
            template=task.template,
            category=task.category,
            protocol=Protocol(kind='standalone'),
            environment_id=test_env.environment_id,
            difficulty=Difficulty(level=1, reasoning_steps=1, nesting_depth=1, 
                                  control_flow='none', state='none'),
            information_condition='FULL_DOC',
            prompt=Prompt(template=('prompt.answer', 1), example_policy='none',
                          public_examples=[], query='Test'),
            answer_spec=AnswerSpec(type='program', kind=None, form='expression'),
            expected=Expected(value={'kind': 'int', 'value': 42}),
            evaluation=Evaluation(method='exact_match', limits={'max_steps': 100000, 
                         'max_ast_depth': 100, 'max_call_depth': 50}, tests=[]),
        )
        
        response = "ANSWER: 42"
        outcome = evaluate(program_task, test_env, response)
        
        assert outcome.outcome == "void"
        assert outcome.score is None
        assert outcome.failure_category == "invalid_submission"
        assert outcome.detail == "program_task_unsupported"
    
    def test_syn_category_wrong_answer(self, task_generator, test_env):
        """Test SYN category with wrong answer."""
        result = task_generator.generate_single_task('SYN', 1, 'FULL_DOC')
        assert result.success, f"Failed to generate SYN task: {result.rejection_reason}"
        
        task = result.task
        
        response = "ANSWER: 0"
        outcome = evaluate(task, test_env, response)
        
        assert outcome.outcome == "fail"
        assert outcome.score == 0
        assert outcome.failure_category == "wrong_answer"
    
    def test_syn_category_empty_response(self, task_generator, test_env):
        """Test SYN category with empty response."""
        result = task_generator.generate_single_task('SYN', 1, 'FULL_DOC')
        assert result.success, f"Failed to generate SYN task: {result.rejection_reason}"
        
        task = result.task
        
        response = ""
        outcome = evaluate(task, test_env, response)
        
        assert outcome.outcome == "void"
        assert outcome.score is None
        assert outcome.failure_category == "extraction_failed"
    
    def test_syn_category_missing_answer_line(self, task_generator, test_env):
        """Test SYN category with missing ANSWER: line."""
        result = task_generator.generate_single_task('SYN', 1, 'FULL_DOC')
        assert result.success, f"Failed to generate SYN task: {result.rejection_reason}"
        
        task = result.task
        
        response = "The answer is 42."
        outcome = evaluate(task, test_env, response)
        
        assert outcome.outcome == "void"
        assert outcome.score is None
        assert outcome.failure_category == "extraction_failed"
    
    def test_syn_category_malformed_answer(self, task_generator, test_env):
        """Test SYN category with malformed (non-integer) answer."""
        result = task_generator.generate_single_task('SYN', 1, 'FULL_DOC')
        assert result.success, f"Failed to generate SYN task: {result.rejection_reason}"
        
        task = result.task
        
        response = "ANSWER: not_a_number"
        outcome = evaluate(task, test_env, response)
        
        assert outcome.outcome == "fail"
        assert outcome.score == 0
        assert outcome.failure_category == "invalid_answer"
    
    def test_inf_category_wrong_answer(self, task_generator, test_env):
        """Test INF category with wrong answer."""
        result = task_generator.generate_single_task('INF', 1, 'FULL_DOC')
        assert result.success, f"Failed to generate INF task: {result.rejection_reason}"
        
        task = result.task
        
        response = "ANSWER: 0"
        outcome = evaluate(task, test_env, response)
        
        assert outcome.outcome == "fail"
        assert outcome.score == 0
        assert outcome.failure_category == "wrong_answer"
    
    def test_inf_category_empty_response(self, task_generator, test_env):
        """Test INF category with empty response."""
        result = task_generator.generate_single_task('INF', 1, 'FULL_DOC')
        assert result.success, f"Failed to generate INF task: {result.rejection_reason}"
        
        task = result.task
        
        response = ""
        outcome = evaluate(task, test_env, response)
        
        assert outcome.outcome == "void"
        assert outcome.score is None
        assert outcome.failure_category == "extraction_failed"
    
    def test_inf_category_missing_answer_line(self, task_generator, test_env):
        """Test INF category with missing ANSWER: line."""
        result = task_generator.generate_single_task('INF', 1, 'FULL_DOC')
        assert result.success, f"Failed to generate INF task: {result.rejection_reason}"
        
        task = result.task
        
        response = "The answer is 42."
        outcome = evaluate(task, test_env, response)
        
        assert outcome.outcome == "void"
        assert outcome.score is None
        assert outcome.failure_category == "extraction_failed"
    
    def test_inf_category_malformed_answer(self, task_generator, test_env):
        """Test INF category with malformed (non-integer) answer."""
        result = task_generator.generate_single_task('INF', 1, 'FULL_DOC')
        assert result.success, f"Failed to generate INF task: {result.rejection_reason}"
        
        task = result.task
        
        response = "ANSWER: not_a_number"
        outcome = evaluate(task, test_env, response)
        
        assert outcome.outcome == "fail"
        assert outcome.score == 0
        assert outcome.failure_category == "invalid_answer"
    
    def test_ctrl_category_wrong_answer(self, task_generator, test_env):
        """Test CTRL category with wrong answer."""
        result = task_generator.generate_single_task('CTRL', 1, 'FULL_DOC')
        assert result.success, f"Failed to generate CTRL task: {result.rejection_reason}"
        
        task = result.task
        
        response = "ANSWER: 0"
        outcome = evaluate(task, test_env, response)
        
        assert outcome.outcome == "fail"
        assert outcome.score == 0
        assert outcome.failure_category == "wrong_answer"
    
    def test_ctrl_category_empty_response(self, task_generator, test_env):
        """Test CTRL category with empty response."""
        result = task_generator.generate_single_task('CTRL', 1, 'FULL_DOC')
        assert result.success, f"Failed to generate CTRL task: {result.rejection_reason}"
        
        task = result.task
        
        response = ""
        outcome = evaluate(task, test_env, response)
        
        assert outcome.outcome == "void"
        assert outcome.score is None
        assert outcome.failure_category == "extraction_failed"
    
    def test_ctrl_category_missing_answer_line(self, task_generator, test_env):
        """Test CTRL category with missing ANSWER: line."""
        result = task_generator.generate_single_task('CTRL', 1, 'FULL_DOC')
        assert result.success, f"Failed to generate CTRL task: {result.rejection_reason}"
        
        task = result.task
        
        response = "The answer is 42."
        outcome = evaluate(task, test_env, response)
        
        assert outcome.outcome == "void"
        assert outcome.score is None
        assert outcome.failure_category == "extraction_failed"
    
    def test_ctrl_category_malformed_answer(self, task_generator, test_env):
        """Test CTRL category with malformed (non-integer) answer."""
        result = task_generator.generate_single_task('CTRL', 1, 'FULL_DOC')
        assert result.success, f"Failed to generate CTRL task: {result.rejection_reason}"
        
        task = result.task
        
        response = "ANSWER: not_a_number"
        outcome = evaluate(task, test_env, response)
        
        assert outcome.outcome == "fail"
        assert outcome.score == 0
        assert outcome.failure_category == "invalid_answer"
    
    def test_syn_category_boolean_correct_answer(self, task_generator, test_env):
        """Test SYN category with boolean answer (manual boolean task construction)."""
        # SYN tasks normally produce int values, so we manually construct a boolean task
        # This ensures we have test coverage for boolean expected values
        from src.challenge.types import TaskRecord, Protocol, Difficulty, Prompt, AnswerSpec, Evaluation, Expected
        
        syn_bool_task = TaskRecord(
            schema_version=1,
            task_id='syn_bool_manual',
            template=('syn.bool_test', 1),
            category='SYN',
            protocol=Protocol(kind='standalone'),
            environment_id=test_env.environment_id,
            difficulty=Difficulty(level=1, reasoning_steps=1, nesting_depth=1, 
                                  control_flow='none', state='none'),
            information_condition='FULL_DOC',
            prompt=Prompt(template=('prompt.answer', 1), example_policy='none',
                          public_examples=[], query='Return true.'),
            answer_spec=AnswerSpec(type='value', kind='bool', form=None),
            expected=Expected(value={'kind': 'bool', 'value': True}),
            evaluation=Evaluation(method='exact_match', limits={'max_steps': 100000, 
                         'max_ast_depth': 100, 'max_call_depth': 50}, tests=[]),
        )
        
        response = "ANSWER: true"
        outcome = evaluate(syn_bool_task, test_env, response)
        
        assert outcome.outcome == "ok"
        assert outcome.score == 1
        assert outcome.failure_category == "ok"
    
    def test_ctrl_category_boolean_correct_answer(self, task_generator, test_env):
        """Test CTRL category with boolean answer (manual boolean task construction)."""
        # CTRL tasks normally produce int values, so we manually construct a boolean task
        from src.challenge.types import TaskRecord, Protocol, Difficulty, Prompt, AnswerSpec, Evaluation, Expected
        
        ctrl_bool_task = TaskRecord(
            schema_version=1,
            task_id='ctrl_bool_manual',
            template=('ctrl.bool_test', 1),
            category='CTRL',
            protocol=Protocol(kind='standalone'),
            environment_id=test_env.environment_id,
            difficulty=Difficulty(level=1, reasoning_steps=1, nesting_depth=1, 
                                  control_flow='none', state='none'),
            information_condition='FULL_DOC',
            prompt=Prompt(template=('prompt.answer', 1), example_policy='none',
                          public_examples=[], query='Return false.'),
            answer_spec=AnswerSpec(type='value', kind='bool', form=None),
            expected=Expected(value={'kind': 'bool', 'value': False}),
            evaluation=Evaluation(method='exact_match', limits={'max_steps': 100000, 
                         'max_ast_depth': 100, 'max_call_depth': 50}, tests=[]),
        )
        
        response = "ANSWER: false"
        outcome = evaluate(ctrl_bool_task, test_env, response)
        
        assert outcome.outcome == "ok"
        assert outcome.score == 1
        assert outcome.failure_category == "ok"
