# TASK: Controls and oversight (agent-4)

**Owner:** agent-4. **Paths:** controls/, tests/controls/. Read PROJECT.md first.

## Objective
Harden the validator, policy engine, injection guard and audit log, and prove them with a red-team suite.
This stream carries the 15% "risk controls and oversight" score and supports traceability.

## Requirements
1. `validate`: every number in the note matches `numbers_cited`, which matches tool outputs and the `RiskScore`; every evidence ID exists.
2. `decide`: hard limits from `controls/limits.py` only (thresholds agreed by the team in Issue #8). Escalations and failed validation need a human.
3. Injection guard: instruction-like memo text is flagged and can never change an outcome.
4. `audit.log` / `verify_chain`: append-only, SHA-256 hash chain, tamper detection.
5. Red-team suite (at least 10 attacks: memo injection, fake evidence IDs, number mismatch, missing fields, Gemini outage). Report the pass rate in `controls/REDTEAM.md` for the deck.
6. Script the one live control for the demo.

## Completion criteria
- `python -m pytest` passes, including the red-team suite.
