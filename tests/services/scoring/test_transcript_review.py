"""Tests for app.services.scoring.transcript_review (Scoring Engine
rules for the transcript verdict): pure, deterministic (I12).
"""

from app.services.scoring.transcript_review import score_transcript


def test_flags_transcript_below_minimum_length():
    result = score_transcript("short transcript", rubric={"min_word_count": 10})

    assert result["meets_minimum_length"] is False
    assert "transcript_below_minimum_length" in result["flags"]


def test_meets_minimum_length():
    text = " ".join(["word"] * 20)

    result = score_transcript(text, rubric={"min_word_count": 10})

    assert result["meets_minimum_length"] is True
    assert result["flags"] == []


def test_uses_default_rubric_when_none_given():
    result = score_transcript("short")

    assert result["min_word_count"] == 200
    assert result["meets_minimum_length"] is False


def test_is_deterministic_for_identical_input():
    text = "some transcript content here"

    assert score_transcript(text) == score_transcript(text)
