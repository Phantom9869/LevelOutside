from __future__ import annotations

from .safety import DENY_PATTERNS
from .text_utils import normalize_noun


def sanitize_objects(names: list[str]) -> tuple[list[str], list[str]]:
    """Split *names* into (kept, removed).

    Each name is lowercased and normalized with normalize_noun.
    Any name whose normalized form matches the living_things deny pattern
    is placed in *removed*; the rest go into *kept*.
    The pattern is also checked against a short phrase ("look at the <name>")
    so that multi-word names embedded in prose are caught correctly.
    """
    living = DENY_PATTERNS["living_things"]

    kept: list[str] = []
    removed: list[str] = []

    for raw in names:
        normalized = normalize_noun(raw)
        probe = f"look at the {normalized}"
        if living.search(normalized) or living.search(probe):
            removed.append(normalized)
        else:
            kept.append(normalized)

    return kept, removed
