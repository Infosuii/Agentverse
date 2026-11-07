"""The single Gemini gateway (MASTER_PROMPT 9.2 and rule 12). Owner: agent-2.

Only this module talks to Gemini. It uses the Interactions API (`google-genai>=2.30.1`) with one client per process
and `store=False`, and owns retries (1, 2, 4 s backoff; at most 3 attempts on 429 / 5xx / timeouts), per-call
timeouts, token-usage logging and native structured output. Callers catch `LLMUnavailable` and fall back.

LLM-facing schemas passed to `generate_structured` should be small Pydantic models rather than full contracts:
contracts use `extra="forbid"` and reject any extra keys the model invents.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from ..config import get_settings

T = TypeVar("T", bound=BaseModel)

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
BACKOFF_S = (1.0, 2.0, 4.0)
DEFAULT_TIMEOUT_S = 60.0


class LLMUnavailable(RuntimeError):
    """Raised when no LLM answer is available (mock without a canned response, missing key, quota, outage)."""


@dataclass(frozen=True)
class Citation:
    """One grounding citation. `url` is exactly what grounding metadata returned (often a Google redirect URL)."""
    url: str
    title: str | None = None
    cited_text: str | None = None


@dataclass(frozen=True)
class GroundedAnswer:
    """A Google-Search-grounded answer. Citations come only from the response's grounding annotations."""
    text: str
    citations: list[Citation] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)
    model: str | None = None


@dataclass(frozen=True)
class FunctionCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolTurn:
    """One model turn of a stateless tool loop.

    `steps` are the response steps exactly as received (JSON dicts, None fields dropped). Append them to the
    history unchanged: in stateless mode thought steps and built-in tool steps carry signatures that the API needs
    back verbatim (docs: thinking.md "Stateless mode", tool-combination.md "Critical fields").
    """
    steps: list[dict[str, Any]]
    function_calls: list[FunctionCall] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)
    text: str = ""
    citations: list[Citation] = field(default_factory=list)
    status: str | None = None


def user_input(text: str) -> dict[str, Any]:
    """A `user_input` history step."""
    return {"type": "user_input", "content": [{"type": "text", "text": text}]}


def function_result(call: FunctionCall, result: Any) -> dict[str, Any]:
    """A `function_result` history step answering `call` (result is JSON-encoded unless already a string)."""
    text = result if isinstance(result, str) else json.dumps(result, default=str)
    return {"type": "function_result", "name": call.name, "call_id": call.id, "result": [{"type": "text", "text": text}]}


def parse_turn(interaction: Any) -> ToolTurn:
    raw_steps = _get(interaction, "steps") or []
    steps = [s if isinstance(s, dict) else s.model_dump(mode="json", exclude_none=True) for s in raw_steps]
    calls = [FunctionCall(id=str(s.get("id")), name=str(s.get("name")), arguments=dict(s.get("arguments") or {}))
             for s in steps if s.get("type") == "function_call"]
    text, citations, queries = parse_grounding({"steps": steps})
    return ToolTurn(steps=steps, function_calls=calls, search_queries=queries, text=text, citations=citations,
                    status=_get(interaction, "status"))


class LLMClient(Protocol):
    """Appendix B gateway interface. `thinking_level` and `search_grounded` are additive (both implementations have
    them); the Appendix B call shapes are unchanged."""
    name: str

    def generate_text(self, prompt: str, *, system: str | None = None, model: str | None = None,
                      thinking_level: str | None = None) -> str: ...

    def generate_structured(
        self, prompt: str, schema: type[T], *, system: str | None = None, model: str | None = None,
        thinking_level: str | None = None,
    ) -> T: ...

    def search_grounded(self, prompt: str, *, system: str | None = None, model: str | None = None,
                        thinking_level: str | None = None) -> GroundedAnswer: ...

    def tool_turn(self, history: list[dict[str, Any]], *, tools: list[dict[str, Any]], system: str | None = None,
                  model: str | None = None, thinking_level: str | None = "low",
                  timeout_s: float | None = None) -> ToolTurn: ...


Factory = Callable[[], Any]
TurnScript = Callable[[list[dict[str, Any]]], ToolTurn]


Factory = Callable[[], Any]


