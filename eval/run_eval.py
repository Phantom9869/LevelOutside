#!/usr/bin/env python
"""
Run an evaluation sweep over the game library and age bands.

Usage (from repo root):
    .venv/Scripts/python.exe eval/run_eval.py [options]

Options:
    --model MODEL        Ollama model name (default: $LEVELOUTSIDE_MODEL or gemma3:4b)
    --limit N            Run only the first N combinations (for smoke tests)
    --out DIR            Output directory (default: eval/results)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from statistics import median, quantiles
from typing import List

# Ensure the repo root is on sys.path so `leveloutside` imports work when
# running the script directly.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from leveloutside import (
    MissionContext,
    generate_with_retries,
)
from leveloutside.llm import make_generator
from leveloutside.games import (
    list_titles,
    get_profile,
)


DEFAULT_GAMES = [
    "Minecraft",
    "Pokemon",
    "Super Mario",
    "Lego Building",
    "Animal Crossing",
]
DEFAULT_OBJECTS = {"tree", "stick", "stone", "bench", "leaf"}
DEFAULT_DURATION = 20
AGE_BANDS = ["5-7", "8-10", "11-13"]


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _percentile(data: List[float], p: float) -> float:
    """Return the p-th percentile (0 <= p <= 100) using nearest-rank."""
    if not data:
        return 0.0
    k = max(1, int(round(len(data) * p / 100.0)))
    return sorted(data)[k - 1]


def run_sweep(
    model: str | None,
    limit: int | None,
    out_dir: Path,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "results.csv"

    # Prepare CSV file and write header (append-safe).
    write_header = not csv_path.exists()
    csv_file = csv_path.open("a", newline="", encoding="utf-8")
    writer = csv.writer(csv_file)
    if write_header:
        writer.writerow(
            [
                "timestamp",
                "model",
                "game",
                "age_band",
                "first_try_pass",  # bool as string
                "attempts",
                "used_fallback",  # bool as string
                "failure_codes",  # JSON list of list of str
                "failure_errors",  # JSON list of list of str
                "latency_seconds",
            ]
        )

    # Build the combination list.
    games_to_run = DEFAULT_GAMES[:]
    combinations = [
        (game, band)
        for game in games_to_run
        for band in AGE_BANDS
    ]
    if limit is not None:
        combinations = combinations[:limit]

    print(f"Running {len(combinations)} combinations…")
    start_overall = time.time()

    for idx, (game_title, age_band) in enumerate(combinations, 1):
        profile = get_profile(game_title)
        if profile is None:
            print(f"[{idx}/{len(combinations)}] SKIP: {game_title} not found in library")
            continue

        ctx = MissionContext(
            confirmed_objects=DEFAULT_OBJECTS.copy(),
            age_band=age_band,
            duration_min=DEFAULT_DURATION,
        )

        gen = make_generator(profile, DEFAULT_OBJECTS, ctx, model=model)

        attempt_errors = []

        def observer(attempt, res):
            attempt_errors.append([] if res.ok else list(res.errors))

        start = time.time()
        try:
            result = generate_with_retries(gen, ctx, observer=observer)
            latency = time.time() - start
        except Exception as exc:  # Ollama down, etc.
            latency = time.time() - start
            print(
                f"[{idx}/{len(combinations)}] ERROR: {game_title} {age_band}: {exc}"
            )
            # Still write a row so we know it was attempted.
            writer.writerow(
                [
                    _now_iso(),
                    model or os.environ.get("LEVELOUTSIDE_MODEL", "gemma3:4b"),
                    game_title,
                    age_band,
                    False,  # first_try_pass
                    0,  # attempts
                    True,  # used_fallback (fallback path)
                    json.dumps([[]]),  # failure_codes
                    json.dumps([[str(exc)]]),  # failure_errors
                    f"{latency:.2f}",
                ]
            )
            csv_file.flush()
            continue

        first_try_pass = (result.attempts == 1 and not result.used_fallback)
        writer.writerow(
            [
                _now_iso(),
                model or os.environ.get("LEVELOUTSIDE_MODEL", "gemma3:4b"),
                game_title,
                age_band,
                str(first_try_pass),
                result.attempts,
                str(result.used_fallback),
                json.dumps(result.failure_codes),
                json.dumps(attempt_errors),
                f"{latency:.2f}",
            ]
        )
        csv_file.flush()

        print(
            f"[{idx}/{len(combinations)}] {game_title} {age_band} — "
            f"attempts={result.attempts}, fallback={result.used_fallback}, "
            f"latency={latency:.1f}s"
        )

    csv_file.close()
    elapsed = time.time() - start_overall
    print(f"\nAll done in {elapsed:.1f}s — results in {csv_path}")

    # --- Summary markdown ---
    # Read back the CSV we just wrote (or the whole file if append).
    rows: List[dict] = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    if not rows:
        print("No rows to summarise.")
        return

    # Parse numeric columns.
    attempts = [int(r["attempts"]) for r in rows]
    latencies = [float(r["latency_seconds"]) for r in rows]
    first_try_pass = [r["first_try_pass"] == "True" for r in rows]
    used_fallback = [r["used_fallback"] == "True" for r in rows]

    # Flatten failure codes across all runs.
    from collections import Counter

    code_counter: Counter[str] = Counter()
    for r in rows:
        try:
            codes_per_attempt = json.loads(r["failure_codes"])
        except Exception:
            codes_per_attempt = []
        for attempt_codes in codes_per_attempt:
            for code in attempt_codes:
                code_counter[code] += 1

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_path = out_dir / f"summary_{ts}.md"
    with summary_path.open("w", encoding="utf-8") as f:
        f.write(f"# LevelOutside Evaluation Summary\n\n")
        f.write(f"- **Model**: {model or os.environ.get('LEVELOUTSIDE_MODEL', 'gemma3:4b')}\n")
        f.write(f"- **Runs**: {len(rows)}\n")
        f.write(f"- **First-try pass rate**: {sum(first_try_pass) / len(first_try_pass):.1%}\n")
        f.write(f"- **Mean attempts**: {sum(attempts) / len(attempts):.2f}\n")
        f.write(f"- **Fallback rate**: {sum(used_fallback) / len(used_fallback):.1%}\n")
        f.write(f"- **Latency p50**: {median(latencies):.1f}s\n")
        f.write(f"- **Latency p95**: {_percentile(latencies, 95):.1f}s\n")
        f.write(f"\n## Failure code counts\n\n")
        if code_counter:
            for code, count in code_counter.most_common():
                f.write(f"- {code}: {count}\n")
        else:
            f.write("(no failures)\n")

    print(f"Summary written to {summary_path}")


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Run LevelOutside evaluation sweep")
    parser.add_argument(
        "--model",
        help="Ollama model name (default: $LEVELOUTSIDE_MODEL or gemma3:4b)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Run only the first N combinations (for smoke tests)",
    )
    parser.add_argument(
        "--out",
        default="eval/results",
        help="Output directory (default: eval/results)",
    )
    args = parser.parse_args()

    run_sweep(
        model=args.model,
        limit=args.limit,
        out_dir=Path(args.out),
    )


if __name__ == "__main__":
    _cli()
