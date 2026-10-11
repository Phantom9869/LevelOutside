from __future__ import annotations

import re

_IRREGULAR = {"leaves": "leaf", "feet": "foot", "mice": "mouse"}


def normalize_noun(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"^(a|an|the|some)\s+", "", s)
    if s in _IRREGULAR:
        return _IRREGULAR[s]
    if len(s) > 3 and s.endswith("ies"):
        return s[:-3] + "y"
    if len(s) > 3 and s.endswith("s") and not s.endswith("ss"):
        return s[:-1]
    return s


def words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z']+", text)


def sentences(text: str) -> list[str]:
    return [p for p in re.split(r"[.!?]+", text) if p.strip()]


def count_syllables(word: str) -> int:
    word = re.sub(r"[^a-z]", "", word.lower())
    if not word:
        return 0
    n = len(re.findall(r"[aeiouy]+", word))
    if word.endswith("e") and not word.endswith(("le", "ee")) and n > 1:
        n -= 1
    return max(1, n)


def fk_grade(text: str) -> float:
    """Flesch-Kincaid grade level (heuristic syllable count)."""
    w = words(text)
    s = sentences(text)
    if not w or not s:
        return 0.0
    syl = sum(count_syllables(x) for x in w)
    return 0.39 * len(w) / len(s) + 11.8 * syl / len(w) - 15.59
