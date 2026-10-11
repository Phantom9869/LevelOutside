from __future__ import annotations

import json
import os
from typing import Callable

import httpx

from .safety import AGE_RULES, ALLOWED_MATERIALS
from .schema import Mission
from .validator import MissionContext

_DEFAULT_MODEL = "gemma3:4b"
_TIMEOUT = 300.0


def _ollama_host() -> str:
    return os.environ.get("OLLAMA_HOST", "http://localhost:11434")


def _model_name(model: str | None) -> str:
    if model:
        return model
    return os.environ.get("LEVELOUTSIDE_MODEL", _DEFAULT_MODEL)


def _system_prompt(profile: dict, confirmed_objects: set[str], ctx: MissionContext) -> str:
    rules = AGE_RULES[ctx.age_band]
    task_lo, task_hi = rules["tasks"]
    max_grade = rules["max_grade"]
    material_list = ", ".join(sorted(ALLOWED_MATERIALS))
    object_list = ", ".join(sorted(confirmed_objects)) if confirmed_objects else "(none — use ground and sky only)"

    verbs = ", ".join(profile.get("verbs", []))
    vocab = ", ".join(profile.get("vocabulary", []))
    goal = profile.get("goal", "")
    game_title = profile.get("title", "")

    return f"""You are writing an outdoor mission card for a child aged {ctx.age_band} in the style of {game_title}.

GAME GOAL: {goal}
GAME VERBS: {verbs}
GAME VOCABULARY: {vocab}

RULES YOU MUST FOLLOW — no exceptions:
- Use ONLY these confirmed outdoor objects: {object_list}
- Materials must come ONLY from this list: {material_list}
- Number of tasks: between {task_lo} and {task_hi} (inclusive)
- Task minutes must total exactly {ctx.duration_min}
- Flesch-Kincaid reading grade must be {max_grade} or lower; use short sentences and simple words
- Address the child only as "Explorer"
- Every task is a physical activity supervised by a grown-up outdoors
- No screens, no devices
- NEVER mention: animals, dogs, cats, birds, pets, people, strangers, water, swimming, \
climbing, roofs, ladders, roads, streets, traffic, fire, matches, knives, scissors, hammers, \
eating, tasting, drinking, digging, or being alone / without a grown-up

OUTPUT: a single JSON object matching the Mission schema. No markdown, no explanation — JSON only."""


def _build_messages(
    system: str,
    feedback: list[str],
    schema_in_prompt: bool,
) -> list[dict]:
    user_parts = ["Write the outdoor mission card now."]
    if schema_in_prompt:
        user_parts.append(
            "\nUse this JSON schema for your response:\n"
            + json.dumps(Mission.model_json_schema(), indent=2)
        )
    if feedback:
        user_parts.append("\nFix these problems:\n" + "\n".join(f"- {e}" for e in feedback))
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n".join(user_parts)},
    ]


def _chat(
    client: httpx.Client,
    model: str,
    messages: list[dict],
    fmt: str | dict,
) -> str:
    """POST to Ollama /api/chat and return the message content string."""
    url = _ollama_host().rstrip("/") + "/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.4},
        "format": fmt,
    }
    try:
        resp = client.post(url, json=payload, timeout=_TIMEOUT)
        resp.raise_for_status()
    except httpx.ConnectError as exc:
        raise RuntimeError(
            f"Cannot reach Ollama at {_ollama_host()}. "
            "Is Ollama running? (ollama serve)"
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Ollama returned HTTP {exc.response.status_code}: {exc.response.text[:300]}"
        ) from exc
    data = resp.json()
    return data["message"]["content"]


def make_generator(
    profile: dict,
    confirmed_objects: set[str],
    ctx: MissionContext,
    model: str | None = None,
) -> Callable[[list[str]], str]:
    """Return a callable that calls Ollama and returns the raw response string."""
    resolved_model = _model_name(model)
    system = _system_prompt(profile, confirmed_objects, ctx)
    schema: str | dict = Mission.model_json_schema()

    def generate(feedback: list[str]) -> str:
        nonlocal schema
        messages = _build_messages(system, feedback, schema_in_prompt=(schema == "json"))
        with httpx.Client() as client:
            try:
                return _chat(client, resolved_model, messages, schema)
            except RuntimeError as exc:
                # If Ollama rejected the structured schema, fall back to format="json"
                # with the schema embedded in the prompt text.
                if "schema" in str(exc).lower() or "format" in str(exc).lower() or "400" in str(exc):
                    schema = "json"
                    messages = _build_messages(system, feedback, schema_in_prompt=True)
                    return _chat(client, resolved_model, messages, schema)
                raise
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (400, 422):
                    schema = "json"
                    messages = _build_messages(system, feedback, schema_in_prompt=True)
                    return _chat(client, resolved_model, messages, schema)
                raise RuntimeError(
                    f"Ollama returned HTTP {exc.response.status_code}: {exc.response.text[:300]}"
                ) from exc

    return generate
