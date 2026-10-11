from leveloutside.games import get_profile, list_titles
from leveloutside.llm import _system_prompt
from leveloutside.validator import MissionContext


CONFIRMED_OBJECTS = {"tree", "stick", "stone", "bench", "leaf"}


def _ctx(age_band: str) -> MissionContext:
    return MissionContext(
        confirmed_objects=CONFIRMED_OBJECTS,
        age_band=age_band,
        duration_min=20,
    )


def test_every_game_prompt_forbids_title_in_mission_text():
    for title in list_titles():
        prompt = _system_prompt(get_profile(title), CONFIRMED_OBJECTS, _ctx("8-10"))
        assert "Never write the game's title or name in any mission field" in prompt
        assert "Use the game name" not in prompt


def test_prompt_contains_food_rule():
    prompt = _system_prompt(get_profile("Super Mario"), CONFIRMED_OBJECTS, _ctx("8-10"))
    assert "Never mention food, eating, mushrooms, berries" in prompt


def test_pokemon_prompt_does_not_contain_pocket_monsters():
    prompt = _system_prompt(get_profile("Pokemon"), CONFIRMED_OBJECTS, _ctx("8-10"))
    assert "pocket monsters" not in prompt.lower()
