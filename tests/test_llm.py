import json
import re
from unittest.mock import patch, MagicMock

import httpx
import pytest

from leveloutside import MissionContext, generate_with_retries
from leveloutside.llm import make_generator, _build_messages, _system_prompt
from leveloutside.safety import AGE_RULES, ALLOWED_MATERIALS
from leveloutside.schema import Mission


CTX = MissionContext(
    confirmed_objects={"tree", "stick", "stone", "bench", "leaf"},
    age_band="8-10",
    duration_min=20,
)

PROFILE = {
    "title": "Minecraft",
    "goal": "Survive and build",
    "verbs": ["gather", "build", "craft"],
    "vocabulary": ["block", "biome"],
}

GOOD_RESPONSE = json.dumps({
    "title": "Build the Stick Shelter",
    "story_hook": "Night is coming. Build a safe shelter before the timer ends.",
    "tasks": [
        {"mechanic": "gather", "instruction": "Gather five sticks of different sizes.",
         "objects": ["stick"], "materials": ["paper bag"], "minutes": 6},
        {"mechanic": "build",
         "instruction": "Lean the sticks against the bench to make a little hut.",
         "objects": ["stick", "bench"], "materials": [], "minutes": 8},
        {"mechanic": "craft", "instruction": "Draw a map of your shelter on paper.",
         "objects": [], "materials": ["paper", "pencil"], "minutes": 6},
    ],
    "finale": "Show your grown-up your shelter and map.",
    "achievement_name": "Master Builder",
})


