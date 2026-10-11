from __future__ import annotations

import re

ALLOWED_MATERIALS = {
    "pencil", "paper", "crayon", "chalk", "string", "ruler",
    "cup", "bucket", "paper bag", "cardboard",
}

# Objects that never need parent confirmation.
ALWAYS_ALLOWED_OBJECTS = {"ground", "sky"}

# Scene nouns we watch for. If the text mentions one the parent did not
# confirm, the mission is rejected (stops the model inventing objects).
KNOWN_SCENE_NOUNS = {
    "tree", "bench", "fence", "wall", "puddle", "slide", "swing", "rock",
    "stone", "stick", "leaf", "grass", "flower", "bush", "sand", "path",
    "gate", "building", "car", "hill", "playground", "statue", "fountain",
    "bin", "lamp", "cloud", "shadow", "pebble", "log", "soil", "mud",
}

# Conservative heuristics. Tune per age band if you wish.
AGE_RULES = {
    "5-7": {"tasks": (2, 4), "max_grade": 3.0},
    "8-10": {"tasks": (3, 5), "max_grade": 5.0},
    "11-13": {"tasks": (3, 6), "max_grade": 7.0},
}

_ANIMALS = (
    r"animals?|birds?|snakes?|bugs?|insects?|spiders?|bees?|wasps?|dogs?|"
    r"cats?|frogs?|lizards?|squirrels?|wild"
)

_RAW_DENY = {
    "heights": (
        r"\b(climb\w*|ladder|cliff|scal(e|ing) (the|a)|jump(ing)? (off|from|down)|"
        r"(on|onto|up) (the |a )?roof|balance on)\b"
    ),
    "water": (
        r"\b(swim\w*|wade|wading|dive|diving|river|lake|pool|pond|stream|ocean|"
        r"sea|splash\w*|drown\w*|paddl\w*|water)\b"
    ),
    "fire": r"\b(fire|flames?|matches|match|lighter|campfire|burn\w*|smok\w*)\b",
    "sharp_tools": (
        r"\b(knife|knives|blade|axe|hatchet|hammer|nails?|sharp|scissors|machete|"
        r"chain ?saw|hack ?saw|(use|with) (a |the )?saw)\b"
    ),
    "eating": (
        r"\b(eat\w*|taste|tasting|lick\w*|chew\w*|swallow\w*|berr(y|ies)|"
        r"mushrooms?|forag\w*|drink\w*)\b"
    ),
    "traffic": (
        r"\b(road|roads|street|streets|traffic|highway|driveway|parking lot|"
        r"cross(ing)? the)\b"
    ),
    "strangers": (
        r"\b(strangers?|knock on|ring the bell|someone'?s (house|yard|garden)|"
        r"neighbo(u)?r'?s|private (property|land))\b"
    ),
    "animals": (
        r"\b(touch|catch|chase|pick up|grab|feed|pet|poke|squish|hold)\b"
        r"[^.!?]{0,40}\b(" + _ANIMALS + r")\b"
    ),
    "alone": (
        r"\b(alone|by yourself|on your own|"
        r"without (a )?(grown-?up|adult|parent))\b"
    ),
    "dark_or_lost": r"\b(after dark|at night|in the dark|hide (from|where)|get lost)\b",
    "digging": r"\b(dig\w*|tunnel\w*)\b",
    "living_things": (
        r"\b(dogs?|cats?|birds?|animals?|pets?|people|persons?|strangers?|"
        r"insects?|bugs?|squirrels?)\b"
    ),
}

DENY_PATTERNS = {k: re.compile(v, re.I) for k, v in _RAW_DENY.items()}


def unsafe_matches(text: str) -> list[tuple[str, str]]:
    """Return (category, matched_text) for every deny-list hit."""
    hits = []
    for category, pattern in DENY_PATTERNS.items():
        for m in pattern.finditer(text):
            hits.append((category, m.group(0)))
    return hits
