import json

from leveloutside.evalstats import (
    FIELDS, append_row, load_rows, percentile, render_summary_md, summarize,
)


def row(game="Minecraft", band="8-10", first=True, attempts=1, fb=False,
        adj=False, codes=None, lat=10.0):
    return {"timestamp": "t", "model": "m", "game": game, "age_band": band,
            "first_try_pass": first, "attempts": attempts, "used_fallback": fb,
            "minutes_adjusted": adj, "failure_codes": codes or [],
            "validator_errors": [], "latency_s": lat}


def test_percentile_nearest_rank():
    assert percentile([1, 2, 3, 4, 5], 50) == 3
    assert percentile([1, 2, 3, 4, 5], 95) == 5
    assert percentile([], 50) == 0.0


def test_summary_math():
    rows = [
        row(first=True, attempts=1, lat=10),
        row(first=False, attempts=2, codes=[["bad_duration"]], lat=30),
        row(first=False, attempts=3, fb=True,
            codes=[["unconfirmed_object", "bad_duration"], ["unconfirmed_object"]], lat=60),
        row(first=True, attempts=1, adj=True, lat=20),
    ]
    s = summarize(rows)
    assert s["runs"] == 4
    assert s["first_try_pass"] == 2 and s["first_try_pass_rate"] == 0.5
    assert s["mean_attempts"] == 1.75
    assert s["fallback_runs"] == 1 and s["fallback_rate"] == 0.25
    assert s["minutes_adjusted_runs"] == 1
    assert s["failure_code_counts"] == {"unconfirmed_object": 2, "bad_duration": 2}
    assert s["p50_latency_s"] == 20 and s["p95_latency_s"] == 60


def test_empty_summary_does_not_divide_by_zero():
    s = summarize([])
    assert s["runs"] == 0 and s["first_try_pass_rate"] == 0.0


def test_csv_written_incrementally_and_roundtrips(tmp_path):
    path = tmp_path / "r.csv"
    base = {"timestamp": "t", "model": "m", "game": "Minecraft", "age_band": "8-10",
            "first_try_pass": True, "attempts": 1, "used_fallback": False,
            "minutes_adjusted": False, "failure_codes_json": "[]",
            "validator_errors_json": "[]", "latency_s": "12.5"}
    append_row(path, base)
    assert len(load_rows(path)) == 1          # readable after the first row
    append_row(path, {**base, "game": "Pokemon", "first_try_pass": False,
                      "attempts": 2,
                      "failure_codes_json": json.dumps([["bad_duration"]])})
    rows = load_rows(path)
    assert [r["game"] for r in rows] == ["Minecraft", "Pokemon"]
    assert rows[1]["failure_codes"] == [["bad_duration"]]
    assert path.read_text().splitlines()[0].split(",") == FIELDS


def test_markdown_mentions_computed_numbers():
    md = render_summary_md([row(), row(first=False, attempts=2, codes=[["bad_duration"]])])
    assert "1/2 (50%)" in md and "bad_duration: 1" in md and "| 8-10 |" in md
