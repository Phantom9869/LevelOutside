import copy
import json

import pytest

from leveloutside import (
    MissionContext,
    generate_with_retries,
    safe_fallback,
    validate_mission,
)
from leveloutside.safety import AGE_RULES

CTX = MissionContext(
    confirmed_objects={"tree", "stick", "stone", "bench", "leaf"},
    age_band="8-10",
    duration_min=20,
)


def good():
    return {
        "title": "Build the Stick Shelter",
        "story_hook": "Night is coming. Build a safe shelter before the timer ends.",
        "tasks": [
            {"mechanic": "gather", "instruction": "Gather five sticks of different sizes.",
             "objects": ["stick"], "materials": ["paper bag"], "minutes": 6},
            {"mechanic": "build",
             "instruction": "Lean the sticks against the bench to make a little hut.",
             "objects": ["stick", "bench"], "materials": [], "minutes": 8},
            {"mechanic": "craft", "instruction": "Draw a map of your shelter on paper.",
             "objects": [], "materials": ["paper", "pencil"], "minutes": 6},
        ],
        "finale": "Show your grown-up your shelter and map.",
        "achievement_name": "Master Builder",
    }


def with_instruction(text):
    m = good()
    m["tasks"][0]["instruction"] = text
    return m


def tasks_of(n, total=20):
    each = total // n
    return [
        {"mechanic": "observe", "instruction": "Look at the stick.", "objects": ["stick"],
         "materials": [], "minutes": each + (total - each * n if i == n - 1 else 0)}
        for i in range(n)
    ]


def test_good_mission_passes():
    r = validate_mission(good(), CTX)
    assert r.ok, r.errors
    assert r.mission is not None


def test_accepts_json_string_and_code_fence():
    s = json.dumps(good())
    assert validate_mission(s, CTX).ok
    assert validate_mission("```json\n" + s + "\n```", CTX).ok


def test_invalid_json_is_schema_error():
    r = validate_mission("not json at all", CTX)
    assert not r.ok and r.codes == ["schema"]


UNSAFE = [
    "Climb the tree and pick a leaf.",
    "Swim across the pond to find a stone.",
    "Light a small fire with matches.",
    "Use a knife to cut the sticks.",
    "Eat three berries from the bush.",
    "Walk along the street and count cars.",
    "Knock on a neighbor's door and say hello.",
    "Catch a bee in a cup.",
    "Go find sticks by yourself.",
    "Dig a deep hole near the tree.",
    "Jump off the bench onto the grass.",
    "Taste a leaf to see if it is sweet.",
    "Pick mushrooms for your shelter.",
    "Splash in the puddle.",
    "Stay outside after dark.",
    "Chase the squirrel around the tree.",
    "Hammer a nail into a stick.",
    "Climb the ladder to the roof.",
    "Talk to a stranger about your map.",
    "Cross the road to find stones.",
    "Drink water from the fountain.",
    "Find sticks without a grown-up.",
    "Touch a snake if you see one.",
    "Poke a spider with a stick.",
]


@pytest.mark.parametrize("text", UNSAFE)
def test_unsafe_wording_is_rejected(text):
    r = validate_mission(with_instruction(text), CTX)
    assert not r.ok
    assert "unsafe_text" in r.codes


SAFE = [
    "Find five sticks of different sizes.",
    "Lay the leaves in a row from smallest to biggest.",
    "Look at the tree and count three things you notice.",
    "Draw the shape of a stone on paper.",
    "Tell your grown-up what you saw.",
]


@pytest.mark.parametrize("text", SAFE)
def test_safe_wording_not_flagged(text):
    r = validate_mission(with_instruction(text), CTX)
    assert "unsafe_text" not in r.codes, r.errors


def test_unconfirmed_object_in_list():
    m = good()
    m["tasks"][0]["objects"] = ["fountain"]
    assert "unconfirmed_object" in validate_mission(m, CTX).codes


def test_unconfirmed_object_smuggled_in_text():
    m = with_instruction("Look at the fence and tell what you see.")
    assert "unconfirmed_object" in validate_mission(m, CTX).codes


def test_object_removed_from_confirmed_list():
    ctx = MissionContext({"tree", "stick"}, "8-10", 20)  # bench not confirmed
    assert "unconfirmed_object" in validate_mission(good(), ctx).codes


def test_bad_material():
    m = good()
    m["tasks"][0]["materials"] = ["scissors"]
    assert "bad_material" in validate_mission(m, CTX).codes


def test_bad_duration():
    m = good()
    for t in m["tasks"]:
        t["minutes"] = 2
    assert "bad_duration" in validate_mission(m, CTX).codes


def test_too_many_tasks_for_young_band():
    ctx = MissionContext({"stick"}, "5-7", 20)
    m = good()
    m["tasks"] = tasks_of(5)
    assert "bad_task_count" in validate_mission(m, ctx).codes


def test_reading_level_too_high_for_young_band():
    ctx = MissionContext({"leaf", "stick"}, "5-7", 20)
    m = good()
    m["tasks"] = tasks_of(3)
    m["tasks"][0]["instruction"] = (
        "Systematically investigate the differences between various leaf "
        "morphologies and photosynthetic characteristics."
    )
    assert "reading_level" in validate_mission(m, ctx).codes


def test_unknown_age_band_raises():
    with pytest.raises(ValueError):
        MissionContext({"tree"}, "99-100", 20)


def test_retry_then_success_passes_feedback():
    calls = []

    def gen(feedback):
        calls.append(list(feedback))
        return with_instruction("Climb the tree.") if len(calls) == 1 else good()

    res = generate_with_retries(gen, CTX)
    assert not res.used_fallback and res.attempts == 2
    assert calls[0] == [] and calls[1]
    assert res.failure_codes[0][0] == "unsafe_text"


def test_always_unsafe_falls_back_to_safe_mission():
    res = generate_with_retries(lambda fb: with_instruction("Climb the tree."), CTX)
    assert res.used_fallback and res.attempts == 3
    assert validate_mission(res.mission, CTX).ok


@pytest.mark.parametrize("band", list(AGE_RULES))
@pytest.mark.parametrize("duration", [10, 20, 40, 45])
@pytest.mark.parametrize("objects", [set(), {"pond", "road"}, {"tree"}, {"bench", "leaf", "stone"}])
def test_fallback_always_valid(band, duration, objects):
    ctx = MissionContext(objects, band, duration)
    fb = safe_fallback(ctx)
    r = validate_mission(fb, ctx)
    assert r.ok, r.errors
    assert "pond" not in fb.model_dump_json() and "road" not in fb.model_dump_json()
