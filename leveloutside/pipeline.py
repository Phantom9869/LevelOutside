from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable

from .fallback import safe_fallback
from .schema import Mission
from .validator import MissionContext, ValidationResult, validate_mission


@dataclass
class PipelineResult:
    mission: Mission
    used_fallback: bool
    attempts: int
    # Codes only (never mission text), safe to send to tracing.
    failure_codes: list[list[str]] = field(default_factory=list)
    # True when the accepted mission only passed after minutes were rescaled.
    minutes_adjusted: bool = False


def _load_json_object(raw) -> dict | None:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
        try:
            data = json.loads(s)
        except (json.JSONDecodeError, ValueError):
            return None
        return data if isinstance(data, dict) else None
    return None


def normalize_minutes(raw, duration: int):
    """Rescale task minutes so they total exactly `duration`.

    Small models are unreliable at arithmetic, so code does the sum. Only the
    integer `minutes` of each task changes. Returns (raw_or_fixed_dict, changed).
    Anything unparseable or impossible is returned untouched for the validator.
    """
    data = _load_json_object(raw)
    if data is None:
        return raw, False
    tasks = data.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        return raw, False
    mins = []
    for t in tasks:
        if not isinstance(t, dict):
            return raw, False
        m = t.get("minutes")
        if isinstance(m, bool) or not isinstance(m, int):
            return raw, False
        mins.append(m)
    total = sum(mins)
    n = len(mins)
    if total <= 0 or total == duration or duration < n or duration > 30 * n:
        return raw, False

    new = [min(30, max(1, round(m * duration / total))) for m in mins]
    diff = duration - sum(new)
    order = sorted(range(n), key=lambda i: -mins[i])
    for _ in range(1000):
        if diff == 0:
            break
        progressed = False
        for i in order:
            if diff > 0 and new[i] < 30:
                new[i] += 1
                diff -= 1
                progressed = True
            elif diff < 0 and new[i] > 1:
                new[i] -= 1
                diff += 1
                progressed = True
            if diff == 0:
                break
        if not progressed:
            return raw, False
    if diff != 0:
        return raw, False

    fixed = dict(data)
    fixed["tasks"] = [dict(t, minutes=m) for t, m in zip(tasks, new)]
    return fixed, True


def generate_with_retries(
    generate: Callable[[list[str]], object],
    ctx: MissionContext,
    max_tries: int = 3,
    observer: Callable[[int, ValidationResult], None] | None = None,
) -> PipelineResult:
    """Call `generate(feedback)` until a mission validates, else use the fallback."""
    feedback: list[str] = []
    failures: list[list[str]] = []
    for attempt in range(1, max_tries + 1):
        raw = generate(feedback)
        raw, adjusted = normalize_minutes(raw, ctx.duration_min)
        result = validate_mission(raw, ctx)
        if observer is not None:
            observer(attempt, result)
        if result.ok:
            return PipelineResult(result.mission, False, attempt, failures, adjusted)
        failures.append(result.codes)
        feedback = result.errors
    return PipelineResult(safe_fallback(ctx), True, max_tries, failures, False)
