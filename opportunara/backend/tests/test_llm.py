"""Tests for the provider-agnostic LLM wrapper (JSON parsing, retries, mock mode)."""

from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel

from config import Settings
from llm import (
    FALLBACK_NOTE,
    LLMClient,
    extract_json_object,
    get_llm_client,
    reset_llm_client,
)


class Answer(BaseModel):
    """Minimal schema used to exercise validation."""

    value: str = ""
    count: int = 0


def _fallback() -> dict:
    return {"value": "fallback", "count": 1}


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------


def test_extract_plain_json() -> None:
    """A bare JSON object parses."""
    assert extract_json_object('{"value": "ok"}') == {"value": "ok"}


def test_extract_fenced_json() -> None:
    """Markdown fences are stripped."""
    assert extract_json_object('```json\n{"value": "ok"}\n```') == {"value": "ok"}
    assert extract_json_object('```\n{"value": "ok"}\n```') == {"value": "ok"}


def test_extract_json_with_preamble() -> None:
    """Chatty preambles are tolerated."""
    raw = 'Sure! Here is the JSON:\n{"value": "ok", "count": 2}\nLet me know if you need more.'
    assert extract_json_object(raw) == {"value": "ok", "count": 2}


@pytest.mark.parametrize("raw", ["", "   ", "no json here", "{broken", "[1, 2, 3]"])
def test_extract_rejects_non_objects(raw: str) -> None:
    """Empty, non-JSON and non-object payloads raise ValueError."""
    with pytest.raises(ValueError):
        extract_json_object(raw)


# ---------------------------------------------------------------------------
# Mock mode
# ---------------------------------------------------------------------------


def test_mock_mode_returns_canned_payload() -> None:
    """With no API key the wrapper returns the caller's canned payload instantly."""
    client = LLMClient(Settings(llm_api_key="", mock_llm=False))
    assert client.mock_mode is True

    result = asyncio.run(
        client.complete_json(
            task="test",
            system="s",
            user="u",
            schema=Answer,
            fallback=_fallback,
        )
    )
    assert result.value.value == "fallback"
    assert result.ai_available is True  # mock is a configured provider
    assert "mock" in (result.note or "").lower()


def test_mock_llm_flag_forces_mock_even_with_key() -> None:
    """MOCK_LLM=true wins over a configured key."""
    client = LLMClient(Settings(llm_api_key="sk-test", mock_llm=True))
    assert client.mock_mode is True
    assert client.provider == "mock"


def test_get_llm_client_is_a_singleton() -> None:
    """One client is shared process-wide."""
    assert get_llm_client() is get_llm_client()
    reset_llm_client()
    assert get_llm_client() is get_llm_client()


# ---------------------------------------------------------------------------
# Live-path behaviour (transport stubbed)
# ---------------------------------------------------------------------------


def _live_client() -> LLMClient:
    settings = Settings(llm_api_key="sk-test", mock_llm=False, llm_provider="openai")
    return LLMClient(settings)


def test_successful_call_parses_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """A valid reply is validated and reported as AI-backed."""
    client = _live_client()

    async def fake_raw(*, system: str, user: str, max_tokens: int) -> str:
        return '{"value": "hello", "count": 3}'

    monkeypatch.setattr(client, "_raw_call", fake_raw)
    result = asyncio.run(
        client.complete_json(task="t", system="s", user="u", schema=Answer, fallback=_fallback)
    )
    assert result.value.value == "hello"
    assert result.value.count == 3
    assert result.ai_available is True
    assert result.note is None


def test_invalid_json_is_retried_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """A parse failure triggers one repair attempt."""
    client = _live_client()
    calls: list[str] = []

    async def fake_raw(*, system: str, user: str, max_tokens: int) -> str:
        calls.append(user)
        return "not json at all" if len(calls) == 1 else '{"value": "second", "count": 2}'

    monkeypatch.setattr(client, "_raw_call", fake_raw)
    result = asyncio.run(
        client.complete_json(task="t", system="s", user="u", schema=Answer, fallback=_fallback)
    )
    assert len(calls) == 2
    assert result.value.value == "second"
    assert result.ai_available is True


