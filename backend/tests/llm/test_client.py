"""Gemini gateway tests. Offline: a fake Interactions client stands in for google-genai. Owner: agent-2."""
from __future__ import annotations

import logging
from typing import Any, Literal

import pytest
from pydantic import BaseModel

from jane_avenue.llm import GeminiLLM, GroundedAnswer, LLMUnavailable, MockLLM, get_llm
from jane_avenue.llm.client import parse_grounding


class Item(BaseModel):
    claim: str
    value: float | None
    kind: Literal["quantitative", "qualitative"]


class Items(BaseModel):
    items: list[Item]


class FakeAPIError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


class APITimeoutError(Exception):
    pass


def _interaction(text: str, *, status: str = "completed", steps: list[dict] | None = None) -> dict[str, Any]:
    return {"status": status, "output_text": text,
            "usage": {"total_input_tokens": 11, "total_output_tokens": 7, "total_thought_tokens": 3},
            "steps": steps if steps is not None else [{"type": "model_output", "content": [{"type": "text",
                                                                                            "text": text}]}]}


class FakeInteractions:
    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = list(outcomes)
        self.requests: list[dict[str, Any]] = []

    def create(self, **body: Any) -> Any:
        self.requests.append(body)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class FakeClient:
    def __init__(self, outcomes: list[Any]) -> None:
        self.interactions = FakeInteractions(outcomes)


def _llm(outcomes: list[Any]) -> tuple[GeminiLLM, FakeClient, list[float]]:
    sleeps: list[float] = []
    client = FakeClient(outcomes)
    return GeminiLLM(api_key="test", client=client, sleep=sleeps.append), client, sleeps


GOOD = '{"items": [{"claim": "Receipts rose", "value": 17.2, "kind": "quantitative"}]}'


def test_generate_structured_uses_native_schema_store_false_and_system() -> None:
    llm, client, _ = _llm([_interaction(GOOD)])
    out = llm.generate_structured("extract", Items, system="be exact", thinking_level="low")
    assert out.items[0].value == 17.2
    req = client.interactions.requests[0]
    assert req["store"] is False
    assert req["system_instruction"] == "be exact"
    assert req["response_format"] == {"type": "text", "mime_type": "application/json",
                                      "schema": Items.model_json_schema()}
    assert req["generation_config"] == {"thinking_level": "low"}
    assert req["model"] == llm.model_fast


def test_generate_structured_retries_once_with_validation_error() -> None:
    llm, client, _ = _llm([_interaction('{"items": [{"claim": "x"}]}'), _interaction(GOOD)])
    out = llm.generate_structured("extract", Items)
    assert out.items[0].claim == "Receipts rose"
    second_prompt = client.interactions.requests[1]["input"]
    assert second_prompt.startswith("extract") and "did not validate" in second_prompt


def test_generate_structured_gives_up_after_second_invalid_reply() -> None:
    llm, _, _ = _llm([_interaction("not json"), _interaction("{}")])
    with pytest.raises(LLMUnavailable, match="validation"):
        llm.generate_structured("extract", Items)


@pytest.mark.parametrize("error", [FakeAPIError(429), FakeAPIError(503), APITimeoutError("slow")])
def test_retries_with_backoff_on_transient_errors(error: Exception) -> None:
    llm, client, sleeps = _llm([error, error, _interaction("ok")])
    assert llm.generate_text("hi") == "ok"
    assert sleeps == [1.0, 2.0]
    assert len(client.interactions.requests) == 3


def test_raises_unavailable_when_retries_are_exhausted() -> None:
    llm, client, sleeps = _llm([FakeAPIError(429)] * 3)
    with pytest.raises(LLMUnavailable, match="after retries"):
        llm.generate_text("hi")
    assert len(client.interactions.requests) == 3 and sleeps == [1.0, 2.0]


