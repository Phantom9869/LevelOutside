"""Replay of three real gemma3:4b outputs (Minecraft, ages 8-10, 20 minutes).

These are raw model outputs from a real run on 11 Oct 2026. Before the fixes,
all three attempts failed and the safe fallback was used. They contain no
child data. A sanitized fixture is used for pass-shape coverage.
"""
from pathlib import Path

from leveloutside import MissionContext, validate_mission
from leveloutside.pipeline import normalize_minutes

FIX = Path(__file__).parent / "fixtures"
CTX = MissionContext({"tree", "stick", "stone", "bench", "leaf"}, "8-10", 20)


def load(n):
    return (FIX / f"gemma3_4b_attempt{n}.json").read_text(encoding="utf-8")


def load_named(name: str):
    return (FIX / name).read_text(encoding="utf-8")


def test_sanitized_real_style_sample_passes():
    r = validate_mission(load_named("gemma3_4b_attempt2_sanitized.json"), CTX)
    assert r.ok


def test_attempt2_rejected_for_unsafe_text():
    r = validate_mission(load(2), CTX)
    assert not r.ok and "unsafe_text" in r.codes


def test_attempt3_rejected_for_unsafe_text():
    raw, _ = normalize_minutes(load(3), 20)
    r = validate_mission(raw, CTX)
    assert not r.ok and "unsafe_text" in r.codes
