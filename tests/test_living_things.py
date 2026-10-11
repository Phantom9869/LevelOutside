"""Tests for hard rule 3: no living things in missions or confirmed objects."""
from __future__ import annotations

import pytest

from leveloutside import MissionContext, safe_fallback, validate_mission
from leveloutside.scene import sanitize_objects


# ── Helpers ─────────────────────────────────────────────────────────────

CTX = MissionContext(
    confirmed_objects={"tree", "stick", "stone", "bench", "leaf"},
    age_band="8-10",
    duration_min=20,
)


def _mission_with_instruction(text: str) -> dict:
    return {
        "title": "Build the Stick Shelter",
        "story_hook": "Night is coming. Build a safe shelter before the timer ends.",
        "tasks": [
            {"mechanic": "gather",
             "instruction": text,
             "objects": ["stick"], "materials": ["paper bag"], "minutes": 6},
            {"mechanic": "build",
             "instruction": "Lean the sticks against the bench to make a little hut.",
             "objects": ["stick", "bench"], "materials": [], "minutes": 8},
            {"mechanic": "craft",
             "instruction": "Draw a map of your shelter on paper.",
             "objects": [], "materials": ["paper", "pencil"], "minutes": 6},
        ],
        "finale": "Show your grown-up your shelter and map.",
        "achievement_name": "Master Builder",
    }


# ── living_things deny category in mission text ──────────────────────────

LIVING_THING_PHRASES = [
    ("dog",       "Pet the dog on the grass."),
    ("dogs",      "Watch out for dogs near the bench."),
    ("cat",       "The cat is sitting on the bench."),
    ("cats",      "Count the cats near the tree."),
    ("bird",      "Look at the bird on the branch."),
    ("birds",     "Listen to the birds singing."),
    ("animal",    "Find a friendly animal near the tree."),
    ("animals",   "Name three animals you see."),
    ("pet",       "Stroke a pet if you find one."),
    ("pets",      "Take a photo of the pets."),
    ("person",    "Ask a person for help."),
    ("people",    "Watch the people in the park."),
    ("stranger",  "Follow a stranger to the gate."),
    ("strangers", "Do not talk to strangers here."),
    ("insect",    "Catch an insect in a cup."),
    ("insects",   "Count the insects on the leaf."),
    ("bug",       "Look at a bug under the stone."),
    ("bugs",      "Collect bugs from the ground."),
    ("squirrel",  "Chase the squirrel to the tree."),
    ("squirrels", "Watch the squirrels play near the bench."),
]


@pytest.mark.parametrize("word,phrase", LIVING_THING_PHRASES)
def test_living_thing_in_text_rejected(word, phrase):
    r = validate_mission(_mission_with_instruction(phrase), CTX)
    assert not r.ok, f"Expected rejection for: {phrase!r}"
    assert "unsafe_text" in r.codes, f"Expected unsafe_text code for: {phrase!r}"


# ── sanitize_objects ─────────────────────────────────────────────────────

def test_sanitize_drops_dog():
    kept, removed = sanitize_objects(["tree", "dog", "leaf"])
    assert "dog" in removed
    assert "tree" in kept
    assert "leaf" in kept


def test_sanitize_drops_bird():
    kept, removed = sanitize_objects(["bench", "bird", "stone"])
    assert "bird" in removed
    assert "bench" in kept
    assert "stone" in kept


def test_sanitize_drops_people():
    kept, removed = sanitize_objects(["stick", "people", "grass"])
    assert "people" in removed
    assert "stick" in kept


def test_sanitize_keeps_inanimate_only():
    names = ["tree", "bench", "fence", "wall", "grass"]
    kept, removed = sanitize_objects(names)
    assert set(kept) == {"tree", "bench", "fence", "wall", "grass"}
    assert removed == []


def test_sanitize_drops_all_living_words():
    living = ["dog", "cat", "bird", "animal", "pet",
              "person", "people", "stranger", "insect", "bug", "squirrel"]
    kept, removed = sanitize_objects(living)
    assert kept == []
    assert set(removed) == set(living)


def test_sanitize_normalizes_case():
    kept, removed = sanitize_objects(["Dog", "BIRD", "Tree"])
    assert "dog" in removed
    assert "bird" in removed
    assert "tree" in kept


def test_sanitize_normalizes_plurals():
    # "dogs" normalized -> "dog", should still be removed
    kept, removed = sanitize_objects(["dogs", "cats", "sticks"])
    assert "dog" in removed
    assert "cat" in removed
    assert "stick" in kept


def test_sanitize_empty_list():
    kept, removed = sanitize_objects([])
    assert kept == []
    assert removed == []


# ── safe_fallback skips living things from confirmed_objects ─────────────

def test_fallback_skips_dog_in_confirmed():
    ctx = MissionContext({"tree", "dog"}, "8-10", 20)
    fb = safe_fallback(ctx)
    dump = fb.model_dump_json()
    assert "dog" not in dump


def test_fallback_skips_bird_in_confirmed():
    ctx = MissionContext({"stick", "bird", "leaf"}, "8-10", 20)
    fb = safe_fallback(ctx)
    dump = fb.model_dump_json()
    assert "bird" not in dump


def test_fallback_skips_cat_in_confirmed():
    ctx = MissionContext({"bench", "cat"}, "8-10", 20)
    fb = safe_fallback(ctx)
    dump = fb.model_dump_json()
    assert "cat" not in dump


def test_fallback_with_only_living_things_confirmed():
    # No safe objects at all — fallback must still use ALWAYS_ALLOWED_OBJECTS (ground, sky)
    ctx = MissionContext({"dog", "cat", "bird"}, "8-10", 20)
    fb = safe_fallback(ctx)
    dump = fb.model_dump_json()
    assert "dog" not in dump
    assert "cat" not in dump
    assert "bird" not in dump
    # Mission must still be valid
    from leveloutside import validate_mission
    r = validate_mission(fb, ctx)
    assert r.ok, r.errors


def test_fallback_valid_with_mixed_confirmed():
    ctx = MissionContext({"tree", "dog", "bench", "bird"}, "8-10", 20)
    fb = safe_fallback(ctx)
    r = validate_mission(fb, ctx)
    assert r.ok, r.errors
    dump = fb.model_dump_json()
    assert "dog" not in dump
    assert "bird" not in dump