def test_client_errors_are_not_retried() -> None:
    llm, client, sleeps = _llm([FakeAPIError(400)])
    with pytest.raises(LLMUnavailable):
        llm.generate_text("hi")
    assert len(client.interactions.requests) == 1 and sleeps == []


def test_failed_interaction_status_is_unavailable() -> None:
    llm, _, _ = _llm([_interaction("", status="failed")])
    with pytest.raises(LLMUnavailable, match="failed"):
        llm.generate_text("hi")


def test_empty_text_is_unavailable() -> None:
    llm, _, _ = _llm([_interaction("")])
    with pytest.raises(LLMUnavailable):
        llm.generate_text("hi")


def test_logs_model_latency_and_token_usage(caplog: pytest.LogCaptureFixture) -> None:
    llm, _, _ = _llm([_interaction("ok")])
    with caplog.at_level(logging.INFO, logger="jane_avenue.llm.client"):
        llm.generate_text("hi")
    line = next(r.getMessage() for r in caplog.records if "gemini call" in r.getMessage())
    assert f"model={llm.model_fast}" in line and "in_tokens=11" in line and "out_tokens=7" in line and "ms=" in line


def test_no_live_calls_in_mock_mode_or_without_key() -> None:
    with pytest.raises(LLMUnavailable, match="mock"):
        GeminiLLM(api_key="test").generate_text("hi")  # tests run with JANE_MODE=mock


def test_get_llm_is_mock_in_mock_mode() -> None:
    assert isinstance(get_llm(), MockLLM)


RAW_SEARCH = {  # trimmed from a logged live response (field names verified against the API)
    "status": "completed",
    "steps": [
        {"type": "thought", "signature": "abc"},
        {"type": "google_search_call", "id": "call_1", "arguments": {"queries": ["UK corporation tax main rate"]}},
        {"type": "google_search_result", "call_id": "call_1", "result": [{"search_suggestions": "<style>"}]},
        {"type": "model_output", "content": [{
            "type": "text", "text": "The main rate is 25%. It rose in 2023.",
            "annotations": [
                {"type": "url_citation", "title": "www.gov.uk", "start_index": 0, "end_index": 21,
                 "url": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AAA"},
                {"type": "url_citation", "title": "obr.uk", "start_index": 22, "end_index": 38,
                 "url": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/BBB"},
                {"type": "url_citation", "title": "www.gov.uk", "start_index": 22, "end_index": 38,
                 "url": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AAA"},
                {"type": "file_citation", "url": "ftp://not-a-web-source"},
            ]}]},
    ],
}


def test_parse_grounding_reads_queries_and_deduplicated_url_citations() -> None:
    text, citations, queries = parse_grounding(RAW_SEARCH)
    assert text == "The main rate is 25%. It rose in 2023."
    assert queries == ["UK corporation tax main rate"]
    assert [c.title for c in citations] == ["www.gov.uk", "obr.uk"]
    assert citations[0].cited_text == "The main rate is 25%."


def test_search_grounded_sends_google_search_tool() -> None:
    llm, client, _ = _llm([RAW_SEARCH])
    answer = llm.search_grounded("What is the CT main rate?")
    assert client.interactions.requests[0]["tools"] == [{"type": "google_search"}]
    assert len(answer.citations) == 2 and answer.model == llm.model_fast


def test_mock_llm_serves_registered_responses_and_records_calls() -> None:
    mock = MockLLM()
    mock.register_text("joke", "ha")
    mock.register_structured("extract", lambda: {"items": []})
    mock.register_search("rate", GroundedAnswer(text="25%"))
    assert mock.generate_text("tell a joke") == "ha"
    assert mock.generate_structured("extract this", Items).items == []
    assert mock.search_grounded("main rate?").text == "25%"
    assert [c[0] for c in mock.calls] == ["text", "structured", "search"]
    for call in (lambda: mock.generate_text("x"), lambda: mock.generate_structured("x", Items),
                 lambda: mock.search_grounded("x")):
        with pytest.raises(LLMUnavailable):
            call()
