"""Tests for the game library and profile lookup."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from leveloutside.games import (
    ALLOWED_VERBS,
    get_profile,
    list_titles,
    profile_from_description,
)
from leveloutside.safety import unsafe_matches


DATA_FILE = Path(__file__).parent.parent / "data" / "games.json"


# ── Library integrity ────────────────────────────────────────────────────

def _load_library() -> list[dict]:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


@pytest.mark.parametrize("entry", _load_library(), ids=lambda e: e["title"])
def test_verbs_are_from_allowed_set(entry):
    bad = set(entry["verbs"]) - ALLOWED_VERBS
    assert not bad, f"{entry['title']} has illegal verbs: {bad}"


@pytest.mark.parametrize("entry", _load_library(), ids=lambda e: e["title"])
def test_verb_count(entry):
    assert 3 <= len(entry["verbs"]) <= 5, (
        f"{entry['title']} has {len(entry['verbs'])} verbs, expected 3-5"
    )


@pytest.mark.parametrize("entry", _load_library(), ids=lambda e: e["title"])
def test_vocabulary_count(entry):
    assert 5 <= len(entry["vocabulary"]) <= 8, (
        f"{entry['title']} has {len(entry['vocabulary'])} vocabulary words, expected 5-8"
    )


@pytest.mark.parametrize("entry", _load_library(), ids=lambda e: e["title"])
def test_goal_no_deny_hits(entry):
    hits = unsafe_matches(entry["goal"])
    assert not hits, f"{entry['title']} goal has deny-list hits: {hits}"


@pytest.mark.parametrize("entry", _load_library(), ids=lambda e: e["title"])
def test_vocabulary_no_deny_hits(entry):
    for word in entry["vocabulary"]:
        hits = unsafe_matches(word)
        assert not hits, f"{entry['title']} vocab '{word}' has deny-list hits: {hits}"


# ── Lookup by title and alias ────────────────────────────────────────────

def test_list_titles_has_ten():
    titles = list_titles()
    assert len(titles) == 10


def test_lookup_exact_title():
    p = get_profile("Minecraft")
    assert p is not None and p["title"] == "Minecraft"


def test_lookup_case_insensitive():
    p = get_profile("minecraft")
    assert p is not None and p["title"] == "Minecraft"


def test_lookup_by_alias():
    p = get_profile("pokémon")
    assert p is not None and p["title"] == "Pokemon"


def test_lookup_alias_roblox():
    p = get_profile("roblox obby")
    assert p is not None and p["title"] == "Roblox Obstacle Courses"


def test_lookup_alias_lego():
    p = get_profile("legos")
    assert p is not None and p["title"] == "Lego Building"


def test_lookup_alias_sonic():
    p = get_profile("sonic the hedgehog")
    assert p is not None and p["title"] == "Sonic"


def test_lookup_typo_fuzzy():
    p = get_profile("Minceraft")  # common typo
    assert p is not None and p["title"] == "Minecraft"


def test_lookup_typo_kirby():
    p = get_profile("Krby")  # close enough at 0.8 cutoff
    assert p is not None and p["title"] == "Kirby"


def test_unknown_returns_none():
    assert get_profile("Fortnite Battle Royale") is None


def test_unknown_short_returns_none():
    assert get_profile("xyz") is None


# ── profile_from_description ────────────────────────────────────────────

def test_description_returns_profile():
    p = profile_from_description("Find hidden treasures in a magical world")
    assert p["title"] == "your game"
    assert p["verbs"] == ["explore", "find", "collect"]
    assert p["vocabulary"] == []
    assert len(p["goal"]) <= 200


def test_description_truncates_long_text():
    long = "a" * 300
    p = profile_from_description(long)
    assert len(p["goal"]) == 200


def test_description_rejects_unsafe():
    with pytest.raises(ValueError, match="unsafe"):
        profile_from_description("Climb up the tree and catch a bird")


def test_description_rejects_violence():
    with pytest.raises(ValueError, match="unsafe"):
        profile_from_description("Use a knife to cut things in the forest")


def test_description_rejects_living_things():
    with pytest.raises(ValueError, match="unsafe"):
        profile_from_description("Play with the dog in the garden")
