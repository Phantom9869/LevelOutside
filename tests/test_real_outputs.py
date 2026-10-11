"""Replay of three real gemma3:4b outputs (Minecraft, ages 8-10, 20 minutes).

These are raw model outputs from a real run on 11 Oct 2026. Before the fixes,
all three attempts failed and the safe fallback was used. They contain no
child data. Attempt 3 must keep failing: it builds a 'wall', which the parent
did not confirm.
"""
from pathlib import Path

from leveloutside import MissionContext, validate_mission
from leveloutside.pipeline import normalize_minutes

FIX = Path(__file__).parent / "fixtures"
CTX = MissionContext({"tree", "stick", "stone", "bench", "leaf"}, "8-10", 20)


def load(n):
    return (FIX / f"gemma3_4b_attempt{n}.json").read_text(encoding="utf-8")


def test_attempt1_passes_after_minutes_rescaled():
    raw, changed = normalize_minutes(load(1), 20)
    assert changed
    assert validate_mission(raw, CTX).ok


def test_attempt2_passes_with_materials_in_objects():
    assert validate_mission(load(2), CTX).ok


def test_attempt3_still_rejected_for_unconfirmed_wall():
    raw, _ = normalize_minutes(load(3), 20)
    r = validate_mission(raw, CTX)
    assert not r.ok and "unconfirmed_object" in r.codes
    assert any("wall" in e for e in r.errors)
