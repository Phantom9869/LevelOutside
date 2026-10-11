import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = (ROOT / "templates" / "card.html").read_text(encoding="utf-8")
GAMES = json.loads((ROOT / "data" / "games.json").read_text(encoding="utf-8"))


def test_card_template_has_draw_box_and_no_inputs():
    assert "Draw your own game hero here" in TEMPLATE
    assert "<input" not in TEMPLATE.lower()


def test_card_template_has_print_reset():
    assert "@media print" in TEMPLATE


def test_no_person_or_animal_home_words_in_vocabulary():
    banned = {"trainer", "habitat", "hero", "villain", "wizard"}
    for entry in GAMES:
        assert not (set(w.lower() for w in entry["vocabulary"]) & banned), entry["title"]
