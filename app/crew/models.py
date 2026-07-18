"""OpenRouter model-configuration layer for every crew agent role.

VHIRE-2x (E6, extended by E17). Maps a logical role name to the
OpenRouter-routed model ID LiteLLM (a transitive CrewAI dependency)
resolves via its `openrouter/` provider prefix - a config/credential
change, not new SDK code, per the 2026-07-16 OpenRouter revision in
docs/07-technical-stack.md. Every crew agent (Extraction, Summarizer,
Reasoning, Judge) reads its model ID from here rather than hardcoding
one, so a future model swap for any role is a settings change - see
vector.md for the Judge model's swappable-default status.
"""

import os

from app.core.config import get_settings

_ROLES = ("extraction", "summarization", "reasoning", "judge")


def _ensure_openrouter_env_var_set() -> None:
    """LiteLLM (CrewAI's underlying model-call layer) reads `OPENROUTER_API_KEY`
    directly from `os.environ`, not from this app's Settings object - set it
    once here so callers don't depend on the process shell having already
    sourced `.env` itself.
    """
    settings = get_settings()
    if settings.openrouter_api_key:
        os.environ["OPENROUTER_API_KEY"] = settings.openrouter_api_key


def model_for_role(role: str) -> str:
    """Return the OpenRouter model ID configured for `role`.

    Raises:
        ValueError: if `role` isn't one of "extraction", "summarization",
            "reasoning", "judge".
    """
    if role not in _ROLES:
        raise ValueError(f"unknown crew role: {role!r} (expected one of {_ROLES})")

    _ensure_openrouter_env_var_set()
    settings = get_settings()
    return {
        "extraction": settings.extraction_model,
        "summarization": settings.summarization_model,
        "reasoning": settings.reasoning_model,
        "judge": settings.judge_model,
    }[role]
