"""Owner: agent-2. STUB: minimal Gemini gateway (agent-1 M0). Agent-2 replaces this with retries, tools and usage logging.

This is the only module allowed to talk to Gemini (MASTER_PROMPT rule 12). Callers catch `LLMUnavailable` and fall back.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from ..config import get_settings

T = TypeVar("T", bound=BaseModel)


class LLMUnavailable(RuntimeError):
    """Raised when no LLM answer is available (mock without a canned response, missing key, quota, outage)."""


class LLMClient(Protocol):
    name: str

    def generate_text(self, prompt: str, *, system: str | None = None, model: str | None = None) -> str: ...

    def generate_structured(
        self, prompt: str, schema: type[T], *, system: str | None = None, model: str | None = None
    ) -> T: ...


class MockLLM:
    """Deterministic LLM for mock mode and tests. Responses are registered by key; unknown prompts raise LLMUnavailable.

    A prompt matches a key when the key is a substring of the prompt.
    """

    name = "mock"

    def __init__(self) -> None:
        self._text: dict[str, str] = {}
        self._structured: dict[str, Callable[[], Any]] = {}

    def register_text(self, key: str, text: str) -> None:
        self._text[key] = text

    def register_structured(self, key: str, factory: Callable[[], Any]) -> None:
        self._structured[key] = factory

    def generate_text(self, prompt: str, *, system: str | None = None, model: str | None = None) -> str:
        for key, text in self._text.items():
            if key in prompt:
                return text
        raise LLMUnavailable("MockLLM: no canned text response for this prompt")

    def generate_structured(
        self, prompt: str, schema: type[T], *, system: str | None = None, model: str | None = None
    ) -> T:
        for key, factory in self._structured.items():
            if key in prompt:
                value = factory()
                return value if isinstance(value, schema) else schema.model_validate(value)
        raise LLMUnavailable("MockLLM: no canned structured response for this prompt")


class GeminiLLM:
    """Live Gemini via the Interactions API (`google-genai>=2.30.1`). One client per process, `store=False`."""

    name = "gemini"

    def __init__(self, api_key: str | None = None, model_fast: str | None = None) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.gemini_api_key
        self.model_fast = model_fast or settings.model_fast
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            if not self._api_key:
                raise LLMUnavailable("GEMINI_API_KEY is not set")
            try:
                from google import genai
            except ImportError as exc:  # pragma: no cover - depends on the environment
                raise LLMUnavailable("google-genai is not installed") from exc
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def generate_text(self, prompt: str, *, system: str | None = None, model: str | None = None) -> str:
        text = f"{system}\n\n{prompt}" if system else prompt
        try:
            interaction = self._get_client().interactions.create(
                model=model or self.model_fast, input=text, store=False
            )
            return interaction.output_text
        except LLMUnavailable:
            raise
        except Exception as exc:  # any SDK/network failure means "unavailable" to callers
            raise LLMUnavailable(f"Gemini call failed: {exc}") from exc

    def generate_structured(
        self, prompt: str, schema: type[T], *, system: str | None = None, model: str | None = None
    ) -> T:
        # STUB: asks for JSON in plain text. Agent-2 switches this to the SDK's structured-output support.
        instructions = f"Reply with only a JSON object matching this JSON schema:\n{schema.model_json_schema()}"
        raw = self.generate_text(f"{prompt}\n\n{instructions}", system=system, model=model).strip()
        if raw.startswith("```"):
            raw = raw.strip("`").removeprefix("json").strip()
        try:
            return schema.model_validate_json(raw)
        except Exception as exc:
            raise LLMUnavailable(f"Gemini returned invalid structured output: {exc}") from exc


_llm: LLMClient | None = None


def get_llm() -> LLMClient:
    """MockLLM in mock mode; GeminiLLM otherwise. Cached per process."""
    global _llm
    if _llm is None:
        _llm = MockLLM() if get_settings().mode == "mock" else GeminiLLM()
    return _llm
