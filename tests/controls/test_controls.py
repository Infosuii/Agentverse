from agent.triage import triage
from controls import audit
from controls.policy import decide
from controls.validator import validate
from data.alerts import make_alerts
from data.loaders import load_transactions
from risk.score import score


def _first(split="val"):
    txns = load_transactions(split)
    alerts = make_alerts(txns)
    scores = score(alerts, txns)
    return txns, alerts, scores


def test_validator_catches_wrong_number():
    txns, alerts, scores = _first()
    rec = triage(alerts[0], scores[0], txns)
    bad = rec.model_copy(update={"numbers_cited": {**rec.numbers_cited, "score.probability": 0.999}})
    assert any("mismatch" in e for e in validate(bad, scores[0], alerts[0], txns))


def test_validator_catches_uncited_number_and_fake_evidence():
    txns, alerts, scores = _first()
    rec = triage(alerts[0], scores[0], txns)
    bad = rec.model_copy(update={"case_note": rec.case_note + " Loss could be 123456.", "evidence_ids": ["FAKE1"]})
    errs = validate(bad, scores[0], alerts[0], txns)
    assert any("uncited number" in e for e in errs)
    assert any("unknown evidence" in e for e in errs)


def test_policy_blocks_unsafe_close():
    txns, alerts, scores = _first()
    i = max(range(len(scores)), key=lambda j: scores[j].probability)
    rec = triage(alerts[i], scores[i], txns).model_copy(update={"action": "close"})
    d = decide(rec, scores[i], alerts[i], txns)
    assert d.final_action == "human_review" and d.requires_human
    assert any(b.startswith("close_blocked") for b in d.blocked)


def test_memo_injection_is_flagged():
    txns, alerts, scores = _first("test")
    hits = [k for k, a in enumerate(alerts) if any("Ignore all previous" in t.memo for t in txns if t.txn_id in a.txn_ids)]
    assert hits, "sample should contain one injection memo in the test split"
    k = hits[0]
    rec = triage(alerts[k], scores[k], txns).model_copy(update={"action": "close"})
    d = decide(rec, scores[k], alerts[k], txns)
    assert d.final_action == "human_review"
    assert any(b.startswith("memo_injection_flagged") for b in d.blocked)


def test_audit_chain_detects_tampering(tmp_path):
    p = tmp_path / "audit.jsonl"
    for i in range(3):
        audit.log("agent", f"A{i}", {"i": i}, p)
    assert audit.verify_chain(p)
    lines = p.read_text(encoding="utf-8").splitlines()
    lines[1] = lines[1].replace('"i": 1', '"i": 99')
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert not audit.verify_chain(p)