class MockLLM:
    """Deterministic LLM for mock mode and tests. Responses are registered by key; unknown prompts raise LLMUnavailable.

    A prompt matches a key when the key is a substring of the prompt. The first registered matching key wins.
    Every call is recorded in `calls` as (method, prompt) so tests can assert on what was asked.
    """

    name = "mock"

    def __init__(self) -> None:
        self._text: dict[str, str] = {}
        self._structured: dict[str, Factory] = {}
        self._search: dict[str, GroundedAnswer | Factory] = {}
        self._loops: dict[str, TurnScript] = {}
        self.calls: list[tuple[str, str]] = []

    def register_text(self, key: str, text: str) -> None:
        self._text[key] = text

    def register_structured(self, key: str, factory: Factory) -> None:
        self._structured[key] = factory

    def register_search(self, key: str, answer: GroundedAnswer | Factory) -> None:
        self._search[key] = answer

    def register_tool_loop(self, key: str, script: TurnScript) -> None:
        """`script(history)` returns the next ToolTurn. `key` is matched against the first user_input's text."""
        self._loops[key] = script

    def generate_text(self, prompt: str, *, system: str | None = None, model: str | None = None,
                      thinking_level: str | None = None) -> str:
        self.calls.append(("text", prompt))
        for key, text in self._text.items():
            if key in prompt:
                return text
        raise LLMUnavailable("MockLLM: no canned text response for this prompt")

    def generate_structured(self, prompt: str, schema: type[T], *, system: str | None = None,
                            model: str | None = None, thinking_level: str | None = None) -> T:
        self.calls.append(("structured", prompt))
        for key, factory in self._structured.items():
            if key in prompt:
                value = factory()
                if isinstance(value, Exception):
                    raise value
                return value if isinstance(value, schema) else schema.model_validate(value)
        raise LLMUnavailable("MockLLM: no canned structured response for this prompt")

    def search_grounded(self, prompt: str, *, system: str | None = None, model: str | None = None,
                        thinking_level: str | None = None) -> GroundedAnswer:
        self.calls.append(("search", prompt))
        for key, answer in self._search.items():
            if key in prompt:
                value = answer if isinstance(answer, GroundedAnswer) else answer()
                if isinstance(value, Exception):
                    raise value
                return value
        raise LLMUnavailable("MockLLM: no canned search response for this prompt")

    def tool_turn(self, history: list[dict[str, Any]], *, tools: list[dict[str, Any]], system: str | None = None,
                  model: str | None = None, thinking_level: str | None = "low",
                  timeout_s: float | None = None) -> ToolTurn:
        first = next((h for h in history if h.get("type") == "user_input"), {})
        prompt = " ".join(c.get("text", "") for c in first.get("content", []))
        self.calls.append(("tool_turn", prompt))
        for key, script in self._loops.items():
            if key in prompt:
                turn = script(history)
                if isinstance(turn, Exception):
                    raise turn
                return turn
        raise LLMUnavailable("MockLLM: no scripted tool loop for this prompt")


# ---------------------------------------------------------------------------------------------------- live Gemini

_client_lock = threading.Lock()
_genai_clients: dict[str, Any] = {}  # one google-genai client per process (keyed by API key)


def _shared_client(api_key: str) -> Any:
    with _client_lock:
        if api_key not in _genai_clients:
            try:
                from google import genai
                from google.genai import types
            except ImportError as exc:  # pragma: no cover - depends on the environment
                raise LLMUnavailable("google-genai is not installed") from exc
            # SDK-level retries are switched off: this module owns the retry policy.
            _genai_clients[api_key] = genai.Client(
                api_key=api_key, http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1))
            )
        return _genai_clients[api_key]


def _is_retryable(exc: BaseException) -> bool:
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status == 429 or status >= 500
    if isinstance(exc, TimeoutError | ConnectionError):
        return True
    name = type(exc).__name__.lower()
    return "timeout" in name or "connection" in name or "transport" in name or "network" in name


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _usage(interaction: Any) -> tuple[int, int, int]:
    usage = _get(interaction, "usage")
    return (int(_get(usage, "total_input_tokens", 0) or 0), int(_get(usage, "total_output_tokens", 0) or 0),
            int(_get(usage, "total_thought_tokens", 0) or 0))


