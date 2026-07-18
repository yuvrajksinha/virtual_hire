"""Resume Analyzer's deterministic Scoring Engine rules. Pure function, no
model calls, no DB access - unit-testable in isolation, and produces
identical output for identical input (determinism is directly tested,
not assumed, per EPIC.md's E16 DoD).

VHIRE-2x (RAG-driven Scoring Engine + Judge, resume verdict).
"""


def score_resume_fit(parsed_data: dict, requisition_requirements: dict) -> dict:
    """Score a parsed resume's fit against a requisition's requirements.

    `parsed_data` is a Resume's `parsed_data` JSONB (`work_history`,
    `education`, `skills`, as produced by the Extraction Agent).
    `requisition_requirements` reads an optional `required_skills` list
    (e.g. drawn from `job_requisitions.scorecard_template`).

    Returns a structured sub-score/flag payload matching
    `verdicts.deterministic_score`'s JSONB shape - never a bare number,
    per the "narrative over score" posture in docs/00-ideation.md.
    """
    resume_skills = {s.strip().lower() for s in parsed_data.get("skills") or [] if isinstance(s, str)}
    required_skills = {
        s.strip().lower() for s in requisition_requirements.get("required_skills") or [] if isinstance(s, str)
    }

    matched = sorted(resume_skills & required_skills)
    missing = sorted(required_skills - resume_skills)
    skill_match_ratio = (len(matched) / len(required_skills)) if required_skills else 1.0

    flags = []
    if not parsed_data.get("work_history"):
        flags.append("no_work_history_extracted")
    if not parsed_data.get("skills"):
        flags.append("no_skills_extracted")

    return {
        "skill_match_ratio": round(skill_match_ratio, 4),
        "matched_skills": matched,
        "missing_skills": missing,
        "roles_listed": len(parsed_data.get("work_history") or []),
        "flags": flags,
    }
