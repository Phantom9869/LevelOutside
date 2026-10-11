# LevelOutside — Project Brief

**Challenge:** DEV Hacktoberfest "Touch Grass" (deadline Oct 11, 11:59 PM PDT)
**Repo:** github.com/Phantom9869/LevelOutside
**License:** MIT
**Language:** Python 3.13, pytest

---

## What it is

A parent enters a child's age band and favorite game (plus an optional photo of the outdoor
space). A local open-weight model (Gemma via Ollama) writes a real-life outdoor mission in
that game's style, using only objects the parent confirmed are present. Plain Python validates
the output for child safety. The result is a printable mission card; the child never touches
a screen.

---

## Architecture

```
leveloutside/
  schema.py      — Mission and Task Pydantic models
  safety.py      — Deny-list patterns, allowed materials, scene nouns, age rules
  validator.py   — validate_mission(), MissionContext
  fallback.py    — safe_fallback() (always-valid pre-written mission)
  pipeline.py    — generate_with_retries() (retry loop + fallback)
tests/
  test_validator.py — 90 unit tests (no model or network required)
```

---

## Hard rules

1. **Privacy:** Everything about the child (age band, photos, free text) stays on this
   machine. Only a game title (SerpApi), finished mission text (ElevenLabs), and
   timing/error codes (Sentry) may ever leave, and all three are optional. The core path
   must work fully offline.

2. **Never weaken or delete safety rules or tests** to make something pass. If a rule
   blocks a feature, report it.

3. **Living things:** Scene-object lists must contain only inanimate objects and plants.
   Never offer animals or people as confirmable objects. If the model reports a living
   creature, drop it and tell the parent the mission will not involve it.
   - "bird" is removed from KNOWN_SCENE_NOUNS.
   - A deny category covers mission text mentioning dog, cat, bird, animal, pet, person,
     people, or stranger.

4. **Unit tests must not need a model or network.** Inject callables, mock HTTP.
   Optional integration tests skip unless Ollama is reachable.

5. **Never fabricate results or benchmark numbers.** Report blockers honestly.

6. **No secrets in the repo.** Read keys from env vars. `.env` stays gitignored.
   Test photos go in `private/` (gitignored).

7. **Small commits after green tests.** Do not push; the user pushes.

---

## Model

- Provider: Ollama (local)
- Default model: `gemma3:4b` (env: `LEVELOUTSIDE_MODEL`)
- Supports image input for the outdoor-space photo step

---

## Optional integrations (all off by default, all env-var gated)

| Integration | What leaves the device | Env var |
|-------------|------------------------|---------|
| SerpApi     | Game title only        | `SERPAPI_KEY` |
| ElevenLabs  | Finished mission text  | `ELEVENLABS_KEY` |
| Sentry      | Timing + error codes   | `SENTRY_DSN` |

---

## Age bands

| Band  | Tasks | Max Flesch-Kincaid grade |
|-------|-------|--------------------------|
| 5–7   | 2–4   | 3.0                      |
| 8–10  | 3–5   | 5.0                      |
| 11–13 | 3–6   | 7.0                      |

---

## Reply format after each task

> What changed / commands run / test results / open issues
