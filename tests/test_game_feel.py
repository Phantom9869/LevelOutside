from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from leveloutside.card import render_card
from leveloutside.llm import make_generator
from leveloutside.schema import Mission
from leveloutside.validator import MissionContext



def _ctx(age_band: str = "8-10") -> MissionContext:
    return MissionContext(
        confirmed_objects={"tree", "stick", "stone", "bench", "leaf"},
        age_band=age_band,
        duration_min=20,
    )


def _mission() -> Mission:
    return Mission.model_validate(
        {
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
    )


def test_prompt_excludes_aliases_and_extra_profile_fields():
    profile = {
        "title": "Pokemon",
        "goal": "Explore the world",
        "verbs": ["explore", "find", "collect"],
        "vocabulary": ["badge", "map", "trail"],
        "aliases": ["FORBIDDEN_ALIAS_TOKEN"],
        "notes": "FORBIDDEN_EXTRA_TOKEN",
    }
    with patch("leveloutside.llm.httpx.Client") as mock_client:
        client = mock_client.return_value.__enter__.return_value
        client.post.return_value.json.return_value = {"message": {"content": "{}"}}
        client.post.return_value.raise_for_status.return_value = None
        gen = make_generator(profile, _ctx().confirmed_objects, _ctx())
        gen([])

        system = client.post.call_args[1]["json"]["messages"][0]["content"]
        assert "FORBIDDEN_ALIAS_TOKEN" not in system
        assert "FORBIDDEN_EXTRA_TOKEN" not in system


def test_rendered_card_has_draw_label_and_no_name_input():
    html = render_card(_mission(), _ctx(), "Minecraft")
    assert "Draw your own game hero here" in html
    assert "child's name" not in html.lower()
    assert 'name="child' not in html.lower()
    assert 'type="text"' not in html.lower()
