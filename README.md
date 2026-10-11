# LevelOutside

Turn a child's favorite game into a real-life outdoor mission, printed on paper.

A parent enters the game and the child's age band, plus an optional photo of the
space. A local open-weight model (Gemma via Ollama) writes a mission using only
objects the parent confirmed. Plain Python then checks the mission for safety
before anything is printed. The child never touches a screen.

## Privacy

Everything about the child stays on the parent's laptop. Optional cloud services
only ever see a game title, finished mission text, or timing data.

## Status

Built during the Hacktoberfest Open-Source AI Challenge (Week 1) window,
October 10-11, 2026. Work in progress.

- [x] Safety validator, retry loop and safe fallback (this repo)
- [ ] Privacy gate (EXIF strip, face rejection)
- [ ] Game profile (library + search fallback)
- [ ] Scene object listing (Gemma vision)
- [ ] Mission writer (Gemma via Ollama)
- [ ] Printable card and audio briefing

## Run the tests

    pip install -r requirements.txt
    pytest -q

## Run the app

    .venv\Scripts\python.exe -m streamlit run app.py

Ollama must be running locally (`ollama serve`) with the `gemma3:4b` model pulled.
The safe-fallback button works fully offline.

## Evaluate

Measures how often the local model produces a valid mission on its first try.
Results are written to `eval/results/` as a CSV plus a markdown summary. Mission
text is never stored, only counts, failure codes and validator messages.

    .venv\Scripts\python.exe eval\run_eval.py --limit 2    # quick smoke test
    .venv\Scripts\python.exe eval\run_eval.py              # 15 runs (5 games x 3 age bands)
    .venv\Scripts\python.exe eval\run_eval.py --model gemma3:4b

If the model gives minutes that do not add up, code rescales them and the run is
counted separately as "minutes rescaled".

## Safety note

The deny-list, reading-level limits and age rules are conservative heuristics,
not a substitute for adult supervision. A grown-up stays with the child.

## License

MIT
