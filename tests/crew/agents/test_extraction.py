"""Tests for app.crew.agents.extraction's pure result-parsing logic
(VHIRE-2x / E6). `extract_resume_fields` itself makes a real LLM call via
CrewAI/OpenRouter and isn't covered here - `app.workers.tasks.parsing`'s
tests mock it wholesale at that boundary instead.
"""

import pytest

from app.crew.agents.extraction import ExtractionResultParseError, parse_extraction_result


def test_parse_extraction_result_parses_valid_json():
    raw = '{"work_history": [], "education": [], "skills": ["python"]}'

    result = parse_extraction_result(raw)

    assert result == {"work_history": [], "education": [], "skills": ["python"]}


def test_parse_extraction_result_raises_on_invalid_json():
    with pytest.raises(ExtractionResultParseError):
        parse_extraction_result("not json at all")
