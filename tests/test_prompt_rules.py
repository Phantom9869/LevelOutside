from leveloutside.games import get_profile
from leveloutside.llm import _system_prompt
from leveloutside.validator import MissionContext


CONFIRMED_OBJECTS = {"tree", "stick", "stone", "bench", "leaf"}


def _ctx(age_band: str) -> MissionContext:
    return MissionContext(
        confirmed_objects=CONFIRMED_OBJECTS,
        age_band=age_band,
        duration_min=20,
    )


def test_prompt_forbids_building_words():
    profile = get_profile("Minecraft")
    prompt = _system_prompt(profile, CONFIRMED_OBJECTS, _ctx("8-10"))
    assert 'Never write the words "building" or "buildings"; use "build" or "make" instead.' in prompt


def test_lego_prompt_calls_the_game_lego():
    profile = get_profile("Lego Building")
    prompt = _system_prompt(profile, CONFIRMED_OBJECTS, _ctx("8-10"))
    assert 'Use the game name "Lego" in mission text.' in prompt


def test_5_7_prompt_has_six_word_rule_only_for_5_7_band():
    prompt_5_7 = _system_prompt(get_profile("Minecraft"), CONFIRMED_OBJECTS, _ctx("5-7"))
    prompt_8_10 = _system_prompt(get_profile("Minecraft"), CONFIRMED_OBJECTS, _ctx("8-10"))
    prompt_11_13 = _system_prompt(get_profile("Minecraft"), CONFIRMED_OBJECTS, _ctx("11-13"))

    six_word_rule = "sentences of at most 6 words"
    assert six_word_rule in prompt_5_7
    assert six_word_rule not in prompt_8_10
    assert six_word_rule not in prompt_11_13


def test_pokemon_prompt_does_not_include_pocket_monsters():
    profile = get_profile("pocket monsters")
    prompt = _system_prompt(profile, CONFIRMED_OBJECTS, _ctx("8-10"))
    assert "pocket monsters" not in prompt.lower()