def test_repair_prompt_mentions_rejection(monkeypatch: pytest.MonkeyPatch) -> None:
    """The retry prompt includes the validation error."""
    client = _live_client()
    prompts_seen: list[str] = []

    async def fake_raw(*, system: str, user: str, max_tokens: int) -> str:
        prompts_seen.append(user)
        return "nope" if len(prompts_seen) == 1 else '{"value": "ok"}'

    monkeypatch.setattr(client, "_raw_call", fake_raw)
    asyncio.run(client.complete_json(task="t", system="s", user="u", schema=Answer, fallback=_fallback))
    assert "previous reply was rejected" in prompts_seen[1].lower()


def test_two_failures_fall_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """After two bad replies the deterministic payload is used and flagged."""
    client = _live_client()
    calls = {"n": 0}

    async def fake_raw(*, system: str, user: str, max_tokens: int) -> str:
        calls["n"] += 1
        return "still not json"

    monkeypatch.setattr(client, "_raw_call", fake_raw)
    result = asyncio.run(
        client.complete_json(task="t", system="s", user="u", schema=Answer, fallback=_fallback)
    )
    assert calls["n"] == 2
    assert result.value.value == "fallback"
    assert result.ai_available is False
    assert result.note == FALLBACK_NOTE


def test_transport_error_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """A network/auth failure never raises - it degrades."""
    client = _live_client()

    async def fake_raw(*, system: str, user: str, max_tokens: int) -> str:
        raise RuntimeError("401 unauthorized")

    monkeypatch.setattr(client, "_raw_call", fake_raw)
    result = asyncio.run(
        client.complete_json(task="t", system="s", user="u", schema=Answer, fallback=_fallback)
    )
    assert result.ai_available is False
    assert result.value.value == "fallback"
    assert result.note == FALLBACK_NOTE


def test_schema_validation_failure_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """JSON that does not satisfy the schema is treated as a parse failure."""
    client = _live_client()

    async def fake_raw(*, system: str, user: str, max_tokens: int) -> str:
        return '{"value": "ok", "count": "not-a-number"}'

    monkeypatch.setattr(client, "_raw_call", fake_raw)
    result = asyncio.run(
        client.complete_json(task="t", system="s", user="u", schema=Answer, fallback=_fallback)
    )
    assert result.ai_available is False
    assert result.value.count == 1


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("provider", "expected"),
    [
        ("openai", "openai"),
        ("OpenRouter", "openai"),
        ("anthropic", "anthropic"),
        ("ANTHROPIC", "anthropic"),
    ],
)
def test_provider_normalisation(provider: str, expected: str) -> None:
    """Provider aliases collapse onto the two supported implementations."""
    settings = Settings(llm_api_key="sk-test", mock_llm=False, llm_provider=provider)
    assert settings.provider == expected


def test_describe_reports_prompt_version() -> None:
    """Health metadata includes prompt provenance."""
    client = LLMClient(Settings(llm_api_key="", mock_llm=True))
    described = client.describe()
    assert described["mock_llm"] is True
    assert described["prompt_version"].startswith("v")


def test_every_prompt_contains_the_guardrail() -> None:
    """All prompts embed the 'only facts provided' guardrail."""
    import prompts

    guardrail_tail = prompts.GUARDRAIL.split(".")[0]
    for name in dir(prompts):
        if name.endswith("_SYSTEM") or name.endswith("_USER"):
            value = getattr(prompts, name)
            if isinstance(value, str) and "{" in value:
                # User templates render the guardrail via the system prompt.
                continue
            if isinstance(value, str):
                assert prompts.GUARDRAIL in value, f"{name} is missing the guardrail"
