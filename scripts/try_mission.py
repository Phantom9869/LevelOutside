#!/usr/bin/env python
"""
Run a real Ollama-backed mission generation and print a summary.

Usage (from repo root):
    python scripts/try_mission.py
    python scripts/try_mission.py --verbose
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add repo root to sys.path so `leveloutside` is importable without install.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from leveloutside import MissionContext, generate_with_retries
from leveloutside.llm import make_generator

PROFILE = {
    "title": "Minecraft",
    "goal": "Survive the night by gathering resources and building a shelter",
    "verbs": ["gather", "build", "explore", "collect", "craft", "find", "observe", "race"],
    "vocabulary": ["block", "biome", "resource", "shelter", "mob", "craft", "inventory"],
}

CTX = MissionContext(
    confirmed_objects={"tree", "stick", "stone", "bench", "leaf"},
    age_band="8-10",
    duration_min=20,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Try a LevelOutside mission generation")
    parser.add_argument("--verbose", action="store_true",
                        help="Also print the model's raw text for every attempt")
    args = parser.parse_args()

    raw_outputs: list[str] = []
    original_generate: list = []

    gen = make_generator(PROFILE, CTX.confirmed_objects, CTX)

    # Wrap the generator to capture raw outputs when --verbose
    def tracked_generate(feedback: list[str]) -> str:
        out = gen(feedback)
        raw_outputs.append(out)
        return out

    print("Calling Ollama (this may take up to 5 minutes on first run)…")
    try:
        result = generate_with_retries(tracked_generate, CTX)
    except RuntimeError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print()
    print("=" * 60)
    print("MISSION JSON")
    print("=" * 60)
    print(json.dumps(result.mission.model_dump(), indent=2))

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Attempts:      {result.attempts}")
    print(f"Used fallback: {result.used_fallback}")
    if result.failure_codes:
        for i, codes in enumerate(result.failure_codes, 1):
            print(f"Attempt {i} failure codes: {codes}")
    else:
        print("Failure codes: (none — passed on first attempt)")

    if args.verbose:
        print()
        print("=" * 60)
        print("RAW MODEL OUTPUT(S)")
        print("=" * 60)
        for i, raw in enumerate(raw_outputs, 1):
            print(f"--- Attempt {i} ---")
            print(raw)


if __name__ == "__main__":
    main()
