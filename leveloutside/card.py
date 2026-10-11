from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .schema import Mission
from .validator import MissionContext

_TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


def render_card(mission: Mission, ctx: MissionContext, game_title: str) -> str:
    """Render a printable HTML mission card.

    Jinja2 autoescape is ON — all variables are HTML-escaped.
    """
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("card.html")
    return template.render(
        mission=mission,
        ctx=ctx,
        game_title=game_title,
    )
