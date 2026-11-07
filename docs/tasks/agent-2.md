# TASK: Maths / risk engine (agent-2)

**Owner:** agent-2. **Paths:** risk/, tests/risk/. Read PROJECT.md first.

## Objective
Replace the heuristic stub in `risk/score.py` with a trained, calibrated model. All maths lives here; no LLM in `risk/`.

## Requirements
1. Features: velocity, amount vs account history, fan-in/fan-out, new counterparty, round amounts, balance drained.
2. Model: scikit-learn `HistGradientBoostingClassifier`, trained on train only; calibrate on val (isotonic).
3. Uncertainty: split-conformal or bootstrap-ensemble interval; `uncertain=True` when the interval is wide or features are outside the training range.
4. `top_factors` per alert (permutation importance or per-feature contributions). Save the model with a `model_version` string.
5. Keep `score(alerts, txns) -> list[RiskScore]` and its output order (same as input alerts).

## Completion criteria
- Unit tests for every feature; `python -m pytest` passes; pipeline still runs end to end.
