"""Judge Agent (Verdict/Judge): CrewAI agent bound to the `judge` role - a
200-300B-parameter-class model via OpenRouter, DeepSeek-V3 by default
(see app.crew.models and vector.md for why this is a swappable default,
not a final vendor decision). Reviews a Scoring Engine result plus
RAG-retrieved context and produces a `pass`/`review`/`fail` verdict with
narrative - never a bare score, matching the ideation doc's posture.

VHIRE-2x (RAG-driven Scoring Engine + Judge).
"""

import json

from crewai import Agent, Crew, Task

from app.crew.models import model_for_role
from app.models.enums import VerdictLabel


class JudgeResultParseError(Exception):
    """Raised when the Judge Agent's output isn't valid JSON with the expected shape."""


def build_judge_agent() -> Agent:
    """Construct the Judge Agent, bound to the configured `judge` model."""
    return Agent(
        role="Hiring Verdict Judge",
        goal=(
            "Review a deterministic Scoring Engine result together with supporting evidence, "
            "and produce a calibrated pass/review/fail verdict with a clear narrative rationale."
        ),
        backstory=(
            "A seasoned hiring panel chair who weighs structured scoring signals against "
            "qualitative context to reach a defensible, well-explained verdict - never a bare number."
        ),
        llm=model_for_role("judge"),
        verbose=False,
    )


def parse_judge_result(raw_output: str) -> dict:
    """Parse the Judge Agent's raw text output into `{"verdict_label", "narrative"}`.

    Raises:
        JudgeResultParseError: if the output isn't valid JSON, is missing
            either key, or `verdict_label` isn't a recognized value.
    """
    try:
        result = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        raise JudgeResultParseError(f"judge agent output was not valid JSON: {exc}") from exc

    if "narrative" not in result:
        raise JudgeResultParseError("judge agent output missing 'narrative'")
    try:
        VerdictLabel(result.get("verdict_label"))
    except ValueError as exc:
        raise JudgeResultParseError(
            f"judge agent output has an invalid verdict_label: {result.get('verdict_label')!r}"
        ) from exc

    return result


def run_judge(*, deterministic_score: dict, context_chunks: list[str], task_description: str) -> dict:
    """Run the Judge Agent over `deterministic_score` and `context_chunks`.

    `deterministic_score` is a required keyword argument with no default -
    the concrete I12 enforcement point: there is no way to call this
    function, and therefore no path to a Judge model call, without a
    preceding Scoring Engine result already computed by the caller.

    Returns `{"verdict_label": "pass"|"review"|"fail", "narrative": str}`.

    Raises:
        Whatever the underlying CrewAI/LiteLLM/OpenRouter call raises on
        failure, or `JudgeResultParseError` if the output doesn't parse -
        the caller (a `generate_*_verdict` task) is responsible for
        deciding how to handle either.
    """
    agent = build_judge_agent()
    context_text = "\n---\n".join(context_chunks) if context_chunks else "(no supporting context retrieved)"
    task = Task(
        description=(
            f"{task_description}\n\n"
            f"Deterministic Scoring Engine result (JSON):\n{json.dumps(deterministic_score)}\n\n"
            f"Supporting context (retrieved via RAG search):\n{context_text}\n\n"
            "Respond with ONLY a JSON object with exactly these keys: 'verdict_label' "
            "(one of 'pass', 'review', 'fail'), 'narrative' (a short paragraph explaining the verdict)."
        ),
        expected_output="A single JSON object with keys verdict_label, narrative.",
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[task], verbose=False)
    result = crew.kickoff()
    return parse_judge_result(str(result))
