"""Transcript + Assignment Reviewer's deterministic Scoring Engine rules.
Pure function - see resume_fit.py's module docstring for the same
determinism/no-model-calls guarantees (I12).

VHIRE-2x. Assignment submissions/rubrics are out of scope for this
session (see vector.md) - `rubric` defaults to a minimal length-based
check rather than reading an `assignments.rubric` JSONB that doesn't
exist yet.
"""

DEFAULT_RUBRIC = {"min_word_count": 200}


def score_transcript(transcript_text: str, rubric: dict | None = None) -> dict:
    """Score a transcript against a competency rubric.

    Returns a structured sub-score/flag payload matching
    `verdicts.deterministic_score`'s JSONB shape.
    """
    rubric = rubric or DEFAULT_RUBRIC
    min_word_count = rubric.get("min_word_count", DEFAULT_RUBRIC["min_word_count"])
    word_count = len(transcript_text.split())

    flags = []
    if word_count < min_word_count:
        flags.append("transcript_below_minimum_length")

    return {
        "word_count": word_count,
        "min_word_count": min_word_count,
        "meets_minimum_length": word_count >= min_word_count,
        "flags": flags,
    }