def parse_grounding(interaction: Any) -> tuple[str, list[Citation], list[str]]:
    """Pull answer text, grounding citations and executed queries out of an Interaction (or its dict dump).

    Field names checked against a logged raw response: `google_search_call.arguments.queries`, and `url_citation`
    annotations (`url`, `title`, `start_index`, `end_index`) on `model_output` text blocks.
    `google_search_result` items currently carry only `search_suggestions` HTML, but any `url` / `title` they hold
    is accepted too, since that is also grounding metadata.
    """
    texts: list[str] = []
    citations: list[Citation] = []
    queries: list[str] = []
    seen: set[str] = set()

    def add(url: Any, title: Any, cited: str | None) -> None:
        if isinstance(url, str) and url.startswith(("http://", "https://")) and url not in seen:
            seen.add(url)
            citations.append(Citation(url=url, title=title if isinstance(title, str) else None, cited_text=cited))

    for step in _get(interaction, "steps") or []:
        kind = _get(step, "type")
        if kind == "google_search_call":
            for q in _get(_get(step, "arguments"), "queries") or []:
                if isinstance(q, str) and q not in queries:
                    queries.append(q)
        elif kind == "google_search_result":
            for item in _get(step, "result") or []:
                add(_get(item, "url"), _get(item, "title"), None)
        elif kind == "model_output":
            for block in _get(step, "content") or []:
                if _get(block, "type") != "text":
                    continue
                text = _get(block, "text") or ""
                texts.append(text)
                for ann in _get(block, "annotations") or []:
                    if _get(ann, "type") == "url_citation":
                        start, end = _get(ann, "start_index"), _get(ann, "end_index")
                        cited = text[start:end] if isinstance(start, int) and isinstance(end, int) else None
                        add(_get(ann, "url"), _get(ann, "title"), cited)
    return "\n".join(texts).strip(), citations, queries


