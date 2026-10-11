from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from pydantic import ValidationError

from .safety import (
    AGE_RULES,
    ALLOWED_MATERIALS,
    ALWAYS_ALLOWED_OBJECTS,
    KNOWN_SCENE_NOUNS,
    unsafe_matches,
)
from .schema import Mission
from .text_utils import fk_grade, normalize_noun, words


@dataclass
class MissionContext:
    confirmed_objects: set[str]
    age_band: str
    duration_min: int
    tolerance: float = 0.10

    def __post_init__(self) -> None:
        if self.age_band not in AGE_RULES:
            raise ValueError(f"unknown age band: {self.age_band}")

    def allowed_objects(self) -> set[str]:
        return {normalize_noun(o) for o in self.confirmed_objects} | ALWAYS_ALLOWED_OBJECTS


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)  # fed back to the model
    codes: list[str] = field(default_factory=list)   # safe to send to tracing
    mission: Mission | None = None


def _parse(raw) -> Mission:
    if isinstance(raw, Mission):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
        raw = json.loads(s)
    return Mission.model_validate(raw)


def validate_mission(raw, ctx: MissionContext) -> ValidationResult:
    try:
        m = _parse(raw)
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
        return ValidationResult(
            False,
            ["Output was not valid JSON matching the mission schema."],
            ["schema"],
        )

    errors: list[str] = []
    codes: list[str] = []

    def fail(code: str, msg: str) -> None:
        errors.append(msg)
        if code not in codes:
            codes.append(code)

    # 1. Unsafe wording anywhere in the mission.
    chunks = [m.title, m.story_hook, m.finale, m.achievement_name]
    for t in m.tasks:
        chunks += [t.mechanic, t.instruction, *t.objects, *t.materials]
    seen = set()
    for chunk in chunks:
        for category, matched in unsafe_matches(chunk):
            if (category, matched.lower()) in seen:
                continue
            seen.add((category, matched.lower()))
            fail("unsafe_text", f"Unsafe wording ({category}): '{matched}'. Remove it.")
            if f"unsafe:{category}" not in codes:
                codes.append(f"unsafe:{category}")

    # 2. Objects must be confirmed by the parent.
    allowed = ctx.allowed_objects()
    # Small models often list materials (paper, chalk...) under "objects".
    # That is harmless, so accept an allowed material there. Anything else
    # must still be a parent-confirmed object, and the deny-list scan above
    # has already run over these entries.
    material_names = {normalize_noun(x) for x in ALLOWED_MATERIALS}
    for i, t in enumerate(m.tasks, 1):
        for obj in t.objects:
            n = normalize_noun(obj)
            if n in allowed or n in material_names:
                continue
            fail("unconfirmed_object",
                 f"Task {i} uses '{obj}', which the parent did not confirm.")

    # 3. Scene nouns mentioned in the text must also be confirmed.
    prose = [m.title, m.story_hook, m.finale] + [t.instruction for t in m.tasks]
    for chunk in prose:
        for token in words(chunk):
            n = normalize_noun(token)
            if n in KNOWN_SCENE_NOUNS and n not in allowed:
                fail("unconfirmed_object",
                     f"The text mentions '{token}', which is not in the confirmed list.")

    # 4. Materials from the allowed list only.
    ok_materials = {normalize_noun(x) for x in ALLOWED_MATERIALS}
    for i, t in enumerate(m.tasks, 1):
        for mat in t.materials:
            if normalize_noun(mat) not in ok_materials:
                fail("bad_material", f"Task {i} uses '{mat}', which is not an allowed material.")

    # 5. Task count for the age band.
    lo, hi = AGE_RULES[ctx.age_band]["tasks"]
    if not lo <= len(m.tasks) <= hi:
        fail("bad_task_count",
             f"Use between {lo} and {hi} tasks for ages {ctx.age_band}; got {len(m.tasks)}.")

    # 6. Total time close to the requested duration.
    total = sum(t.minutes for t in m.tasks)
    delta = max(2, round(ctx.tolerance * ctx.duration_min))
    if abs(total - ctx.duration_min) > delta:
        fail("bad_duration",
             f"Task minutes add up to {total}; they should add up to about {ctx.duration_min}.")

    # 7. Reading level for the age band.
    kid_text = " ".join([m.story_hook, m.finale] + [t.instruction for t in m.tasks])
    grade = fk_grade(kid_text)
    max_grade = AGE_RULES[ctx.age_band]["max_grade"]
    if grade > max_grade:
        fail("reading_level",
             f"Reading level is too high ({grade:.1f} vs max {max_grade}). "
             "Use shorter sentences and simpler words.")

    return ValidationResult(not errors, errors, codes, m if not errors else None)
