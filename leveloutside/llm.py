from __future__ import annotations

import json
import os
from typing import Callable

import httpx

from .safety import AGE_RULES, ALLOWED_MATERIALS, KNOWN_SCENE_NOUNS
from .text_utils import normalize_noun
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


def _shape_example(duration: int) -> str:
    """A placeholder-only JSON shape (no real content, so nothing to copy)."""
    base, extra = divmod(duration, 3)
    mins = [base + (1 if i < extra else 0) for i in range(3)]
    return (
        "{\n"
        '  "title": "<short title>",\n'
        '  "story_hook": "<one or two short sentences in the game\'s voice>",\n'
        '  "tasks": [\n'
        '    {"mechanic": "<one verb>", "instruction": "<one short sentence>", '
        f'"objects": ["<a confirmed object>"], "materials": [], "minutes": {mins[0]}}},\n'
        '    {"mechanic": "<one verb>", "instruction": "<one short sentence>", '
        f'"objects": [], "materials": ["<an allowed material>"], "minutes": {mins[1]}}},\n'
        '    {"mechanic": "<one verb>", "instruction": "<one short sentence>", '
        f'"objects": ["<a confirmed object>"], "materials": [], "minutes": {mins[2]}}}\n'
        "  ],\n"
        '  "finale": "<one short sentence>",\n'
        '  "achievement_name": "<short name>"\n'
        "}"
    )


def _system_prompt(profile: dict, confirmed_objects: set[str], ctx: MissionContext) -> str:
    rules = AGE_RULES[ctx.age_band]
    task_lo, task_hi = rules["tasks"]
    max_grade = rules["max_grade"]
    material_list = ", ".join(sorted(ALLOWED_MATERIALS))
    object_list = ", ".join(sorted(confirmed_objects)) if confirmed_objects else "(none — use ground and sky only)"

    confirmed_norm = {normalize_noun(o) for o in confirmed_objects}
    absent = ", ".join(sorted(KNOWN_SCENE_NOUNS - confirmed_norm))

    verb_list = profile.get("verbs", [])
    verbs = ", ".join(verb_list)
    vocab = ", ".join(profile.get("vocabulary", []))
    goal = profile.get("goal", "")
    game_title = profile.get("title", "")
    mechanic_rule = (
        f"each task's \"mechanic\" is exactly ONE word from: {verbs}"
        if verb_list else "each task's \"mechanic\" is exactly ONE plain verb"
    )

    return f"""You are writing an outdoor mission card for a child aged {ctx.age_band} in the style of {game_title}.

GAME GOAL: {goal}
GAME VERBS: {verbs}
GAME VOCABULARY: {vocab}

RULES YOU MUST FOLLOW — no exceptions:
- Use ONLY these confirmed outdoor objects: {object_list}
- Name no scene objects outside the confirmed list.
- A task's "objects" list may contain ONLY confirmed objects (it may be empty).
- Materials must come ONLY from this list: {material_list}
- A task's "materials" list holds items from the materials list. Never put a material in "objects".
- Describe objects as fallen or lying on the ground (for example: "fallen leaves" and "sticks from the ground"). Never ask the child to pick anything off living plants.
- Do not mention these things, because they are NOT here: {absent}
- Number of tasks: between {task_lo} and {task_hi} (inclusive)
- Task minutes must total exactly {ctx.duration_min}; check your sum before answering
- {mechanic_rule}
- Flesch-Kincaid reading grade must be {max_grade} or lower; use short sentences and simple words
- Address the child only as "Explorer"
- Every task is a physical activity supervised by a grown-up outdoors
- No screens, no devices
- Never mention monsters, mobs, creatures, enemies, or any living thing, even if the game normally has them.
- NEVER mention: animals, dogs, cats, birds, pets, people, strangers, water, swimming, \
climbing, roofs, ladders, roads, streets, traffic, fire, matches, knives, scissors, hammers, \
eating, tasting, drinking, digging, or being alone / without a grown-up

OUTPUT: a single JSON object, JSON only, no markdown and no explanation. Shape example only (write a new mission for {game_title}, do not copy the placeholders):
{_shape_example(ctx.duration_min)}"""


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