class GeminiLLM:
    """Live Gemini via the Interactions API. One client per process, `store=False`, system instruction per call."""

    name = "gemini"

    def __init__(self, api_key: str | None = None, model_fast: str | None = None, model_deep: str | None = None, *,
                 client: Any = None, timeout_s: float = DEFAULT_TIMEOUT_S,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.gemini_api_key
        self.model_fast = model_fast or settings.model_fast
        self.model_deep = model_deep or settings.model_deep
        self._client = client
        self.timeout_s = timeout_s
        self._sleep = sleep

    def _get_client(self) -> Any:
        if self._client is None:
            if get_settings().mode == "mock":
                raise LLMUnavailable("JANE_MODE=mock: live Gemini calls are disabled")
            if not self._api_key:
                raise LLMUnavailable("GEMINI_API_KEY is not set")
            self._client = _shared_client(self._api_key)
        return self._client

    def interact(self, input: Any, *, model: str | None = None, system: str | None = None,
                 tools: list[dict[str, Any]] | None = None, response_format: dict[str, Any] | None = None,
                 generation_config: dict[str, Any] | None = None, timeout_s: float | None = None,
                 purpose: str = "call", max_attempts: int = MAX_ATTEMPTS) -> Any:
        """One `interactions.create` call with retries and usage logging. Returns the SDK Interaction.
        `max_attempts` (at most MAX_ATTEMPTS) lets time-budgeted callers retry less."""
        max_attempts = max(1, min(MAX_ATTEMPTS, max_attempts))
        client = self._get_client()
        model = model or self.model_fast
        body: dict[str, Any] = {"model": model, "input": input, "store": False}
        if system:
            body["system_instruction"] = system
        if tools:
            body["tools"] = tools
        if response_format:
            body["response_format"] = response_format
        if generation_config:
            body["generation_config"] = generation_config
        last: BaseException | None = None
        for attempt in range(1, max_attempts + 1):
            t0 = time.monotonic()
            try:
                interaction = client.interactions.create(**body, timeout=timeout_s or self.timeout_s)
            except Exception as exc:
                last = exc
                ms = int((time.monotonic() - t0) * 1000)
                retry = _is_retryable(exc) and attempt < max_attempts
                log.warning("gemini call failed model=%s purpose=%s attempt=%d ms=%d retry=%s error=%s",
                            model, purpose, attempt, ms, retry, f"{type(exc).__name__}: {exc}"[:300])
                if not retry:
                    break
                self._sleep(BACKOFF_S[attempt - 1])
                continue
            ms = int((time.monotonic() - t0) * 1000)
            in_tok, out_tok, thought_tok = _usage(interaction)
            log.info("gemini call model=%s purpose=%s in_tokens=%d out_tokens=%d thought_tokens=%d ms=%d",
                     model, purpose, in_tok, out_tok, thought_tok, ms)
            status = _get(interaction, "status")
            if status not in (None, "completed", "requires_action"):  # requires_action = waiting on our function
                raise LLMUnavailable(f"Gemini interaction ended with status {status!r}")
            return interaction
        raise LLMUnavailable(f"Gemini call failed after retries: {type(last).__name__}: {last}"[:500]) from last

    @staticmethod
    def _config(thinking_level: str | None) -> dict[str, Any] | None:
        return {"thinking_level": thinking_level} if thinking_level else None

    def generate_text(self, prompt: str, *, system: str | None = None, model: str | None = None,
                      thinking_level: str | None = None) -> str:
        interaction = self.interact(prompt, model=model, system=system, generation_config=self._config(thinking_level),
                                    purpose="text")
        text = _get(interaction, "output_text")
        if not text:
            raise LLMUnavailable("Gemini returned no text")
        return text

    def generate_structured(self, prompt: str, schema: type[T], *, system: str | None = None,
                            model: str | None = None, thinking_level: str | None = None) -> T:
        """Native structured output (JSON schema from the Pydantic model), validated with Pydantic.
        On a validation error the call is retried once with the error appended to the prompt."""
        response_format = {"type": "text", "mime_type": "application/json", "schema": schema.model_json_schema()}
        attempt_prompt = prompt
        for attempt in (1, 2):
            interaction = self.interact(attempt_prompt, model=model, system=system, response_format=response_format,
                                        generation_config=self._config(thinking_level),
                                        purpose=f"structured:{schema.__name__}")
            raw = _get(interaction, "output_text") or ""
            try:
                return schema.model_validate_json(raw)
            except ValidationError as exc:
                if attempt == 2:
                    raise LLMUnavailable(f"Gemini output failed {schema.__name__} validation twice: {exc}"[:500]) \
                        from exc
                log.warning("structured output failed validation schema=%s; retrying once", schema.__name__)
                attempt_prompt = (f"{prompt}\n\nYour previous reply did not validate against the JSON schema:\n"
                                  f"{str(exc)[:1500]}\nReply again with JSON that matches the schema exactly.")
        raise AssertionError("unreachable")  # pragma: no cover

    def search_grounded(self, prompt: str, *, system: str | None = None, model: str | None = None,
                        thinking_level: str | None = "low") -> GroundedAnswer:
        """Answer `prompt` with the built-in Google Search tool. Citations come from grounding metadata only."""
        model = model or self.model_fast
        interaction = self.interact(prompt, model=model, system=system, tools=[{"type": "google_search"}],
                                    generation_config=self._config(thinking_level), timeout_s=90.0,
                                    purpose="google_search")
        text, citations, queries = parse_grounding(interaction)
        return GroundedAnswer(text=text, citations=citations, queries=queries, model=model)

    def tool_turn(self, history: list[dict[str, Any]], *, tools: list[dict[str, Any]], system: str | None = None,
                  model: str | None = None, thinking_level: str | None = "low",
                  timeout_s: float | None = None) -> ToolTurn:
        """One stateless turn of a tool loop (`store=False`, so the caller passes the whole history every time).
        Built-in tools (e.g. `{"type": "google_search"}`) and function declarations can be combined. The loop runs
        against a wall-clock budget, so a turn is tried at most twice."""
        interaction = self.interact(history, model=model, system=system, tools=tools,
                                    generation_config=self._config(thinking_level), timeout_s=timeout_s,
                                    purpose="tool_turn", max_attempts=2)
        return parse_turn(interaction)


_llm: LLMClient | None = None


def get_llm() -> LLMClient:
    """MockLLM in mock mode; GeminiLLM otherwise. Cached per process."""
    global _llm
    if _llm is None:
        _llm = MockLLM() if get_settings().mode == "mock" else GeminiLLM()
    return _llm
