from __future__ import annotations

import difflib
import json
import re
import unicodedata
from pathlib import Path

from .safety import unsafe_matches

_DATA_FILE = Path(__file__).parent.parent / "data" / "games.json"

# Loaded once at import time.
_LIBRARY: list[dict] = json.loads(_DATA_FILE.read_text(encoding="utf-8"))

# Allowed verbs (must stay in sync with the task brief).
ALLOWED_VERBS: frozenset[str] = frozenset(
    ["gather", "build", "explore", "collect", "craft", "find", "observe", "race"]
)


def _normalise(s: str) -> str:
    """Lowercase, strip accents, collapse punctuation/whitespace to a single space."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")  # strip combining marks
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return s.strip()


def _candidates(entry: dict) -> list[str]:
    """Return normalised forms for the title and all aliases."""
    return [_normalise(entry["title"])] + [_normalise(a) for a in entry.get("aliases", [])]


def list_titles() -> list[str]:
    """Return the canonical title for every entry in the library."""
    return [entry["title"] for entry in _LIBRARY]


def get_profile(title: str) -> dict | None:
    """Return the profile dict for *title*, or None if not found.

    Matching is case-insensitive, punctuation-stripped, and covers both
    the canonical title and all aliases.  If no exact normalised match is
    found, difflib fuzzy matching (cutoff 0.8) is tried across all
    normalised candidate strings.
    """
    needle = _normalise(title)

    # 1. Exact normalised match against title or any alias.
    for entry in _LIBRARY:
        if needle in _candidates(entry):
            return entry

    # 2. Fuzzy match across every candidate string.
    all_candidates: list[tuple[str, dict]] = []
    for entry in _LIBRARY:
        for cand in _candidates(entry):
            all_candidates.append((cand, entry))

    candidate_strings = [c for c, _ in all_candidates]
    matches = difflib.get_close_matches(needle, candidate_strings, n=1, cutoff=0.8)
    if matches:
        matched_str = matches[0]
        for cand, entry in all_candidates:
            if cand == matched_str:
                return entry

    return None


def profile_from_description(text: str) -> dict:
    """Build a generic profile from a free-text game description.

    Raises ValueError if the text hits any safety deny-list category.
    Returns a profile with:
      title       = "your game"
      goal        = text stripped to 200 characters
      verbs       = ["explore", "find", "collect"]
      vocabulary  = []
    """
    hits = unsafe_matches(text)
    if hits:
        categories = sorted({cat for cat, _ in hits})
        raise ValueError(
            f"Game description contains unsafe content "
            f"({', '.join(categories)}): please rephrase."
        )

    return {
        "title": "your game",
        "goal": text.strip()[:200],
        "verbs": ["explore", "find", "collect"],
        "vocabulary": [],
    }
