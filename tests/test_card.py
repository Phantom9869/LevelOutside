"""Tests for card.py and app.py import safety. No model, no network."""
from __future__ import annotations

import json

import pytest

from leveloutside import MissionContext, validate_mission
from leveloutside.card import render_card
from leveloutside.schema import Mission, Task


# ── Helpers ─────────────────────────────────────────────────────────────

CTX = MissionContext(
    confirmed_objects={"tree", "stick", "stone", "bench", "leaf"},
    age_band="8-10",
    duration_min=20,
)


def _good_mission() -> Mission:
    data = {
        "title": "Build the Stick Shelter",
        "story_hook": "Night is coming. Build a safe shelter before the timer ends.",
        "tasks": [
            {"mechanic": "gather",
             "instruction": "Gather five sticks of different sizes.",
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
    return Mission.model_validate(data)


# ── render_card ──────────────────────────────────────────────────────────

def test_render_card_contains_task_instructions():
    mission = _good_mission()
    html = render_card(mission, CTX, "Minecraft")
    assert "Gather five sticks of different sizes." in html
    assert "Lean the sticks against the bench to make a little hut." in html
    assert "Draw a map of your shelter on paper." in html


def test_render_card_contains_supervision_line():
    html = render_card(_good_mission(), CTX, "Minecraft")
    assert "grown-up stays with you" in html


def test_render_card_contains_achievement_name():
    html = render_card(_good_mission(), CTX, "Minecraft")
    assert "Master Builder" in html


def test_render_card_contains_game_title():
    html = render_card(_good_mission(), CTX, "Minecraft")
    assert "Minecraft" in html


def test_render_card_contains_story_hook():
    html = render_card(_good_mission(), CTX, "Minecraft")
    assert "Night is coming" in html


def test_render_card_contains_finale():
    html = render_card(_good_mission(), CTX, "Minecraft")
    assert "Show your grown-up your shelter and map." in html


def test_render_card_contains_task_minutes():
    html = render_card(_good_mission(), CTX, "Minecraft")
    assert "6 min" in html
    assert "8 min" in html


def test_render_card_contains_certificate_section():
    html = render_card(_good_mission(), CTX, "Minecraft")
    assert "Certificate" in html


def test_render_card_html_escapes_script_tag():
    """A <script> tag in a task instruction must be escaped, never injected."""
    mission = _good_mission()
    mission.tasks[0].instruction = "<script>alert(1)</script>"
    html = render_card(mission, CTX, "Minecraft")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_render_card_html_escapes_in_game_title():
    html = render_card(_good_mission(), CTX, "<b>GameTitle</b>")
    assert "<b>GameTitle</b>" not in html
    assert "&lt;b&gt;" in html


def test_render_card_html_escapes_story_hook():
    mission = _good_mission()
    mission.story_hook = '<img src=x onerror=alert(1)>'
    html = render_card(mission, CTX, "Minecraft")
    assert "<img" not in html
    assert "&lt;img" in html


def test_render_card_returns_string():
    html = render_card(_good_mission(), CTX, "Minecraft")
    assert isinstance(html, str)
    assert len(html) > 100


def test_render_card_no_name_input():
    """The template must not include a name field for the child."""
    html = render_card(_good_mission(), CTX, "Minecraft")
    assert "child's name" not in html.lower()
    assert 'name="child' not in html.lower()
    assert 'placeholder="name"' not in html.lower()


def test_render_card_no_external_resources():
    """No cdn, googleapis, or external http links in the template."""
    html = render_card(_good_mission(), CTX, "Minecraft")
    # Must not link to any external resource
    for domain in ["cdn.", "googleapis", "fontawesome", "unpkg.com", "jsdelivr"]:
        assert domain not in html, f"External resource reference found: {domain}"


def test_render_card_contains_no_name_label():
    """Double-check raw template text has no child name field."""
    from pathlib import Path
    template_text = (
        Path(__file__).parent.parent / "templates" / "card.html"
    ).read_text(encoding="utf-8")
    assert "child" not in template_text.lower() or "child's name" not in template_text.lower()
    # More direct: no input element asking for a name
    assert 'type="text"' not in template_text


# ── app.py import safety ─────────────────────────────────────────────────

def test_app_imports_without_launching_server():
    """Importing app.py must not start a Streamlit server."""
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "app",
        str(Path(__file__).parent.parent / "app.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    # If this raises or hangs, the server was launched at import time.
    spec.loader.exec_module(mod)
    # main() must exist
    assert callable(mod.main)
