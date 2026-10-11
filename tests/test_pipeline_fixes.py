"""Fixes found in a real gemma3:4b run: materials in objects, minute totals."""
import json

import pytest

from leveloutside import MissionContext, generate_with_retries, validate_mission
from leveloutside.pipeline import normalize_minutes

CTX = MissionContext({"tree", "stick", "stone", "bench", "leaf"}, "8-10", 20)


def mission(minutes=(6, 8, 6), objects=None, extra_tasks=None):
    tasks = [
        {"mechanic": "gather", "instruction": "Gather five sticks of different sizes.",
         "objects": ["stick"], "materials": [], "minutes": minutes[0]},
        {"mechanic": "build",
         "instruction": "Lean the sticks against the bench to make a little hut.",
         "objects": objects if objects is not None else ["stick", "bench"],
         "materials": [], "minutes": minutes[1]},
        {"mechanic": "craft", "instruction": "Draw a map of your shelter on paper.",
         "objects": [], "materials": ["paper", "pencil"], "minutes": minutes[2]},
    ]
    return {"title": "Build the Stick Shelter",
            "story_hook": "Night is coming. Build a safe shelter before the timer ends.",
            "tasks": tasks + (extra_tasks or []),
            "finale": "Show your grown-up your shelter and map.",
            "achievement_name": "Master Builder"}


# ---- materials listed under "objects" ----

def test_material_in_objects_is_accepted():
    r = validate_mission(mission(objects=["stick", "crayon", "paper"]), CTX)
    assert r.ok, r.errors


def test_unconfirmed_object_still_rejected():
    r = validate_mission(mission(objects=["stick", "fountain"]), CTX)
    assert "unconfirmed_object" in r.codes


def test_unsafe_thing_in_objects_still_rejected():
    r = validate_mission(mission(objects=["stick", "scissors"]), CTX)
    assert not r.ok and "unsafe_text" in r.codes


# ---- normalize_minutes ----

def total(m):
    return sum(t["minutes"] for t in m["tasks"])


def test_24_becomes_20():
    fixed, changed = normalize_minutes(mission(minutes=(8, 8, 8)), 20)
    assert changed and total(fixed) == 20


def test_14_becomes_20():
    fixed, changed = normalize_minutes(mission(minutes=(5, 5, 4)), 20)
    assert changed and total(fixed) == 20


def test_correct_total_unchanged():
    m = mission(minutes=(6, 8, 6))
    fixed, changed = normalize_minutes(m, 20)
    assert not changed and fixed is m


def test_bad_json_passes_through():
    raw = "this is not json"
    fixed, changed = normalize_minutes(raw, 20)
    assert not changed and fixed == raw


def test_code_fenced_json_is_handled():
    raw = "```json\n" + json.dumps(mission(minutes=(8, 8, 8))) + "\n```"
    fixed, changed = normalize_minutes(raw, 20)
    assert changed and total(fixed) == 20


def test_non_integer_minutes_left_alone():
    m = mission()
    m["tasks"][0]["minutes"] = "six"
    fixed, changed = normalize_minutes(m, 20)
    assert not changed


def test_only_minutes_change():
    m = mission(minutes=(8, 8, 8))
    fixed, _ = normalize_minutes(m, 20)
    for a, b in zip(m["tasks"], fixed["tasks"]):
        assert {k: v for k, v in a.items() if k != "minutes"} == \
               {k: v for k, v in b.items() if k != "minutes"}
    assert m["tasks"][0]["minutes"] == 8  # input not mutated


@pytest.mark.parametrize("mins", [(1, 1, 1), (30, 30, 30), (2, 40, 3), (10, 10, 10, 10, 10)])
def test_result_is_always_exactly_duration_or_untouched(mins):
    m = mission(minutes=(mins[0], mins[1], mins[2]))
    if len(mins) > 3:
        m["tasks"] += [dict(m["tasks"][0], minutes=x) for x in mins[3:]]
    fixed, changed = normalize_minutes(m, 20)
    if changed:
        assert total(fixed) == 20
        assert all(1 <= t["minutes"] <= 30 for t in fixed["tasks"])


# ---- pipeline integration ----

def test_pipeline_accepts_after_rescale_and_flags_it():
    res = generate_with_retries(lambda fb: json.dumps(mission(minutes=(8, 8, 8))), CTX)
    assert not res.used_fallback and res.attempts == 1 and res.minutes_adjusted


def test_pipeline_not_flagged_when_total_already_right():
    res = generate_with_retries(lambda fb: mission(), CTX)
    assert res.attempts == 1 and not res.minutes_adjusted


def test_observer_sees_each_attempt():
    seen = []
    bad = mission(objects=["fountain"])
    calls = iter([bad, mission()])
    res = generate_with_retries(lambda fb: next(calls), CTX,
                                observer=lambda n, r: seen.append((n, r.ok)))
    assert seen == [(1, False), (2, True)] and res.attempts == 2