def _make_response(content: str, status_code: int = 200):
    """Create a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = {"message": {"content": content}}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.text = f"error {status_code}"
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"Error {status_code}", request=MagicMock(), response=resp,
        )
    return resp


# ── Request body tests ──────────────────────────────────────────────────

class TestRequestBody:
    def test_model_in_request(self):
        """The resolved model name appears in the POST payload."""
        with patch("leveloutside.llm.httpx.Client") as MockClient:
            client = MockClient.return_value.__enter__.return_value
            client.post.return_value = _make_response(GOOD_RESPONSE)

            gen = make_generator(PROFILE, CTX.confirmed_objects, CTX, model="test-model")
            gen([])

            body = client.post.call_args[1]["json"]
            assert body["model"] == "test-model"

    def test_stream_false_in_request(self):
        with patch("leveloutside.llm.httpx.Client") as MockClient:
            client = MockClient.return_value.__enter__.return_value
            client.post.return_value = _make_response(GOOD_RESPONSE)

            gen = make_generator(PROFILE, CTX.confirmed_objects, CTX)
            gen([])

            body = client.post.call_args[1]["json"]
            assert body["stream"] is False

    def test_format_is_json_schema(self):
        with patch("leveloutside.llm.httpx.Client") as MockClient:
            client = MockClient.return_value.__enter__.return_value
            client.post.return_value = _make_response(GOOD_RESPONSE)

            gen = make_generator(PROFILE, CTX.confirmed_objects, CTX)
            gen([])

            body = client.post.call_args[1]["json"]
            assert isinstance(body["format"], dict)
            assert "properties" in body["format"]

    def test_confirmed_objects_in_system_prompt(self):
        with patch("leveloutside.llm.httpx.Client") as MockClient:
            client = MockClient.return_value.__enter__.return_value
            client.post.return_value = _make_response(GOOD_RESPONSE)

            gen = make_generator(PROFILE, CTX.confirmed_objects, CTX)
            gen([])

            body = client.post.call_args[1]["json"]
            system = body["messages"][0]["content"]
            for obj in CTX.confirmed_objects:
                assert obj in system

    def test_age_band_limits_in_system_prompt(self):
        with patch("leveloutside.llm.httpx.Client") as MockClient:
            client = MockClient.return_value.__enter__.return_value
            client.post.return_value = _make_response(GOOD_RESPONSE)

            gen = make_generator(PROFILE, CTX.confirmed_objects, CTX)
            gen([])

            body = client.post.call_args[1]["json"]
            system = body["messages"][0]["content"]
            rules = AGE_RULES["8-10"]
            assert str(rules["tasks"][0]) in system  # task lo
            assert str(rules["tasks"][1]) in system  # task hi
            assert str(rules["max_grade"]) in system


# ── Feedback / retry tests ──────────────────────────────────────────────

class TestFeedback:
    def test_feedback_appears_in_prompt(self):
        with patch("leveloutside.llm.httpx.Client") as MockClient:
            client = MockClient.return_value.__enter__.return_value
            client.post.return_value = _make_response(GOOD_RESPONSE)

            gen = make_generator(PROFILE, CTX.confirmed_objects, CTX)
            gen(["Task 1 uses 'fountain', which the parent did not confirm."])

            body = client.post.call_args[1]["json"]
            user_msg = body["messages"][1]["content"]
            assert "Fix these problems:" in user_msg
            assert "fountain" in user_msg

    def test_empty_feedback_no_fix_section(self):
        with patch("leveloutside.llm.httpx.Client") as MockClient:
            client = MockClient.return_value.__enter__.return_value
            client.post.return_value = _make_response(GOOD_RESPONSE)

            gen = make_generator(PROFILE, CTX.confirmed_objects, CTX)
            gen([])

            body = client.post.call_args[1]["json"]
            user_msg = body["messages"][1]["content"]
            assert "Fix these problems:" not in user_msg


# ── Format fallback tests ──────────────────────────────────────────────

class TestFormatFallback:
    def test_schema_fallback_to_json(self):
        """When the schema format causes a 400, retry with format='json'."""
        with patch("leveloutside.llm.httpx.Client") as MockClient:
            client = MockClient.return_value.__enter__.return_value
            # First call fails (schema rejected), second succeeds with format="json"
            client.post.side_effect = [
                _make_response("error", status_code=400),
                _make_response(GOOD_RESPONSE),
            ]

            gen = make_generator(PROFILE, CTX.confirmed_objects, CTX)
            result = gen([])

            assert result == GOOD_RESPONSE
            # Second call should use format="json"
            second_call_body = client.post.call_args_list[1][1]["json"]
            assert second_call_body["format"] == "json"
            # Schema should appear in user message text
            user_msg = second_call_body["messages"][1]["content"]
            assert "model_json_schema" in user_msg or "properties" in user_msg


# ── Error handling tests ────────────────────────────────────────────────

class TestErrors:
    def test_connection_error_raises_runtime(self):
        with patch("leveloutside.llm.httpx.Client") as MockClient:
            client = MockClient.return_value.__enter__.return_value
            client.post.side_effect = httpx.ConnectError("refused")

            gen = make_generator(PROFILE, CTX.confirmed_objects, CTX)
            with pytest.raises(RuntimeError, match="Cannot reach Ollama"):
                gen([])


# ── System prompt content tests ─────────────────────────────────────────

class TestSystemPrompt:
    def test_materials_listed(self):
        prompt = _system_prompt(PROFILE, CTX.confirmed_objects, CTX)
        for mat in ALLOWED_MATERIALS:
            assert mat in prompt

    def test_no_animals_instruction(self):
        prompt = _system_prompt(PROFILE, CTX.confirmed_objects, CTX)
        assert "animals" in prompt.lower()
        assert "dogs" in prompt.lower()

    def test_duration_mentioned(self):
        prompt = _system_prompt(PROFILE, CTX.confirmed_objects, CTX)
        assert str(CTX.duration_min) in prompt

    def test_empty_objects_says_ground_sky(self):
        prompt = _system_prompt(PROFILE, set(), CTX)
        assert "ground" in prompt and "sky" in prompt


# ── Integration test (skips without Ollama) ─────────────────────────────

def _ollama_reachable() -> bool:
    try:
        resp = httpx.get("http://localhost:11434/api/tags", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


@pytest.mark.integration
@pytest.mark.skipif(not _ollama_reachable(), reason="Ollama not reachable")
def test_integration_real_ollama():
    """Hit a real Ollama instance; validate the result with the pipeline."""
    profile = {
        "title": "Minecraft",
        "goal": "Survive the night by building a shelter and gathering resources",
        "verbs": ["gather", "build", "explore", "craft"],
        "vocabulary": ["block", "biome", "resource", "shelter"],
    }
    ctx = MissionContext(
        confirmed_objects={"tree", "stick", "stone", "bench", "leaf"},
        age_band="8-10",
        duration_min=20,
    )
    gen = make_generator(profile, ctx.confirmed_objects, ctx)
    result = generate_with_retries(gen, ctx)
    assert result.mission is not None
    # It should be valid (possibly via fallback)
    assert result.mission.title



# ---- prompt fixes found in a real run ----

class TestPromptFixes:
    def _prompt(self):
        from leveloutside.llm import _system_prompt
        return _system_prompt(PROFILE, CTX.confirmed_objects, CTX)

    def test_materials_never_in_objects_rule(self):
        p = self._prompt()
        assert "Never put a material in \"objects\"" in p

    def test_unconfirmed_scene_nouns_listed_as_absent(self):
        p = self._prompt()
        assert "wall" in p and "fence" in p      # not confirmed
        absent_line = [l for l in p.splitlines() if l.startswith("- Do not mention these")][0]
        assert "tree" not in absent_line and "stick" not in absent_line

    def test_mechanic_must_be_a_listed_verb(self):
        p = self._prompt()
        assert "ONE word from: gather, build, craft" in p

    def test_shape_example_minutes_sum_to_duration(self):
        import re
        p = self._prompt()
        mins = [int(m) for m in re.findall(r'"minutes": (\d+)', p)]
        assert len(mins) == 3 and sum(mins) == CTX.duration_min
