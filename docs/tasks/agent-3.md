# TASK: Gemini triage agent (agent-3)

**Owner:** agent-3. **Paths:** agent/, tests/agent/. Read PROJECT.md first.

## Objective
Replace the template in `agent/triage.py` with a Gemini agent that investigates an alert and writes a cited case note.

## Requirements
1. `google-genai>=2.30.1`, model `gemini-3.8-flash`, `client = genai.Client()` created once and reused, `store=False`. Follow the gemini-api-dev skill and its docs for the Interactions API, structured output and function calling. Do not guess API calls.
2. Read-only tools: account history, counterparties, risk score; each returns evidence IDs.
3. Output must parse into `Recommendation`. The LLM never calculates: every number comes from a tool and appears in `numbers_cited` with a source key understood by `controls/validator.py`.
4. Memo text is passed as quoted data, never as instructions.
5. On validator failure: one retry, then `template_recommendation()` fallback. Cache responses to `.cache/` so the demo is reproducible offline.
6. Tests use a mocked Gemini client. No live API calls in pytest.

## Completion criteria
- `python -m pytest` passes without an API key; pipeline runs end to end with and without a key.
