"""Pure helpers for the evaluation script: CSV rows and summary statistics.

Nothing here talks to a model or the network, so it can be unit tested.
Every number in a summary is computed from recorded rows, never typed by hand.
"""
from __future__ import annotations

import csv
import json
import math
from collections import Counter
from pathlib import Path

FIELDS = [
    "timestamp", "model", "game", "age_band", "first_try_pass", "attempts",
    "used_fallback", "minutes_adjusted", "failure_codes_json",
    "validator_errors_json", "latency_s",
]


def append_row(path: str | Path, row: dict) -> None:
    """Append one row, writing the header first if the file is new."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in FIELDS})
        f.flush()


def _as_bool(v) -> bool:
    return v is True or str(v).strip().lower() == "true"


def load_rows(path: str | Path) -> list[dict]:
    """Read a results CSV back into typed rows."""
    rows = []
    with Path(path).open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append({
                "timestamp": r["timestamp"],
                "model": r["model"],
                "game": r["game"],
                "age_band": r["age_band"],
                "first_try_pass": _as_bool(r["first_try_pass"]),
                "attempts": int(r["attempts"]),
                "used_fallback": _as_bool(r["used_fallback"]),
                "minutes_adjusted": _as_bool(r["minutes_adjusted"]),
                "failure_codes": json.loads(r["failure_codes_json"] or "[]"),
                "validator_errors": json.loads(r["validator_errors_json"] or "[]"),
                "latency_s": float(r["latency_s"]),
            })
    return rows


def percentile(values: list[float], p: float) -> float:
    """Nearest-rank percentile (p in 0..100). Returns 0.0 for no data."""
    if not values:
        return 0.0
    ordered = sorted(values)
    k = max(1, math.ceil(p / 100 * len(ordered)))
    return ordered[k - 1]


def _rate(count: int, total: int) -> float:
    return count / total if total else 0.0


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    lat = [r["latency_s"] for r in rows]
    codes = Counter()
    for r in rows:
        for attempt_codes in r["failure_codes"]:
            for c in attempt_codes:
                codes[c] += 1
    return {
        "runs": n,
        "first_try_pass": sum(1 for r in rows if r["first_try_pass"]),
        "first_try_pass_rate": _rate(sum(1 for r in rows if r["first_try_pass"]), n),
        "mean_attempts": (sum(r["attempts"] for r in rows) / n) if n else 0.0,
        "fallback_runs": sum(1 for r in rows if r["used_fallback"]),
        "fallback_rate": _rate(sum(1 for r in rows if r["used_fallback"]), n),
        "minutes_adjusted_runs": sum(1 for r in rows if r["minutes_adjusted"]),
        "p50_latency_s": percentile(lat, 50),
        "p95_latency_s": percentile(lat, 95),
        "failure_code_counts": dict(codes.most_common()),
    }


def _pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def render_summary_md(rows: list[dict]) -> str:
    s = summarize(rows)
    models = sorted({r["model"] for r in rows}) or ["(none)"]
    out = [
        "# LevelOutside evaluation summary",
        "",
        f"- Model: {', '.join(models)}",
        f"- Runs: {s['runs']}",
        f"- First-try pass (attempt 1 accepted, no fallback): "
        f"{s['first_try_pass']}/{s['runs']} ({_pct(s['first_try_pass_rate'])})",
        f"- Mean attempts per run: {s['mean_attempts']:.2f}",
        f"- Safe fallback used: {s['fallback_runs']}/{s['runs']} ({_pct(s['fallback_rate'])})",
        f"- Runs where minutes were rescaled by code: {s['minutes_adjusted_runs']}/{s['runs']}",
        f"- Latency per run (all attempts): p50 {s['p50_latency_s']:.1f}s, p95 {s['p95_latency_s']:.1f}s",
        "",
        "Failure codes (counted once per failed attempt):",
        "",
    ]
    if s["failure_code_counts"]:
        out += [f"- {code}: {count}" for code, count in s["failure_code_counts"].items()]
    else:
        out.append("- none")

    for key, title in (("age_band", "By age band"), ("game", "By game")):
        out += ["", f"## {title}", "", f"| {key} | runs | first-try pass | fallback |", "|---|---|---|---|"]
        for value in sorted({r[key] for r in rows}):
            sub = [r for r in rows if r[key] == value]
            ss = summarize(sub)
            out.append(f"| {value} | {ss['runs']} | {ss['first_try_pass']}/{ss['runs']} | "
                       f"{ss['fallback_runs']}/{ss['runs']} |")
    out += [
        "",
        "Notes: the sample is small and uses one object set and one duration. "
        "Treat these as a snapshot of this setup, not a general benchmark.",
        "",
    ]
    return "\n".join(out)
