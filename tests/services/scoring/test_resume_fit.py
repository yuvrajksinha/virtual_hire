"""Tests for app.services.scoring.resume_fit (E16-equivalent Scoring
Engine rules): pure, no DB/model calls, deterministic (I12).
"""

from app.services.scoring.resume_fit import score_resume_fit


def test_scores_full_skill_match():
    parsed_data = {"skills": ["Python", "SQL"], "work_history": [{"title": "Engineer"}]}
    requirements = {"required_skills": ["python", "sql"]}

    result = score_resume_fit(parsed_data, requirements)

    assert result["skill_match_ratio"] == 1.0
    assert result["matched_skills"] == ["python", "sql"]
    assert result["missing_skills"] == []
    assert result["flags"] == []


def test_scores_partial_skill_match():
    parsed_data = {"skills": ["Python"], "work_history": [{"title": "Engineer"}]}
    requirements = {"required_skills": ["python", "kubernetes"]}

    result = score_resume_fit(parsed_data, requirements)

    assert result["skill_match_ratio"] == 0.5
    assert result["missing_skills"] == ["kubernetes"]


def test_no_required_skills_yields_full_ratio():
    result = score_resume_fit({"skills": ["python"]}, {"required_skills": []})

    assert result["skill_match_ratio"] == 1.0


def test_flags_missing_work_history_and_skills():
    result = score_resume_fit({}, {"required_skills": []})

    assert "no_work_history_extracted" in result["flags"]
    assert "no_skills_extracted" in result["flags"]


def test_is_deterministic_for_identical_input():
    parsed_data = {"skills": ["Python", "Go"], "work_history": [{"title": "Engineer"}]}
    requirements = {"required_skills": ["python", "rust"]}

    first = score_resume_fit(parsed_data, requirements)
    second = score_resume_fit(parsed_data, requirements)

    assert first == second
