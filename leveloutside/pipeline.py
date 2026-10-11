from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .fallback import safe_fallback
from .schema import Mission
from .validator import MissionContext, validate_mission


@dataclass
class PipelineResult:
    mission: Mission
    used_fallback: bool
    attempts: int
    # Codes only (never mission text), safe to send to tracing.
    failure_codes: list[list[str]] = field(default_factory=list)


def generate_with_retries(
    generate: Callable[[list[str]], object],
    ctx: MissionContext,
    max_tries: int = 3,
) -> PipelineResult:
    """Call `generate(feedback)` until a mission validates, else use the fallback."""
    feedback: list[str] = []
    failures: list[list[str]] = []
    for attempt in range(1, max_tries + 1):
        result = validate_mission(generate(feedback), ctx)
        if result.ok:
            return PipelineResult(result.mission, False, attempt, failures)
        failures.append(result.codes)
        feedback = result.errors
    return PipelineResult(safe_fallback(ctx), True, max_tries, failures)
