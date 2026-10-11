# LevelOutside

Turn a child's favorite game into a real-life outdoor mission, printed on paper.

A parent picks an age band, a duration and the child's favorite game, then ticks
the things that are actually in the garden or park. A local open-weight model
(Gemma 3 4B, served by Ollama) writes a short supervised mission in that game's
style, and plain Python checks it for child safety before it can be printed. The
child never touches a screen. Nothing about the child leaves the parent's laptop.

Built for the DEV Hacktoberfest Open-Source AI Challenge, Week 1 ("Touch Grass"),
October 10-11, 2026.

## How it works

1. Choose an age band (5-7, 8-10, 11-13), 20 or 40 minutes, and a game. Ten games
   are built in (Minecraft, Pokemon, Super Mario, Roblox obstacle courses, Animal
   Crossing, Lego, Sonic, Mario Kart, Kirby, Stardew Valley), or describe another in
   one sentence.
2. Tick objects from a fixed checklist of inanimate things and plants. No animals
   or people are ever offered. There is no photo step.
3. "Make my mission" runs Gemma with a retry loop. A validator checks every
   attempt. After 3 failed attempts the app uses a plain, pre-written safe mission.
   The UI shows the attempt count and whether the fallback was used.
4. Download a printable A4 card (HTML): a "A grown-up stays with you" banner, a
   checkbox and time per task, a certificate, and a box to draw a game hero.
   There is no field for a child's name.

## The model proposes, the code decides

Safety lives in code (`leveloutside/validator.py`, `leveloutside/safety.py`), not
only in the prompt:

- deny-list: living things (including creature words), eating, and other
  categories (`unsafe_text`)
- only parent-confirmed objects may appear (`unconfirmed_object`)
- reading-level limit per age band (`reading_level`)
- task minutes must total the chosen duration (code rescales small errors)

The deny-list and limits are conservative heuristics, not a substitute for adult
supervision. A grown-up stays with the child.

## Run it (Windows)

    python -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    ollama pull gemma3:4b
    .venv\Scripts\python.exe -m streamlit run app.py

Ollama must be running locally. The "quick safe mission" button works without the
model. Other scripts: `scripts/try_mission.py` (one real generation) and
`scripts/make_card.py` (mission to HTML and PDF; it looks for Microsoft Edge or
Chrome for the PDF).

## Tests

    .venv\Scripts\python.exe -m pytest -q -m "not integration"

272 tests pass without a model or network. One integration test needs Ollama and is
skipped when it is not running.

## Evaluation

`eval/run_eval.py` runs 15 combinations (5 games x 3 age bands; objects tree, stick,
stone, bench, leaf; 20 minutes) against real gemma3:4b through Ollama. "First-try
pass" means the validator accepted attempt 1. One run per combination per round.
Results are committed under `eval/results`, `eval/results_v2`, `eval/results_v3`
and `eval/results_v3b`.

| Round | Commit | First-try pass | Mean attempts | Fallbacks | Latency p50 / p95 |
|---|---|---|---|---|---|
| 1 | c4fc30e | 7/15 (46.7%) | 1.80 | 3/15 | 31.6s / 65.8s |
| 2 | 4443a69 | 6/15 (40.0%) | 2.07 | 6/15 | 54.8s / 79.8s |
| 3 | bd24a2e | 13/15 (86.7%) | 1.20 | 0/15 | 30.9s / 53.0s |
| 3, repeat | bd24a2e | 12/15 (80.0%) | 1.27 | 1/15 | 31.4s / 55.5s |

Round 2 got worse because a prompt change made the model write the game's name in
the mission text ("Animal" in Animal Crossing tripped the living-things check;
"Mushroom" in Super Mario tripped the eating check). The validator rejected all of
it. Round 3 forbids the game title in mission text.

## Limits

- Small sample (15 runs per round), one 4B model. This is not a benchmark.
- The evaluation measures validity and safety, not whether a child enjoys a mission.
- Ages 5-7 are the hardest band for a 4B model under the reading-level limit.
- Not tested with a child yet.
- The checklist includes playground items (swing, slide) that I would remove.
- Not built: a photo step, simpler 5-7 vocabulary, and any cloud integrations.

## License

MIT
