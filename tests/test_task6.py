from __future__ import annotations

import pytest

from leveloutside import MissionContext, validate_mission
from leveloutside.games import get_profile
from leveloutside.llm import _system_prompt


CTX = MissionContext(
    confirmed_objects={"tree", "stick", "stone", "bench", "leaf"},
    age_band="8-10",
    duration_min=20,
)

PROFILE = {
    "title": "Minecraft",
    "goal": "Survive and build",
    "verbs": ["gather", "build", "craft"],
    "vocabulary": ["block", "biome"],
}

NEW_LIVING_THING_WORDS = [
    "mob",
    "mobs",
    "monster",
    "monsters",
    "zombie",
    "zombies",
    "creeper",
    "creepers",
    "skeleton",
    "skeletons",
    "enemy",
    "enemies",
]


def _mission_with_instruction(text: str) -> dict:
    return {
        "title": "Build the Stick Shelter",
        "story_hook": "Night is coming. Build a safe shelter before the timer ends.",
        "tasks": [
            {
                "mechanic": "gather",
                "instruction": text,
                "objects": ["stick"],
                "materials": ["paper bag"],
                "minutes": 6,
            },
            {
                "mechanic": "build",
                "instruction": "Lean the sticks against the bench to make a little hut.",
                "objects": ["stick", "bench"],
                "materials": [],
                "minutes": 8,
            },
            {
                "mechanic": "craft",
                "instruction": "Draw a map of your shelter on paper.",
                "objects": [],
                "materials": ["paper", "pencil"],
                "minutes": 6,
            },
        ],
        "finale": "Show your grown-up your shelter and map.",
        "achievement_name": "Master Builder",
    }


@pytest.mark.parametrize("word", NEW_LIVING_THING_WORDS)
def test_new_creature_words_in_text_rejected(word):
    r = validate_mission(_mission_with_instruction(f"Find the {word} near the bench."), CTX)
    assert not r.ok
    assert "unsafe_text" in r.codes


def test_get_profile_alias_pocket_monsters_still_resolves():
    profile = get_profile("pocket monsters")
    assert profile is not None
    assert profile["title"] == "Pokemon"


def test_prompt_contains_three_new_rules():
    prompt = _system_prompt(PROFILE, CTX.confirmed_objects, CTX)
    assert "fallen or lying on the ground" in prompt
    assert "fallen leaves" in prompt
    assert "sticks from the ground" in prompt
    assert "pick anything off living plants" in prompt
    assert "Name no scene objects outside the confirmed list." in prompt
    assert "Never mention monsters, mobs, creatures, enemies, or any living thing" in prompt


def test_pokemon_prompt_does_not_contain_pocket_monsters():
    pokemon = get_profile("Pokemon")
    assert pokemon is not None
    prompt = _system_prompt(pokemon, CTX.confirmed_objects, CTX)
    assert "pocket monsters" not in prompt.lower()
