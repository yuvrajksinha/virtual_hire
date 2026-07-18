"""Tests for app.crew.agents.judge's pure result-parsing logic and the
I12 signature-level guarantee. `run_judge` itself makes a real LLM call
via CrewAI/OpenRouter and isn't covered here - the `verdicts` task tests
mock it wholesale at that boundary instead.
"""

import inspect

import pytest

from app.crew.agents.judge import JudgeResultParseError, parse_judge_result, run_judge


def test_parse_judge_result_parses_valid_json():
    raw = '{"verdict_label": "pass", "narrative": "Strong candidate."}'

    result = parse_judge_result(raw)

    assert result == {"verdict_label": "pass", "narrative": "Strong candidate."}


def test_parse_judge_result_raises_on_invalid_json():
    with pytest.raises(JudgeResultParseError):
        parse_judge_result("not json")


def test_parse_judge_result_raises_on_missing_narrative():
    with pytest.raises(JudgeResultParseError):
        parse_judge_result('{"verdict_label": "pass"}')


def test_parse_judge_result_raises_on_invalid_verdict_label():
    with pytest.raises(JudgeResultParseError):
        parse_judge_result('{"verdict_label": "maybe", "narrative": "..."}')


def test_run_judge_requires_deterministic_score_with_no_default():
    """I12: there is no way to call run_judge without supplying a
    deterministic_score - enforced at the function-signature level."""
    signature = inspect.signature(run_judge)

    assert signature.parameters["deterministic_score"].default is inspect.Parameter.empty


def test_run_judge_raises_type_error_when_deterministic_score_omitted():
    with pytest.raises(TypeError):
        run_judge(context_chunks=[], task_description="review")
