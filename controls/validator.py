"""Check the agent's case note against the maths. Owner: agent-4.

The person checking the LLM is not the person building it.
"""
import re

from contracts.schemas import Alert, Recommendation, RiskScore, Transaction

TOL = 1e-3
_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def _source_value(key: str, score: RiskScore, alert: Alert, by_id: dict[str, Transaction]) -> float | None:
    if key in ("score.probability", "score.interval_low", "score.interval_high"):
        return getattr(score, key.split(".", 1)[1])
    if key == "alert.n_txns":
        return float(len(alert.txn_ids))
    if key.startswith("factor."):
        name = key.split(".", 1)[1]
        for f in score.top_factors:
            if f.name == name:
                return f.value
        return None
    m = re.fullmatch(r"txn\.(.+)\.amount_gbp", key)
    if m and m.group(1) in by_id and m.group(1) in alert.txn_ids:
        return by_id[m.group(1)].amount_gbp
    return None


def validate(rec: Recommendation, score: RiskScore, alert: Alert, txns: list[Transaction]) -> list[str]:
    """Return a list of problems; an empty list means the note is valid."""
    errors: list[str] = []
    by_id = {t.txn_id: t for t in txns}
    if rec.alert_id != alert.alert_id or score.alert_id != alert.alert_id:
        errors.append("alert_id mismatch")

    valid_evidence = set(alert.txn_ids) | {f.name for f in score.top_factors} | {"score"}
    for e in rec.evidence_ids:
        if e not in valid_evidence:
            errors.append(f"unknown evidence id: {e}")

    for key, value in rec.numbers_cited.items():
        src = _source_value(key, score, alert, by_id)
        if src is None:
            errors.append(f"unknown number source: {key}")
        elif abs(round(src, 3) - value) > TOL:
            errors.append(f"number mismatch for {key}: note says {value}, source is {src}")

    # Every number written in the note must be one of the cited numbers.
    text = rec.case_note.replace(alert.alert_id, " ")
    for ident in sorted(valid_evidence | set(rec.evidence_ids), key=len, reverse=True):
        text = text.replace(ident, " ")
    cited = list(rec.numbers_cited.values())
    for tok in _NUM.findall(text):
        if not any(abs(float(tok) - c) <= TOL for c in cited):
            errors.append(f"uncited number in note: {tok}")
    return errors
