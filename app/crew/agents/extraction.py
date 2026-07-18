"""Extraction Agent: CrewAI agent bound to the `extraction` role (Claude
Haiku 4.5 via OpenRouter by default - see app.crew.models), extracting
structured work history/education/skills fields from raw resume text.

VHIRE-2x (E6). See docs/06-architecture.md's Parsing Worker row and
docs/07-technical-stack.md's per-task model assignment.
"""

import json

from crewai import Agent, Crew, Task

from app.crew.models import model_for_role


class ExtractionResultParseError(Exception):
    """Raised when the Extraction Agent's output isn't valid JSON."""


def build_extraction_agent() -> Agent:
    """Construct the Extraction Agent, bound to the configured `extraction` model."""
    return Agent(
        role="Resume Extraction Specialist",
        goal="Extract structured work history, education, and skills fields from raw resume text.",
        backstory=(
            "An expert technical recruiter who has read thousands of resumes and can "
            "reliably pull structured facts out of unstructured text."
        ),
        llm=model_for_role("extraction"),
        verbose=False,
    )


def parse_extraction_result(raw_output: str) -> dict:
    """Parse the Extraction Agent's raw text output into a structured dict.

    Raises:
        ExtractionResultParseError: if `raw_output` isn't valid JSON.
    """
    try:
        return json.loads(raw_output)
    except json.JSONDecodeError as exc:
        raise ExtractionResultParseError(f"extraction agent output was not valid JSON: {exc}") from exc


def extract_resume_fields(resume_text: str) -> dict:
    """Run the Extraction Agent over `resume_text`, returning structured fields
    (`work_history`, `education`, `skills`).

    Raises:
        Whatever the underlying CrewAI/LiteLLM/OpenRouter call raises on
        failure (network, auth, rate limit), or `ExtractionResultParseError`
        if the model's output isn't valid JSON - the caller
        (`app.workers.tasks.parsing.parse_resume`) is responsible for
        catching this and setting `status=parse_failed` (I6).
    """
    agent = build_extraction_agent()
    task = Task(
        description=(
            "Extract structured fields from the following resume text. Respond with "
            "ONLY a JSON object with exactly these keys: 'work_history' (list of "
            "{title, company, start_date, end_date} objects), 'education' (list of "
            "{institution, degree, field} objects), 'skills' (list of strings). "
            f"Resume text:\n\n{resume_text}"
        ),
        expected_output="A single JSON object with keys work_history, education, skills.",
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[task], verbose=False)
    result = crew.kickoff()
    return parse_extraction_result(str(result))
