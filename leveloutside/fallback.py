from __future__ import annotations

import math

from .safety import AGE_RULES, ALWAYS_ALLOWED_OBJECTS, unsafe_matches
from .schema import Mission, Task
from .text_utils import normalize_noun
from .validator import MissionContext


def safe_fallback(ctx: MissionContext) -> Mission:
    """A pre-written mission that always passes validation."""
    lo, hi = AGE_RULES[ctx.age_band]["tasks"]
    n = min(hi, max(lo, math.ceil(ctx.duration_min / 30)))

    pool = []
    for obj in sorted({normalize_noun(o) for o in ctx.confirmed_objects}):
        if not unsafe_matches(f"Look at the {obj}."):
            pool.append(obj)
    pool += sorted(ALWAYS_ALLOWED_OBJECTS)

    base, extra = divmod(ctx.duration_min, n)
    tasks = []
    for i in range(n):
        obj = pool[i % len(pool)]
        tasks.append(Task(
            mechanic="observe",
            instruction=f"Look at the {obj}. Tell your grown-up three things you notice.",
            objects=[obj],
            materials=[],
            minutes=base + (extra if i == n - 1 else 0),
        ))
    return Mission(
        title="Explorer look-around",
        story_hook="You are an explorer on a short mission.",
        tasks=tasks,
        finale="Tell your grown-up the best thing you saw.",
        achievement_name="Keen-Eyed Explorer",
    )
