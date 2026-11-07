"""Provider-agnostic LLM wrapper with strict-JSON mode, retries and mock mode.

Design goals
------------
* One function - :meth:`LLMClient.complete_json` - is all the rest of the app
  uses. It always returns a validated Pydantic model, never a raw string.
* Strict JSON: OpenAI-compatible providers get ``response_format=json_object``;
  Anthropic gets an explicit instruction plus a markdown-fence stripper.  A
  parse/validation failure is retried once, then falls back to a caller-supplied
  deterministic payload so the product never breaks.
* Mock mode: when ``MOCK_LLM=true`` or no API key is configured, the same
  fallback payload is returned immediately - realistic canned JSON that keeps a
  live demo safe.
* Every call is bounded by ``LLM_TIMEOUT_SECONDS`` (default 10s) and a small
  concurrency semaphore, so the per-listing "why it fits" fan-out is safe on
  rate-limited free tiers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Callable, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from config import Settings, get_settings
from prompts import prompt_fingerprint

logger = logging.getLogger("scoutly.llm")

T = TypeVar("T", bound=BaseModel)

#: Maximum number of LLM calls allowed to be in flight at once.
MAX_CONCURRENCY = 6

#: Player-friendly message shown in the UI when a real call did not happen.
FALLBACK_NOTE = "AI unavailable, showing basic results."

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def extract_json_object(raw: str) -> dict[str, Any]:
    """Parse the first JSON object out of an LLM reply.

    Handles markdown fences and chatty preambles.  Raises :class:`ValueError`
    when no parseable object exists.
    """
    if not raw or not raw.strip():
        raise ValueError("empty LLM response")

    text = _FENCE_RE.sub("", raw.strip()).strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found in LLM response")

    candidate = text[start : end + 1]
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise ValueError(f"invalid JSON from LLM: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("LLM returned JSON but not an object")
    return parsed


@dataclass
class LLMResult(Generic[T]):
    """Outcome of one structured LLM call."""

    value: T
    ai_available: bool
    note: str | None = None

    @property
    def ok(self) -> bool:
        """True when a real provider produced the value."""
        return self.ai_available


class LLMClient:
    """Async client that hides provider differences behind one JSON call."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._openai_client: Any = None
        self._anthropic_client: Any = None
        self._semaphore: asyncio.Semaphore | None = None

    # -- public API --------------------------------------------------------

    @property
    def mock_mode(self) -> bool:
        """True when no real provider call will be made."""
        return self.settings.mock_mode

    @property
    def provider(self) -> str:
        """Normalised provider id: ``openai``, ``anthropic`` or ``mock``."""
        return self.settings.provider

    @property
    def model(self) -> str:
        """Configured model id."""
        return self.settings.llm_model

    def describe(self) -> dict[str, Any]:
        """Small dict for the ``/api/health`` response."""
        return {
            "mock_llm": self.mock_mode,
            "llm_provider": self.provider,
            "llm_model": self.model,
            "prompt_version": prompt_fingerprint(),
        }

    async def complete_json(
        self,
        *,
        task: str,
        system: str,
        user: str,
        schema: type[T],
        fallback: Callable[[], dict[str, Any]],
        max_tokens: int = 1400,
    ) -> LLMResult[T]:
        """Ask the LLM for JSON conforming to ``schema``.

        Args:
            task: Short tag used in logs (e.g. ``"why_it_fits"``).
            system: System prompt, usually a constant from :mod:`prompts`.
            user: Rendered user prompt.
            schema: Pydantic model class the JSON must validate against.
            fallback: Zero-argument callable returning canned JSON. Used in mock
                mode and after two failed attempts. Must itself validate.
            max_tokens: Output token cap.

        Returns:
            :class:`LLMResult` carrying the validated value plus whether a real
            provider answered, and a user-facing note when it did not.
        """
        if self.mock_mode:
            # Mock mode is a *configured* provider, not a failure: the demo is
            # expected to run end-to-end on canned JSON. ``/api/health`` reports
            # ``mock_llm: true`` so the UI can label it honestly.
            return LLMResult(
                value=self._build(schema, fallback),
                ai_available=True,
                note="Mock mode: realistic canned response.",
            )

        parsed = await self._attempt_loop(
            task=task,
            system=system,
            user=user,
            schema=schema,
            max_tokens=max_tokens,
        )
        if parsed is not None:
            return LLMResult(value=parsed, ai_available=True, note=None)

        logger.warning("LLM task %r fell back to deterministic output", task)
        return LLMResult(
            value=self._build(schema, fallback),
            ai_available=False,
            note=FALLBACK_NOTE,
        )

    # -- internals ---------------------------------------------------------

    def _build(self, schema: type[T], fallback: Callable[[], dict[str, Any]]) -> T:
        """Validate the caller's deterministic payload (last line of defence)."""
        try:
            return schema.model_validate(fallback())
        except ValidationError as exc:  # pragma: no cover - programmer error
            logger.error("Fallback payload failed validation for %s: %s", schema, exc)
            raise

    async def _attempt_loop(
        self,
        *,
        task: str,
        system: str,
        user: str,
        schema: type[T],
        max_tokens: int,
    ) -> T | None:
        """Try up to twice (original + one repair attempt), validating JSON."""
        last_error = ""
        for attempt in range(2):
            prompt = user if attempt == 0 else (
                f"{user}\n\nYour previous reply was rejected: {last_error}\n"
                "Reply again with ONLY a valid JSON object, no markdown fences, no prose."
            )
            try:
                raw = await self._raw_call(system=system, user=prompt, max_tokens=max_tokens)
            except Exception as exc:  # network, auth, rate limit, timeout
                logger.warning("LLM %s attempt %s transport error: %s", task, attempt + 1, exc)
                last_error = f"transport error: {exc}"
                continue

            try:
                payload = extract_json_object(raw)
                return schema.model_validate(payload)
            except (ValueError, ValidationError) as exc:
                last_error = str(exc)[:400]
                logger.info("LLM %s attempt %s parse/validate error: %s", task, attempt + 1, last_error)

        return None

    async def _raw_call(self, *, system: str, user: str, max_tokens: int) -> str:
        """One bounded provider call, returning raw text."""
        timeout = float(self.settings.llm_timeout_seconds)
        sem = self._get_semaphore()
        async with sem:
            if self.provider == "anthropic":
                coro = self._call_anthropic(system=system, user=user, max_tokens=max_tokens)
            else:
                coro = self._call_openai(system=system, user=user, max_tokens=max_tokens)
            return await asyncio.wait_for(coro, timeout=timeout)

    def _get_semaphore(self) -> asyncio.Semaphore:
        """Lazily create the concurrency limiter inside the running loop."""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
        return self._semaphore

    async def _call_openai(self, *, system: str, user: str, max_tokens: int) -> str:
        """Call any OpenAI-compatible ``/chat/completions`` endpoint."""
        from openai import AsyncOpenAI

        if self._openai_client is None:
            kwargs: dict[str, Any] = {
                "api_key": self.settings.llm_api_key,
                "timeout": float(self.settings.llm_timeout_seconds),
                "max_retries": 0,
            }
            if self.settings.llm_base_url.strip():
                kwargs["base_url"] = self.settings.llm_base_url.strip()
            self._openai_client = AsyncOpenAI(**kwargs)

        response = await self._openai_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=max_tokens,
        )
        content = (response.choices[0].message.content or "").strip()
        if not content:
            raise ValueError("empty completion content")
        return content

    async def _call_anthropic(self, *, system: str, user: str, max_tokens: int) -> str:
        """Call Anthropic's Messages API and coerce the reply to JSON."""
        from anthropic import AsyncAnthropic

        if self._anthropic_client is None:
            self._anthropic_client = AsyncAnthropic(
                api_key=self.settings.llm_api_key,
                timeout=float(self.settings.llm_timeout_seconds),
                max_retries=0,
            )

        message = await self._anthropic_client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=0,
            system=system + "\n\nRespond with a single JSON object and nothing else.",
            messages=[{"role": "user", "content": user}],
        )
        chunks = [block.text for block in message.content if getattr(block, "type", "") == "text"]
        content = "\n".join(chunks).strip()
        if not content:
            raise ValueError("empty completion content")
        return content


_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Return the process-wide :class:`LLMClient` singleton."""
    global _client
    if _client is None:
        _client = LLMClient(get_settings())
    return _client


def reset_llm_client() -> None:
    """Drop the cached client (used by tests after settings change)."""
    global _client
    _client = None
